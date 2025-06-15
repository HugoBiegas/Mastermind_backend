"""
Repository pour la gestion des utilisateurs
Couche d'accès aux données avec SQLAlchemy 2.0.41 et Pydantic v2
"""
from typing import List, Optional, Dict, Any, Sequence, Union
from uuid import UUID
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc, text
from sqlalchemy.orm import selectinload, joinedload

from app.models.user import User
from app.repositories.base import BaseRepositoryWithMixins
from app.core.database import PaginationParams, PaginationResult
from app.schemas.user import UserCreate, UserUpdate
from app.utils.exceptions import EntityNotFoundError, ValidationError, DatabaseError


class UserRepository(BaseRepositoryWithMixins[User, UserCreate, UserUpdate]):
    """Repository pour les opérations CRUD sur les utilisateurs"""

    def __init__(self):
        super().__init__(User)

    # === MÉTHODES DE RÉCUPÉRATION SPÉCIFIQUES ===

    async def get_by_username(
        self,
        db: AsyncSession,
        username: str,
        *,
        case_sensitive: bool = False
    ) -> Optional[User]:
        """
        Récupère un utilisateur par son nom d'utilisateur

        Args:
            db: Session de base de données
            username: Nom d'utilisateur
            case_sensitive: Recherche sensible à la casse

        Returns:
            Utilisateur trouvé ou None
        """
        try:
            query = select(User)

            if case_sensitive:
                query = query.where(User.username == username)
            else:
                query = query.where(User.username.ilike(username.lower()))

            result = await db.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            raise DatabaseError(f"Erreur lors de la récupération par username: {str(e)}")

    async def get_by_email(
        self,
        db: AsyncSession,
        email: str
    ) -> Optional[User]:
        """
        Récupère un utilisateur par son adresse email

        Args:
            db: Session de base de données
            email: Adresse email

        Returns:
            Utilisateur trouvé ou None
        """
        try:
            query = select(User).where(User.email.ilike(email.lower()))
            result = await db.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            raise DatabaseError(f"Erreur lors de la récupération par email: {str(e)}")

    async def get_by_username_or_email(
        self,
        db: AsyncSession,
        identifier: str
    ) -> Optional[User]:
        """
        Récupère un utilisateur par nom d'utilisateur ou email

        Args:
            db: Session de base de données
            identifier: Nom d'utilisateur ou email

        Returns:
            Utilisateur trouvé ou None
        """
        try:
            query = select(User).where(
                or_(
                    User.username.ilike(identifier.lower()),
                    User.email.ilike(identifier.lower())
                )
            )
            result = await db.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            raise DatabaseError(f"Erreur lors de la récupération par identifiant: {str(e)}")

    async def get_active_users(
        self,
        db: AsyncSession,
        *,
        limit: int = 100,
        pagination: Optional[PaginationParams] = None
    ) -> Union[Sequence[User], PaginationResult]:
        """
        Récupère les utilisateurs actifs

        Args:
            db: Session de base de données
            limit: Nombre maximum d'utilisateurs (si pas de pagination)
            pagination: Paramètres de pagination

        Returns:
            Liste d'utilisateurs ou résultat paginé
        """
        filters = {"is_active": True}

        if pagination:
            return await self.get_multi_paginated(
                db, pagination, filters=filters, order_by="last_login"
            )
        else:
            return await self.get_multi(
                db, limit=limit, filters=filters, order_by="last_login"
            )

    async def get_verified_users(
        self,
        db: AsyncSession,
        pagination: PaginationParams
    ) -> PaginationResult:
        """
        Récupère les utilisateurs vérifiés

        Args:
            db: Session de base de données
            pagination: Paramètres de pagination

        Returns:
            Résultat paginé
        """
        filters = {"is_verified": True, "is_active": True}
        return await self.get_multi_paginated(
            db, pagination, filters=filters, order_by="created_at"
        )

    async def get_superusers(
        self,
        db: AsyncSession
    ) -> Sequence[User]:
        """
        Récupère tous les super-utilisateurs

        Args:
            db: Session de base de données

        Returns:
            Liste des super-utilisateurs
        """
        filters = {"is_superuser": True, "is_active": True}
        return await self.get_multi(db, filters=filters, order_by="created_at")

    # === MÉTHODES DE RECHERCHE ===

    async def search_users(
        self,
        db: AsyncSession,
        *,
        query: str,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None,
        include_inactive: bool = False
    ) -> PaginationResult:
        """
        Recherche d'utilisateurs par terme

        Args:
            db: Session de base de données
            query: Terme de recherche
            pagination: Paramètres de pagination
            filters: Filtres supplémentaires
            include_inactive: Inclure les utilisateurs inactifs

        Returns:
            Résultat paginé
        """
        search_fields = ["username", "email", "full_name"]

        # Filtres par défaut
        base_filters = {}
        if not include_inactive:
            base_filters["is_active"] = True

        # Fusion avec les filtres fournis
        if filters:
            base_filters.update(filters)

        return await self.search(
            db,
            query=query,
            search_fields=search_fields,
            pagination=pagination,
            filters=base_filters,
            order_by="username"
        )

    async def get_users_by_rank(
        self,
        db: AsyncSession,
        rank: str,
        pagination: PaginationParams
    ) -> PaginationResult:
        """
        Récupère les utilisateurs d'un rang spécifique

        Args:
            db: Session de base de données
            rank: Rang recherché
            pagination: Paramètres de pagination

        Returns:
            Résultat paginé
        """
        filters = {"rank": rank, "is_active": True}
        return await self.get_multi_paginated(
            db, pagination, filters=filters, order_by="score", order_desc=True
        )

    async def get_users_by_score_range(
        self,
        db: AsyncSession,
        min_score: Optional[int] = None,
        max_score: Optional[int] = None,
        pagination: Optional[PaginationParams] = None
    ) -> Union[Sequence[User], PaginationResult]:
        """
        Récupère les utilisateurs dans une plage de scores

        Args:
            db: Session de base de données
            min_score: Score minimum
            max_score: Score maximum
            pagination: Paramètres de pagination

        Returns:
            Liste d'utilisateurs ou résultat paginé
        """
        try:
            query = select(User).where(User.is_active == True)

            if min_score is not None:
                query = query.where(User.score >= min_score)
            if max_score is not None:
                query = query.where(User.score <= max_score)

            query = query.order_by(desc(User.score))

            if pagination:
                # Compter le total
                count_query = select(func.count(User.id)).select_from(query.subquery())
                count_result = await db.execute(count_query)
                total = count_result.scalar() or 0

                # Paginer
                query = query.offset(pagination.offset).limit(pagination.limit)
                result = await db.execute(query)
                items = result.scalars().all()

                return PaginationResult(
                    items=items,
                    total=total,
                    page=pagination.page,
                    per_page=pagination.per_page
                )
            else:
                result = await db.execute(query)
                return result.scalars().all()

        except Exception as e:
            raise DatabaseError(f"Erreur lors de la récupération par score: {str(e)}")

    # === MÉTHODES DE STATISTIQUES ===

    async def get_user_statistics(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Récupère les statistiques d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur

        Returns:
            Dictionnaire des statistiques
        """
        try:
            # Récupérer l'utilisateur avec les relations
            user = await self.get_by_id(
                db, user_id,
                eager_load=["game_participations", "game_attempts"]
            )

            if not user:
                raise EntityNotFoundError(f"Utilisateur {user_id} non trouvé")

            # Calculs de base à partir des relations
            total_games = len(user.game_participations) if hasattr(user, 'game_participations') else 0
            total_attempts = len(user.game_attempts) if hasattr(user, 'game_attempts') else 0

            # Requêtes SQL pour les statistiques avancées
            stats_query = text("""
                SELECT 
                    COUNT(DISTINCT gp.game_id) as total_games,
                    COUNT(CASE WHEN gp.status = 'won' THEN 1 END) as games_won,
                    COUNT(CASE WHEN gp.status = 'lost' THEN 1 END) as games_lost,
                    COALESCE(AVG(gp.score), 0) as average_score,
                    COALESCE(MAX(gp.score), 0) as best_score,
                    COUNT(DISTINCT ga.id) as total_attempts,
                    COUNT(CASE WHEN ga.is_winning THEN 1 END) as successful_attempts
                FROM users u
                LEFT JOIN game_participations gp ON u.id = gp.user_id
                LEFT JOIN game_attempts ga ON u.id = ga.user_id
                WHERE u.id = :user_id
                GROUP BY u.id
            """)

            result = await db.execute(stats_query, {"user_id": user_id})
            stats_row = result.fetchone()

            if not stats_row:
                # Utilisateur sans statistiques
                return {
                    "total_games": 0,
                    "games_won": 0,
                    "games_lost": 0,
                    "win_rate": 0.0,
                    "average_score": 0.0,
                    "best_score": 0,
                    "total_attempts": 0,
                    "successful_attempts": 0,
                    "success_rate": 0.0
                }

            games_won = stats_row.games_won or 0
            total_games = stats_row.total_games or 0
            successful_attempts = stats_row.successful_attempts or 0
            total_attempts = stats_row.total_attempts or 0

            return {
                "total_games": total_games,
                "games_won": games_won,
                "games_lost": stats_row.games_lost or 0,
                "win_rate": (games_won / total_games * 100) if total_games > 0 else 0.0,
                "average_score": float(stats_row.average_score or 0),
                "best_score": stats_row.best_score or 0,
                "total_attempts": total_attempts,
                "successful_attempts": successful_attempts,
                "success_rate": (successful_attempts / total_attempts * 100) if total_attempts > 0 else 0.0
            }

        except EntityNotFoundError:
            raise
        except Exception as e:
            raise DatabaseError(f"Erreur lors du calcul des statistiques: {str(e)}")

    async def get_leaderboard(
        self,
        db: AsyncSession,
        *,
        limit: int = 50,
        period: str = "all",
        metric: str = "score"
    ) -> List[Dict[str, Any]]:
        """
        Récupère le classement des utilisateurs

        Args:
            db: Session de base de données
            limit: Nombre d'entrées
            period: Période (all, month, week, day)
            metric: Métrique de classement (score, games_won, win_rate)

        Returns:
            Liste du classement
        """
        try:
            # Construction de la requête de base
            query = select(
                User.id,
                User.username,
                User.full_name,
                User.avatar_url,
                User.score,
                User.rank,
                func.row_number().over(order_by=desc(User.score)).label('position')
            ).where(User.is_active == True)

            # Filtrage par période si nécessaire
            if period != "all":
                date_filter = datetime.now(timezone.utc)
                if period == "day":
                    date_filter -= timedelta(days=1)
                elif period == "week":
                    date_filter -= timedelta(weeks=1)
                elif period == "month":
                    date_filter -= timedelta(days=30)

                query = query.where(User.updated_at >= date_filter)

            # Tri et limitation
            if metric == "score":
                query = query.order_by(desc(User.score))
            elif metric == "games_won":
                query = query.order_by(desc(User.games_won))

            query = query.limit(limit)

            result = await db.execute(query)
            rows = result.fetchall()

            return [
                {
                    "position": row.position,
                    "user_id": row.id,
                    "username": row.username,
                    "full_name": row.full_name,
                    "avatar_url": row.avatar_url,
                    "score": row.score,
                    "rank": row.rank
                }
                for row in rows
            ]

        except Exception as e:
            raise DatabaseError(f"Erreur lors de la récupération du classement: {str(e)}")

    # === MÉTHODES DE MISE À JOUR SPÉCIFIQUES ===

    async def update_last_login(
        self,
        db: AsyncSession,
        user_id: UUID,
        login_time: Optional[datetime] = None
    ) -> bool:
        """
        Met à jour la dernière connexion d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur
            login_time: Heure de connexion (maintenant par défaut)

        Returns:
            True si mis à jour avec succès
        """
        try:
            if login_time is None:
                login_time = datetime.now(timezone.utc)

            query = update(User).where(User.id == user_id).values(
                last_login=login_time,
                updated_at=datetime.now(timezone.utc)
            )

            result = await db.execute(query)
            await db.commit()

            return result.rowcount > 0

        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Erreur lors de la mise à jour de la dernière connexion: {str(e)}")

    async def update_score(
        self,
        db: AsyncSession,
        user_id: UUID,
        score_delta: int
    ) -> User:
        """
        Met à jour le score d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur
            score_delta: Variation du score

        Returns:
            Utilisateur mis à jour

        Raises:
            EntityNotFoundError: Si l'utilisateur n'existe pas
        """
        try:
            user = await self.get_by_id(db, user_id)
            if not user:
                raise EntityNotFoundError(f"Utilisateur {user_id} non trouvé")

            new_score = max(0, user.score + score_delta)

            query = update(User).where(User.id == user_id).values(
                score=new_score,
                updated_at=datetime.now(timezone.utc)
            )

            await db.execute(query)
            await db.commit()
            await db.refresh(user)

            return user

        except EntityNotFoundError:
            raise
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Erreur lors de la mise à jour du score: {str(e)}")

    async def update_preferences(
        self,
        db: AsyncSession,
        user_id: UUID,
        preferences: Dict[str, Any]
    ) -> User:
        """
        Met à jour les préférences d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur
            preferences: Nouvelles préférences

        Returns:
            Utilisateur mis à jour
        """
        try:
            user = await self.get_by_id(db, user_id)
            if not user:
                raise EntityNotFoundError(f"Utilisateur {user_id} non trouvé")

            # Fusion des préférences existantes
            current_prefs = user.preferences or {}
            updated_prefs = {**current_prefs, **preferences}

            query = update(User).where(User.id == user_id).values(
                preferences=updated_prefs,
                updated_at=datetime.now(timezone.utc)
            )

            await db.execute(query)
            await db.commit()
            await db.refresh(user)

            return user

        except EntityNotFoundError:
            raise
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"Erreur lors de la mise à jour des préférences: {str(e)}")

    # === MÉTHODES DE VALIDATION ===

    async def is_username_available(
        self,
        db: AsyncSession,
        username: str,
        exclude_user_id: Optional[UUID] = None
    ) -> bool:
        """
        Vérifie si un nom d'utilisateur est disponible

        Args:
            db: Session de base de données
            username: Nom d'utilisateur à vérifier
            exclude_user_id: ID d'utilisateur à exclure (pour les mises à jour)

        Returns:
            True si disponible
        """
        try:
            query = select(User).where(User.username.ilike(username.lower()))

            if exclude_user_id:
                query = query.where(User.id != exclude_user_id)

            result = await db.execute(query)
            existing_user = result.scalar_one_or_none()

            return existing_user is None

        except Exception as e:
            raise DatabaseError(f"Erreur lors de la vérification du nom d'utilisateur: {str(e)}")

    async def is_email_available(
        self,
        db: AsyncSession,
        email: str,
        exclude_user_id: Optional[UUID] = None
    ) -> bool:
        """
        Vérifie si une adresse email est disponible

        Args:
            db: Session de base de données
            email: Email à vérifier
            exclude_user_id: ID d'utilisateur à exclure

        Returns:
            True si disponible
        """
        try:
            query = select(User).where(User.email.ilike(email.lower()))

            if exclude_user_id:
                query = query.where(User.id != exclude_user_id)

            result = await db.execute(query)
            existing_user = result.scalar_one_or_none()

            return existing_user is None

        except Exception as e:
            raise DatabaseError(f"Erreur lors de la vérification de l'email: {str(e)}")

    # === MÉTHODES D'ADMINISTRATION ===

    async def bulk_activate(
        self,
        db: AsyncSession,
        user_ids: List[UUID],
        activated_by: UUID
    ) -> int:
        """
        Active plusieurs utilisateurs en lot

        Args:
            db: Session de base de données
            user_ids: Liste des IDs d'utilisateurs
            activated_by: ID de l'administrateur

        Returns:
            Nombre d'utilisateurs activés
        """
        return await self.bulk_update(
            db,
            filters={"id": user_ids},
            update_data={
                "is_active": True,
                "updated_by": activated_by,
                "updated_at": datetime.now(timezone.utc)
            }
        )

    async def bulk_deactivate(
        self,
        db: AsyncSession,
        user_ids: List[UUID],
        deactivated_by: UUID
    ) -> int:
        """
        Désactive plusieurs utilisateurs en lot

        Args:
            db: Session de base de données
            user_ids: Liste des IDs d'utilisateurs
            deactivated_by: ID de l'administrateur

        Returns:
            Nombre d'utilisateurs désactivés
        """
        return await self.bulk_update(
            db,
            filters={"id": user_ids},
            update_data={
                "is_active": False,
                "updated_by": deactivated_by,
                "updated_at": datetime.now(timezone.utc)
            }
        )

    async def get_inactive_users(
        self,
        db: AsyncSession,
        days_inactive: int = 30,
        pagination: Optional[PaginationParams] = None
    ) -> Union[Sequence[User], PaginationResult]:
        """
        Récupère les utilisateurs inactifs depuis X jours

        Args:
            db: Session de base de données
            days_inactive: Nombre de jours d'inactivité
            pagination: Paramètres de pagination

        Returns:
            Liste d'utilisateurs ou résultat paginé
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_inactive)

        filters = {
            "last_login": {"lt": cutoff_date},
            "is_active": True
        }

        if pagination:
            return await self.get_multi_paginated(
                db, pagination, filters=filters, order_by="last_login"
            )
        else:
            return await self.get_multi(db, filters=filters, order_by="last_login")


# === INSTANCE GLOBALE ===

user_repository = UserRepository()