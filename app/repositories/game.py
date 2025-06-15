"""
Repository pour la gestion des jeux
Opérations CRUD et requêtes spécialisées pour les parties et tentatives
CORRECTION: Noms de champs synchronisés avec la BDD
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, select, or_, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.game import Game, GameParticipation, GameAttempt, GameStatus, GameType, GameMode, ParticipationStatus
from app.schemas.game import GameCreate, GameUpdate, GameSearch
from .base import BaseRepository


class GameRepository(BaseRepository[Game, GameCreate, GameUpdate]):
    """Repository pour les jeux avec méthodes spécialisées"""

    def __init__(self):
        super().__init__(Game)

    # === MÉTHODES DE RECHERCHE SPÉCIALISÉES ===

    async def get_by_unique_field(
            self,
            db: AsyncSession,
            field_value: str
    ) -> Optional[Game]:
        """Récupère un jeu par room_code (implémentation abstraite)"""
        return await self.get_by_room_code(db, field_value)

    async def get_by_room_code(
            self,
            db: AsyncSession,
            room_code: str,
            *,
            with_players: bool = True,
            with_deleted: bool = False
    ) -> Optional[Game]:
        """
        Récupère un jeu par son code de room
        CORRECTION: room_code (pas room_id)

        Args:
            db: Session de base de données
            room_code: Code de la room
            with_players: Charger les joueurs
            with_deleted: Inclure les jeux supprimés

        Returns:
            Le jeu ou None
        """
        query = select(Game).where(Game.room_code == room_code.upper())

        if not with_deleted and hasattr(Game, 'is_deleted'):
            query = query.where(Game.is_deleted.is_(False))

        if with_players:
            query = query.options(selectinload(Game.participations))

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_game_with_full_details(
            self,
            db: AsyncSession,
            game_id: UUID
    ) -> Optional[Game]:
        """
        Récupère un jeu avec tous ses détails (joueurs, tentatives)

        Args:
            db: Session de base de données
            game_id: ID du jeu

        Returns:
            Le jeu avec toutes ses relations
        """
        query = (
            select(Game)
            .options(
                selectinload(Game.participations).selectinload(GameParticipation.player),
                selectinload(Game.attempts).selectinload(GameAttempt.player),
                selectinload(Game.creator)
            )
            .where(Game.id == game_id)
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def search_games(
            self,
            db: AsyncSession,
            search_params: GameSearch,
            offset: int = 0,
            limit: int = 20
    ) -> tuple[List[Game], int]:
        """
        Recherche des jeux selon des critères

        Args:
            db: Session de base de données
            search_params: Paramètres de recherche
            offset: Décalage pour la pagination
            limit: Limite de résultats

        Returns:
            Tuple (liste des jeux, total)
        """
        # Construction de la requête de base
        query = select(Game).options(
            selectinload(Game.creator),
            selectinload(Game.participations)
        )

        # Application des filtres
        conditions = []

        if search_params.game_type:
            conditions.append(Game.game_type == search_params.game_type)

        if search_params.game_mode:
            conditions.append(Game.game_mode == search_params.game_mode)

        if search_params.status:
            conditions.append(Game.status == search_params.status)

        if search_params.difficulty:
            conditions.append(Game.difficulty == search_params.difficulty)

        if search_params.creator_id:
            conditions.append(Game.creator_id == search_params.creator_id)

        if search_params.room_code:
            conditions.append(Game.room_code.ilike(f"%{search_params.room_code}%"))

        if search_params.public_only:
            conditions.append(Game.is_private == False)

        if search_params.min_players:
            # Compter les participants actifs
            active_participants = (
                select(func.count(GameParticipation.id))
                .where(
                    and_(
                        GameParticipation.game_id == Game.id,
                        GameParticipation.status != ParticipationStatus.DISCONNECTED
                    )
                )
                .scalar_subquery()
            )
            conditions.append(active_participants >= search_params.min_players)

        if search_params.max_players:
            conditions.append(Game.max_players <= search_params.max_players)

        # Application des conditions
        if conditions:
            query = query.where(and_(*conditions))

        # Comptage total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Application de l'ordre et pagination
        query = query.order_by(desc(Game.created_at))
        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        games = result.scalars().all()

        return list(games), total

    async def get_user_games(
            self,
            db: AsyncSession,
            user_id: UUID,
            status_filter: Optional[GameStatus] = None,
            offset: int = 0,
            limit: int = 20
    ) -> tuple[List[Game], int]:
        """
        Récupère les jeux d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur
            status_filter: Filtre sur le statut
            offset: Décalage pour la pagination
            limit: Limite de résultats

        Returns:
            Tuple (liste des jeux, total)
        """
        # Jeux créés ou auxquels l'utilisateur participe
        query = (
            select(Game)
            .options(
                selectinload(Game.creator),
                selectinload(Game.participations).selectinload(GameParticipation.player)
            )
            .where(
                or_(
                    Game.creator_id == user_id,
                    Game.participations.any(GameParticipation.player_id == user_id)
                )
            )
        )

        if status_filter:
            query = query.where(Game.status == status_filter)

        # Comptage total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Application de l'ordre et pagination
        query = query.order_by(desc(Game.created_at))
        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        games = result.scalars().all()

        return list(games), total

    async def get_public_games(
            self,
            db: AsyncSession,
            offset: int = 0,
            limit: int = 20
    ) -> tuple[List[Game], int]:
        """
        Récupère les jeux publics

        Args:
            db: Session de base de données
            offset: Décalage pour la pagination
            limit: Limite de résultats

        Returns:
            Tuple (liste des jeux, total)
        """
        query = (
            select(Game)
            .options(
                selectinload(Game.creator),
                selectinload(Game.participations)
            )
            .where(
                and_(
                    Game.is_private == False,
                    Game.status.in_([GameStatus.WAITING, GameStatus.ACTIVE])
                )
            )
        )

        # Comptage total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Application de l'ordre et pagination
        query = query.order_by(desc(Game.created_at))
        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        games = result.scalars().all()

        return list(games), total

    async def get_games_statistics(
            self,
            db: AsyncSession,
            time_period: str = "all"
    ) -> Dict[str, Any]:
        """
        Récupère les statistiques des jeux

        Args:
            db: Session de base de données
            time_period: Période (all, month, week, day)

        Returns:
            Dictionnaire des statistiques
        """
        # Calcul de la date de début selon la période
        now = datetime.now(timezone.utc)
        if time_period == "day":
            start_date = now - timedelta(days=1)
        elif time_period == "week":
            start_date = now - timedelta(weeks=1)
        elif time_period == "month":
            start_date = now - timedelta(days=30)
        else:
            start_date = None

        # Construction de la requête de base
        query = select(Game)
        if start_date:
            query = query.where(Game.created_at >= start_date)

        # Statistiques générales
        stats_query = select(
            func.count(Game.id).label('total_games'),
            func.count(case((Game.status == GameStatus.FINISHED, 1))).label('finished_games'),
            func.count(case((Game.status == GameStatus.ACTIVE, 1))).label('active_games'),
            func.count(case((Game.status == GameStatus.WAITING, 1))).label('waiting_games'),
            func.avg(Game.max_players).label('avg_players'),
            func.count(case((Game.quantum_enabled == True, 1))).label('quantum_games')
        ).select_from(Game)

        if start_date:
            stats_query = stats_query.where(Game.created_at >= start_date)

        result = await db.execute(stats_query)
        stats = result.first()

        return {
            'total_games': stats.total_games or 0,
            'finished_games': stats.finished_games or 0,
            'active_games': stats.active_games or 0,
            'waiting_games': stats.waiting_games or 0,
            'average_players': float(stats.avg_players or 0),
            'quantum_games': stats.quantum_games or 0,
            'period': time_period
        }


class GameParticipationRepository(BaseRepository[GameParticipation, dict, dict]):
    """Repository pour les participations de jeu"""

    def __init__(self):
        super().__init__(GameParticipation)

    async def get_by_unique_field(
            self,
            db: AsyncSession,
            field_value: Any
    ) -> Optional[GameParticipation]:
        """Implémentation abstraite"""
        return None

    async def get_player_in_game(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: UUID
    ) -> Optional[GameParticipation]:
        """
        Récupère la participation d'un joueur dans une partie
        CORRECTION: player_id (pas user_id)

        Args:
            db: Session de base de données
            game_id: ID de la partie
            user_id: ID de l'utilisateur

        Returns:
            Le joueur ou None
        """
        query = select(GameParticipation).where(
            and_(
                GameParticipation.game_id == game_id,
                GameParticipation.player_id == user_id
            )
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_game_players(
            self,
            db: AsyncSession,
            game_id: UUID,
            *,
            active_only: bool = False
    ) -> List[GameParticipation]:
        """
        Récupère tous les joueurs d'une partie

        Args:
            db: Session de base de données
            game_id: ID de la partie
            active_only: Seulement les joueurs actifs

        Returns:
            Liste des joueurs
        """
        query = select(GameParticipation).where(GameParticipation.game_id == game_id)

        if active_only:
            query = query.where(
                GameParticipation.status != ParticipationStatus.DISCONNECTED
            )

        query = query.order_by(GameParticipation.join_order)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_user_active_participations(
            self,
            db: AsyncSession,
            user_id: UUID
    ) -> List[GameParticipation]:
        """
        Récupère les participations actives d'un utilisateur
        CORRECTION: player_id (pas user_id)

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur

        Returns:
            Liste des participations actives
        """
        query = (
            select(GameParticipation)
            .options(selectinload(GameParticipation.game))
            .where(
                and_(
                    GameParticipation.player_id == user_id,
                    GameParticipation.status.in_([
                        ParticipationStatus.WAITING,
                        ParticipationStatus.READY,
                        ParticipationStatus.ACTIVE
                    ])
                )
            )
        )

        result = await db.execute(query)
        return list(result.scalars().all())


class GameAttemptRepository(BaseRepository[GameAttempt, dict, dict]):
    """Repository pour les tentatives de jeu"""

    def __init__(self):
        super().__init__(GameAttempt)

    async def get_by_unique_field(
            self,
            db: AsyncSession,
            field_value: Any
    ) -> Optional[GameAttempt]:
        """Implémentation abstraite"""
        return None

    async def get_player_attempts(
            self,
            db: AsyncSession,
            game_id: UUID,
            player_id: UUID,
            *,
            limit: Optional[int] = None
    ) -> List[GameAttempt]:
        """
        Récupère les tentatives d'un joueur
        CORRECTION: player_id (pas user_id)

        Args:
            db: Session de base de données
            game_id: ID de la partie
            player_id: ID du joueur
            limit: Nombre maximum de tentatives

        Returns:
            Liste des tentatives ordonnées
        """
        query = select(GameAttempt).where(
            and_(
                GameAttempt.game_id == game_id,
                GameAttempt.player_id == player_id
            )
        ).order_by(GameAttempt.attempt_number)

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_game_attempts(
            self,
            db: AsyncSession,
            game_id: UUID,
            *,
            limit: Optional[int] = None
    ) -> List[GameAttempt]:
        """
        Récupère toutes les tentatives d'une partie

        Args:
            db: Session de base de données
            game_id: ID de la partie
            limit: Nombre maximum de tentatives

        Returns:
            Liste des tentatives ordonnées
        """
        query = (
            select(GameAttempt)
            .options(selectinload(GameAttempt.player))
            .where(GameAttempt.game_id == game_id)
            .order_by(GameAttempt.created_at)
        )

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_latest_attempt(
            self,
            db: AsyncSession,
            game_id: UUID,
            player_id: UUID
    ) -> Optional[GameAttempt]:
        """
        Récupère la dernière tentative d'un joueur
        CORRECTION: player_id (pas user_id)

        Args:
            db: Session de base de données
            game_id: ID de la partie
            player_id: ID du joueur

        Returns:
            La dernière tentative ou None
        """
        query = (
            select(GameAttempt)
            .where(
                and_(
                    GameAttempt.game_id == game_id,
                    GameAttempt.player_id == player_id
                )
            )
            .order_by(desc(GameAttempt.attempt_number))
            .limit(1)
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def count_player_attempts(
            self,
            db: AsyncSession,
            game_id: UUID,
            player_id: UUID
    ) -> int:
        """
        Compte les tentatives d'un joueur
        CORRECTION: player_id (pas user_id)

        Args:
            db: Session de base de données
            game_id: ID de la partie
            player_id: ID du joueur

        Returns:
            Nombre de tentatives
        """
        query = select(func.count(GameAttempt.id)).where(
            and_(
                GameAttempt.game_id == game_id,
                GameAttempt.player_id == player_id
            )
        )

        result = await db.execute(query)
        return result.scalar() or 0

    async def get_winning_attempt(
            self,
            db: AsyncSession,
            game_id: UUID
    ) -> Optional[GameAttempt]:
        """
        Récupère la tentative gagnante d'une partie

        Args:
            db: Session de base de données
            game_id: ID de la partie

        Returns:
            La tentative gagnante ou None
        """
        query = (
            select(GameAttempt)
            .options(selectinload(GameAttempt.player))
            .where(
                and_(
                    GameAttempt.game_id == game_id,
                    GameAttempt.is_correct == True
                )
            )
            .order_by(GameAttempt.created_at)
            .limit(1)
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()


# === EXPORTS ===

__all__ = [
    "GameRepository",
    "GameParticipationRepository",
    "GameAttemptRepository"
]