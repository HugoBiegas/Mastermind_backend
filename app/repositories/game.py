"""
Repository pour la gestion des jeux
Opérations CRUD et requêtes spécialisées pour les parties et tentatives
CORRECTION: Noms de champs synchronisés avec la BDD
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, select, or_, case, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.game import Game, GameParticipation, GameAttempt, GameStatus, GameType, GameMode, ParticipationStatus
from app.schemas.game import GameCreate, GameUpdate, GameSearch
from .base import BaseRepository
from ..api.auth import logger


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

    async def sync_participation_status(self, db: AsyncSession, game_id: UUID) -> int:
        """
        Synchronise les statuts des participations avec l'état de la partie
        AMÉLIORATION: Ajout de logs et meilleure gestion d'erreurs

        Args:
            db: Session de base de données
            game_id: ID de la partie

        Returns:
            Nombre de participations mises à jour
        """
        try:
            # Récupérer la partie
            game_query = select(Game).where(Game.id == game_id)
            game_result = await db.execute(game_query)
            game = game_result.scalar_one_or_none()

            if not game:
                logger.warning(f"Tentative de synchronisation sur une partie inexistante: {game_id}")
                return 0

            # Récupérer toutes les participations de cette partie
            participations_query = select(GameParticipation).where(
                GameParticipation.game_id == game_id
            )
            participations_result = await db.execute(participations_query)
            participations = participations_result.scalars().all()

            updated_count = 0
            current_time = datetime.now(timezone.utc)

            for participation in participations:
                old_status = participation.status
                updated = False

                # Si la partie est terminée, marquer les participations actives comme terminées
                if game.is_finished and participation.status in [
                    ParticipationStatus.WAITING,
                    ParticipationStatus.READY,
                    ParticipationStatus.ACTIVE
                ]:
                    participation.status = ParticipationStatus.FINISHED
                    if not participation.finished_at:
                        participation.finished_at = current_time
                    updated = True

                    logger.info(f"Participation {participation.id} mise à jour: {old_status} → FINISHED")

                # Si la partie est active, marquer les participations en attente comme actives
                elif game.status == GameStatus.ACTIVE and participation.status == ParticipationStatus.WAITING:
                    participation.status = ParticipationStatus.ACTIVE
                    updated = True

                    logger.info(f"Participation {participation.id} mise à jour: {old_status} → ACTIVE")

                if updated:
                    updated_count += 1

            if updated_count > 0:
                await db.commit()
                logger.info(
                    f"Synchronisation terminée pour la partie {game_id}: {updated_count} participations mises à jour")
            else:
                logger.debug(f"Aucune synchronisation nécessaire pour la partie {game_id}")

            return updated_count

        except Exception as e:
            await db.rollback()
            logger.error(f"Erreur lors de la synchronisation des participations pour la partie {game_id}: {str(e)}")
            raise

    async def sync_all_games_participation_status(self, db: AsyncSession) -> Dict[str, int]:
        """
        Synchronise les statuts de toutes les parties (utile pour les tâches de maintenance)

        Returns:
            Statistiques de synchronisation
        """
        try:
            # Récupérer toutes les parties non terminées
            games_query = select(Game).where(
                Game.status.in_([
                    GameStatus.WAITING,
                    GameStatus.STARTING,
                    GameStatus.ACTIVE,
                    GameStatus.PAUSED
                ])
            )
            games_result = await db.execute(games_query)
            games = games_result.scalars().all()

            total_games = len(games)
            total_updated = 0
            games_with_updates = 0

            for game in games:
                updated_count = await self.sync_participation_status(db, game.id)
                total_updated += updated_count
                if updated_count > 0:
                    games_with_updates += 1

            stats = {
                "total_games_checked": total_games,
                "games_with_updates": games_with_updates,
                "total_participations_updated": total_updated
            }

            logger.info(f"Synchronisation globale terminée: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Erreur lors de la synchronisation globale: {str(e)}")
            raise

    async def get_inconsistent_games(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        Détecte les parties avec des statuts incohérents

        Returns:
            Liste des parties avec problèmes de cohérence
        """
        try:
            # Requête pour détecter les incohérences
            inconsistent_query = """
             SELECT DISTINCT 
                 g.id as game_id,
                 g.room_code,
                 g.status as game_status,
                 g.finished_at,
                 COUNT(gp.id) as total_participants,
                 COUNT(CASE WHEN gp.status IN ('waiting', 'ready', 'active') THEN 1 END) as active_participants,
                 COUNT(CASE WHEN gp.status = 'finished' THEN 1 END) as finished_participants,
                 ARRAY_AGG(DISTINCT gp.status) as participant_statuses
             FROM games g
             LEFT JOIN game_participations gp ON g.id = gp.game_id
             WHERE g.status IN ('finished', 'cancelled', 'aborted')
             GROUP BY g.id, g.room_code, g.status, g.finished_at
             HAVING COUNT(CASE WHEN gp.status IN ('waiting', 'ready', 'active') THEN 1 END) > 0
             """

            result = await db.execute(text(inconsistent_query))
            inconsistent_games = []

            for row in result:
                inconsistent_games.append({
                    "game_id": str(row.game_id),
                    "room_code": row.room_code,
                    "game_status": row.game_status,
                    "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                    "total_participants": row.total_participants,
                    "active_participants": row.active_participants,
                    "finished_participants": row.finished_participants,
                    "participant_statuses": row.participant_statuses,
                    "issue": "Partie terminée avec des joueurs encore actifs"
                })

            logger.info(f"Détection d'incohérences: {len(inconsistent_games)} parties problématiques trouvées")
            return inconsistent_games

        except Exception as e:
            logger.error(f"Erreur lors de la détection d'incohérences: {str(e)}")
            raise

    async def fix_inconsistent_game(self, db: AsyncSession, game_id: UUID) -> bool:
        """
        Corrige les incohérences d'une partie spécifique

        Args:
            db: Session de base de données
            game_id: ID de la partie à corriger

        Returns:
            True si des corrections ont été apportées
        """
        try:
            updated_count = await self.sync_participation_status(db, game_id)

            if updated_count > 0:
                logger.info(f"Partie {game_id} corrigée: {updated_count} participations mises à jour")
                return True
            else:
                logger.debug(f"Partie {game_id}: aucune correction nécessaire")
                return False

        except Exception as e:
            logger.error(f"Erreur lors de la correction de la partie {game_id}: {str(e)}")
            raise

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
        Récupère les participations actives d'un utilisateur avec les détails du jeu
        CORRECTION: player_id (pas user_id)

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur

        Returns:
            Liste des participations actives avec les détails des parties
        """
        query = (
            select(GameParticipation)
            .options(
                selectinload(GameParticipation.game),  # Charge les détails de la partie
                selectinload(GameParticipation.player)  # Charge les détails du joueur
            )
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
            .order_by(GameParticipation.joined_at.desc())  # Plus récent en premier
        )

        result = await db.execute(query)
        return list(result.scalars().all())


    async def get_user_participation_history(
            self,
            db: AsyncSession,
            user_id: UUID,
            limit: int = 10,
            include_active: bool = True
    ) -> List[GameParticipation]:
        """
        Récupère l'historique des participations d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur
            limit: Nombre maximum de participations à retourner
            include_active: Inclure les participations actives

        Returns:
            Liste des participations ordonnées par date
        """
        query = (
            select(GameParticipation)
            .options(selectinload(GameParticipation.game))
            .where(GameParticipation.player_id == user_id)
        )

        if not include_active:
            query = query.where(
                GameParticipation.status.in_([
                    ParticipationStatus.FINISHED,
                    ParticipationStatus.ELIMINATED,
                    ParticipationStatus.DISCONNECTED
                ])
            )

        query = query.order_by(GameParticipation.joined_at.desc()).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())


    async def cleanup_stale_participations(
            self,
            db: AsyncSession,
            hours_threshold: int = 24
    ) -> int:
        """
        Nettoie les participations en attente depuis trop longtemps

        Args:
            db: Session de base de données
            hours_threshold: Seuil en heures pour considérer une participation comme périmée

        Returns:
            Nombre de participations nettoyées
        """
        from datetime import timedelta

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)

        # Marquer comme déconnectées les participations en attente depuis trop longtemps
        query = (
            select(GameParticipation)
            .where(
                and_(
                    GameParticipation.status == ParticipationStatus.WAITING,
                    GameParticipation.joined_at < cutoff_time
                )
            )
        )

        result = await db.execute(query)
        stale_participations = result.scalars().all()

        count = 0
        current_time = datetime.now(timezone.utc)

        for participation in stale_participations:
            participation.status = ParticipationStatus.DISCONNECTED
            participation.left_at = current_time
            count += 1

        if count > 0:
            await db.commit()

        return count

    async def get_user_participation_stats(
            self,
            db: AsyncSession,
            user_id: UUID
    ) -> Dict[str, Any]:
        """
        Récupère les statistiques de participation d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur

        Returns:
            Dictionnaire avec les statistiques
        """
        # Requête pour les statistiques générales
        stats_query = select(
            func.count(GameParticipation.id).label('total_games'),
            func.count(case((GameParticipation.status == ParticipationStatus.FINISHED, 1))).label('finished_games'),
            func.count(case((GameParticipation.is_winner == True, 1))).label('wins'),
            func.avg(GameParticipation.score).label('avg_score'),
            func.max(GameParticipation.score).label('max_score'),
            func.sum(GameParticipation.attempts_made).label('total_attempts')
        ).where(GameParticipation.player_id == user_id)

        result = await db.execute(stats_query)
        stats = result.first()

        # Calcul du taux de victoire
        win_rate = 0.0
        if stats.finished_games and stats.finished_games > 0:
            win_rate = (stats.wins or 0) / stats.finished_games

        return {
            'total_games': stats.total_games or 0,
            'finished_games': stats.finished_games or 0,
            'wins': stats.wins or 0,
            'win_rate': round(win_rate * 100, 2),  # En pourcentage
            'average_score': round(float(stats.avg_score or 0), 2),
            'max_score': stats.max_score or 0,
            'total_attempts': stats.total_attempts or 0
        }

    async def check_participation_conflicts(
            self,
            db: AsyncSession,
            user_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Vérifie s'il y a des conflits dans les participations d'un utilisateur
        (ex: plusieurs participations actives, participations dans des parties terminées, etc.)

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur

        Returns:
            Liste des conflits détectés
        """
        conflicts = []

        # Vérifier les participations multiples actives
        active_participations = await self.get_user_active_participations(db, user_id)

        if len(active_participations) > 1:
            conflicts.append({
                'type': 'multiple_active_participations',
                'description': f'Utilisateur dans {len(active_participations)} parties actives simultanément',
                'participations': [
                    {
                        'game_id': str(p.game_id),
                        'room_code': p.game.room_code if p.game else 'N/A',
                        'status': p.status
                    }
                    for p in active_participations
                ]
            })

        # Vérifier les participations dans des parties terminées mais marquées comme actives
        for participation in active_participations:
            if participation.game and participation.game.is_finished:
                conflicts.append({
                    'type': 'active_in_finished_game',
                    'description': f'Participation active dans une partie terminée',
                    'game_id': str(participation.game_id),
                    'room_code': participation.game.room_code,
                    'game_status': participation.game.status,
                    'participation_status': participation.status
                })

        return conflicts

    # Nouvelle méthode pour forcer la synchronisation du statut
    async def sync_participation_status_with_game(
            self,
            db: AsyncSession,
            game_id: UUID
    ) -> int:
        """
        Synchronise le statut des participations avec le statut de la partie

        Args:
            db: Session de base de données
            game_id: ID de la partie

        Returns:
            Nombre de participations mises à jour
        """
        # Récupérer la partie
        game_query = select(Game).where(Game.id == game_id)
        game_result = await db.execute(game_query)
        game = game_result.scalar_one_or_none()

        if not game:
            return 0

        # Récupérer toutes les participations de cette partie
        participations_query = select(GameParticipation).where(
            GameParticipation.game_id == game_id
        )
        participations_result = await db.execute(participations_query)
        participations = participations_result.scalars().all()

        updated_count = 0
        current_time = datetime.now(timezone.utc)

        for participation in participations:
            updated = False

            # Si la partie est terminée, marquer les participations actives comme terminées
            if game.is_finished and participation.status in [
                ParticipationStatus.WAITING,
                ParticipationStatus.READY,
                ParticipationStatus.ACTIVE
            ]:
                participation.status = ParticipationStatus.FINISHED
                if not participation.finished_at:
                    participation.finished_at = current_time
                updated = True

            # Si la partie est active, marquer les participations en attente comme actives
            elif game.status == GameStatus.ACTIVE and participation.status == ParticipationStatus.WAITING:
                participation.status = ParticipationStatus.ACTIVE
                updated = True

            if updated:
                updated_count += 1

        if updated_count > 0:
            await db.commit()

        return updated_count

    async def check_user_can_join_new_game(
            self,
            db: AsyncSession,
            user_id: UUID,
            exclude_game_id: Optional[UUID] = None
    ) -> bool:
        """
        Vérifie si un utilisateur peut rejoindre une nouvelle partie
        (c'est-à-dire qu'il n'est pas déjà dans une partie active)

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur
            exclude_game_id: ID de partie à exclure de la vérification (optionnel)

        Returns:
            True si l'utilisateur peut rejoindre une nouvelle partie
        """
        query = (
            select(func.count(GameParticipation.id))
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

        # Exclure une partie spécifique si nécessaire (utile pour la reconnexion)
        if exclude_game_id:
            query = query.where(GameParticipation.game_id != exclude_game_id)

        result = await db.execute(query)
        active_count = result.scalar() or 0

        return active_count == 0


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