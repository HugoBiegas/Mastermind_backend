"""
Repository pour la gestion des jeux
Opérations CRUD et requêtes spécialisées pour les parties et tentatives
"""
from datetime import datetime, timedelta
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
        """Récupère un jeu par room_id (implémentation abstraite)"""
        return await self.get_by_room_id(db, field_value)

    async def get_by_room_id(
            self,
            db: AsyncSession,
            room_id: str,
            *,
            with_players: bool = True,
            with_deleted: bool = False
    ) -> Optional[Game]:
        """
        Récupère un jeu par son ID de room

        Args:
            db: Session de base de données
            room_id: ID de la room
            with_players: Charger les joueurs
            with_deleted: Inclure les jeux supprimés

        Returns:
            Le jeu ou None
        """
        query = select(Game).where(Game.room_id == room_id.upper())

        if not with_deleted and hasattr(Game, 'is_deleted'):
            query = query.where(Game.is_deleted == False)

        if with_players:
            query = query.options(selectinload(Game.players))

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
            Le jeu complet ou None
        """
        query = select(Game).where(Game.id == game_id).options(
            selectinload(Game.players),
            selectinload(Game.attempts)
        )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    # === MÉTHODES DE RECHERCHE DE PARTIES ===

    async def get_active_games(
            self,
            db: AsyncSession,
            *,
            game_type: Optional[GameType] = None,
            has_slots: bool = False,
            limit: int = 50
    ) -> List[Game]:
        """
        Récupère les parties actives

        Args:
            db: Session de base de données
            game_type: Type de jeu à filtrer
            has_slots: Seulement les parties avec places libres
            limit: Nombre maximum de parties

        Returns:
            Liste des parties actives
        """
        query = select(Game).where(
            Game.status.in_([GameStatus.WAITING, GameStatus.ACTIVE])
        ).options(selectinload(Game.players))

        if game_type:
            query = query.where(Game.game_type == game_type)

        if has_slots:
            # Sous-requête pour compter les joueurs actuels
            player_count = select(func.count(GameParticipation.id)).where(
                and_(
                    GameParticipation.game_id == Game.id,
                    GameParticipation.status != ParticipationStatus.DISCONNECTED
                )
            ).scalar_subquery()

            query = query.where(player_count < Game.max_players)

        query = query.order_by(desc(Game.created_at)).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    async def get_user_games(
            self,
            db: AsyncSession,
            user_id: UUID,
            *,
            status: Optional[GameStatus] = None,
            limit: int = 20
    ) -> List[Game]:
        """
        Récupère les parties d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur
            status: Statut des parties à filtrer
            limit: Nombre maximum de parties

        Returns:
            Liste des parties de l'utilisateur
        """
        # Jointure avec GameParticipation pour récupérer les parties de l'utilisateur
        query = select(Game).join(GameParticipation).where(
            GameParticipation.user_id == user_id
        ).options(selectinload(Game.players))

        if status:
            query = query.where(Game.status == status)

        query = query.order_by(desc(Game.created_at)).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    async def search_games(
            self,
            db: AsyncSession,
            search_criteria: GameSearch
    ) -> Dict[str, Any]:
        """
        Recherche avancée de parties

        Args:
            db: Session de base de données
            search_criteria: Critères de recherche

        Returns:
            Résultats de recherche paginés
        """
        query = select(Game).options(selectinload(Game.players))

        # Filtres
        if search_criteria.game_type:
            query = query.where(Game.game_type == search_criteria.game_type)

        if search_criteria.game_mode:
            query = query.where(Game.game_mode == search_criteria.game_mode)

        if search_criteria.status:
            query = query.where(Game.status == search_criteria.status)

        if search_criteria.difficulty:
            query = query.where(Game.difficulty == search_criteria.difficulty)

        if search_criteria.has_slots:
            # Seulement les parties avec places libres
            player_count = select(func.count(GameParticipation.id)).where(
                GameParticipation.game_id == Game.id
            ).scalar_subquery()
            query = query.where(player_count < Game.max_players)

        if search_criteria.created_by:
            query = query.where(Game.created_by == search_criteria.created_by)

        # Tri
        if search_criteria.sort_by == 'created_at':
            sort_field = Game.created_at
        elif search_criteria.sort_by == 'players_count':
            sort_field = func.count(GameParticipation.id)
        else:
            sort_field = Game.created_at

        if search_criteria.sort_order == 'asc':
            query = query.order_by(sort_field)
        else:
            query = query.order_by(desc(sort_field))

        # Pagination
        total_query = select(func.count(Game.id)).select_from(query.subquery())
        total_result = await db.execute(total_query)
        total = total_result.scalar()

        offset = (search_criteria.page - 1) * search_criteria.page_size
        query = query.offset(offset).limit(search_criteria.page_size)

        result = await db.execute(query)
        games = result.scalars().all()

        return {
            'games': games,
            'total': total,
            'page': search_criteria.page,
            'page_size': search_criteria.page_size,
            'total_pages': (total + search_criteria.page_size - 1) // search_criteria.page_size
        }

    # === MÉTHODES DE VALIDATION ===

    async def is_room_id_available(
            self,
            db: AsyncSession,
            room_id: str
    ) -> bool:
        """
        Vérifie si un ID de room est disponible

        Args:
            db: Session de base de données
            room_id: ID de room à vérifier

        Returns:
            True si disponible
        """
        query = select(func.count(Game.id)).where(
            Game.room_id == room_id.upper()
        )

        result = await db.execute(query)
        count = result.scalar()
        return count == 0

    async def can_user_join_game(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: UUID
    ) -> Dict[str, Any]:
        """
        Vérifie si un utilisateur peut rejoindre une partie

        Args:
            db: Session de base de données
            game_id: ID de la partie
            user_id: ID de l'utilisateur

        Returns:
            Dictionnaire avec can_join et raison si impossible
        """
        game = await self.get_by_id(db, game_id, eager_load=['players'])
        if not game:
            return {'can_join': False, 'reason': 'Partie non trouvée'}

        # Vérifications
        if game.status != GameStatus.WAITING:
            return {'can_join': False, 'reason': 'Partie déjà commencée ou terminée'}

        if game.is_full:
            return {'can_join': False, 'reason': 'Partie complète'}

        # Vérifier si l'utilisateur est déjà dans la partie
        for player in game.players:
            if player.user_id == user_id:
                return {'can_join': False, 'reason': 'Déjà dans la partie'}

        return {'can_join': True}

    # === MÉTHODES DE STATISTIQUES ===

    async def get_game_statistics(
            self,
            db: AsyncSession,
            *,
            period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Récupère les statistiques générales des jeux

        Args:
            db: Session de base de données
            period_days: Période en jours pour les stats

        Returns:
            Dictionnaire des statistiques
        """
        since_date = datetime.utcnow() - timedelta(days=period_days)

        # Requêtes de statistiques
        total_games_query = select(func.count(Game.id))
        active_games_query = select(func.count(Game.id)).where(
            Game.status.in_([GameStatus.WAITING, GameStatus.ACTIVE])
        )
        recent_games_query = select(func.count(Game.id)).where(
            Game.created_at >= since_date
        )

        # Exécution des requêtes
        total_games_result = await db.execute(total_games_query)
        active_games_result = await db.execute(active_games_query)
        recent_games_result = await db.execute(recent_games_query)

        total_games = total_games_result.scalar()
        active_games = active_games_result.scalar()
        recent_games = recent_games_result.scalar()

        # Statistiques par type de jeu
        type_stats_query = select(
            Game.game_type,
            func.count(Game.id).label('count')
        ).group_by(Game.game_type)

        type_stats_result = await db.execute(type_stats_query)
        type_stats = {row.game_type: row.count for row in type_stats_result}

        return {
            'total_games': total_games,
            'active_games': active_games,
            'recent_games': recent_games,
            'games_by_type': type_stats,
            'period_days': period_days
        }

    async def get_user_game_stats(
            self,
            db: AsyncSession,
            user_id: UUID
    ) -> Dict[str, Any]:
        """
        Récupère les statistiques de jeu d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur

        Returns:
            Dictionnaire des statistiques
        """
        # Jointure avec GameParticipation pour les stats
        query = select(
            func.count(GameParticipation.id).label('total_games'),
            func.sum(case((GameParticipation.has_won == True, 1), else_=0)).label('wins'),
            func.avg(GameParticipation.score).label('avg_score'),
            func.sum(GameParticipation.quantum_measurements_used).label('total_measurements'),
            func.sum(GameParticipation.grover_hints_used).label('total_grover_hints'),
            func.avg(GameParticipation.quantum_advantage_score).label('avg_quantum_advantage')
        ).where(GameParticipation.user_id == user_id)

        result = await db.execute(query)
        row = result.first()

        if not row or row.total_games == 0:
            return {
                'total_games': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0,
                'avg_score': 0.0,
                'total_measurements': 0,
                'total_grover_hints': 0,
                'avg_quantum_advantage': 0.0
            }

        total_games = row.total_games or 0
        wins = row.wins or 0

        return {
            'total_games': total_games,
            'wins': wins,
            'losses': total_games - wins,
            'win_rate': (wins / total_games * 100) if total_games > 0 else 0.0,
            'avg_score': float(row.avg_score or 0),
            'total_measurements': row.total_measurements or 0,
            'total_grover_hints': row.total_grover_hints or 0,
            'avg_quantum_advantage': float(row.avg_quantum_advantage or 0)
        }


class GameParticipationRepository(BaseRepository[GameParticipation, dict, dict]):
    """Repository pour les joueurs dans les parties"""

    def __init__(self):
        super().__init__(GameParticipation)

    async def get_by_unique_field(
            self,
            db: AsyncSession,
            field_value: Any
    ) -> Optional[GameParticipation]:
        """Implémentation abstraite - récupère par game_id + user_id"""
        # Cette méthode nécessiterait deux valeurs, on l'adapte
        return None

    async def get_player_in_game(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: UUID
    ) -> Optional[GameParticipation]:
        """
        Récupère un joueur dans une partie spécifique

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
                GameParticipation.user_id == user_id
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
        return result.scalars().all()


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
        return result.scalars().all()

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
            Liste des tentatives
        """
        query = select(GameAttempt).where(
            GameAttempt.game_id == game_id
        ).order_by(GameAttempt.created_at)

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    async def get_latest_attempt(
            self,
            db: AsyncSession,
            game_id: UUID,
            player_id: UUID
    ) -> Optional[GameAttempt]:
        """
        Récupère la dernière tentative d'un joueur

        Args:
            db: Session de base de données
            game_id: ID de la partie
            player_id: ID du joueur

        Returns:
            La dernière tentative ou None
        """
        query = select(GameAttempt).where(
            and_(
                GameAttempt.game_id == game_id,
                GameAttempt.player_id == player_id
            )
        ).order_by(desc(GameAttempt.attempt_number)).limit(1)

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
        return result.scalar()