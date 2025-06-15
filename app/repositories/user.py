"""
Repository pour la gestion des utilisateurs
Couche d'accès aux données avec SQLAlchemy 2.0.41
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload, joinedload

from app.models.user import User
from app.core.database import Base
from app.utils.exceptions import EntityNotFoundError, ValidationError


class UserRepository:
    """Repository pour les opérations CRUD sur les utilisateurs"""

    async def create(self, db: AsyncSession, user_data: Dict[str, Any]) -> User:
        """
        Crée un nouvel utilisateur

        Args:
            db: Session de base de données
            user_data: Données de l'utilisateur

        Returns:
            Utilisateur créé

        Raises:
            ValidationError: Si les données sont invalides
        """
        try:
            user = User(**user_data)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return user
        except Exception as e:
            await db.rollback()
            raise ValidationError(f"Erreur lors de la création de l'utilisateur: {str(e)}")

    async def get_by_id(self, db: AsyncSession, user_id: UUID) -> Optional[User]:
        """
        Récupère un utilisateur par son ID

        Args:
            db: Session de base de données
            user_id: UUID de l'utilisateur

        Returns:
            Utilisateur trouvé ou None
        """
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        """
        Récupère un utilisateur par son nom d'utilisateur

        Args:
            db: Session de base de données
            username: Nom d'utilisateur

        Returns:
            Utilisateur trouvé ou None
        """
        stmt = select(User).where(User.username == username.lower())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """
        Récupère un utilisateur par son email

        Args:
            db: Session de base de données
            email: Adresse email

        Returns:
            Utilisateur trouvé ou None
        """
        stmt = select(User).where(User.email == email.lower())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_relations(
        self,
        db: AsyncSession,
        user_id: UUID,
        load_games: bool = False,
        load_participations: bool = False
    ) -> Optional[User]:
        """
        Récupère un utilisateur avec ses relations

        Args:
            db: Session de base de données
            user_id: UUID de l'utilisateur
            load_games: Charger les jeux créés
            load_participations: Charger les participations

        Returns:
            Utilisateur avec relations chargées
        """
        stmt = select(User).where(User.id == user_id)

        if load_games:
            stmt = stmt.options(selectinload(User.created_games))

        if load_participations:
            stmt = stmt.options(selectinload(User.game_participations))

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        db: AsyncSession,
        user_id: UUID,
        update_data: Dict[str, Any]
    ) -> Optional[User]:
        """
        Met à jour un utilisateur

        Args:
            db: Session de base de données
            user_id: UUID de l'utilisateur
            update_data: Données à mettre à jour

        Returns:
            Utilisateur mis à jour

        Raises:
            EntityNotFoundError: Si l'utilisateur n'existe pas
        """
        # Ajouter la date de mise à jour
        update_data["updated_at"] = datetime.now(timezone.utc)

        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(**update_data)
            .returning(User)
        )

        result = await db.execute(stmt)
        updated_user = result.scalar_one_or_none()

        if not updated_user:
            raise EntityNotFoundError(
                "Utilisateur non trouvé",
                entity_type="User",
                entity_id=user_id
            )

        await db.commit()
        await db.refresh(updated_user)
        return updated_user

    async def delete(self, db: AsyncSession, user_id: UUID) -> bool:
        """
        Supprime un utilisateur

        Args:
            db: Session de base de données
            user_id: UUID de l'utilisateur

        Returns:
            True si supprimé, False si non trouvé
        """
        stmt = delete(User).where(User.id == user_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    async def get_multi(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True,
        verified_only: bool = False
    ) -> List[User]:
        """
        Récupère plusieurs utilisateurs avec pagination

        Args:
            db: Session de base de données
            skip: Nombre d'éléments à ignorer
            limit: Nombre maximum d'éléments
            active_only: Seulement les utilisateurs actifs
            verified_only: Seulement les utilisateurs vérifiés

        Returns:
            Liste des utilisateurs
        """
        stmt = select(User)

        if active_only:
            stmt = stmt.where(User.is_active == True)

        if verified_only:
            stmt = stmt.where(User.is_verified == True)

        stmt = stmt.offset(skip).limit(limit).order_by(desc(User.created_at))

        result = await db.execute(stmt)
        return result.scalars().all()

    async def search_users(
        self,
        db: AsyncSession,
        query: str,
        skip: int = 0,
        limit: int = 20,
        active_only: bool = True
    ) -> List[User]:
        """
        Recherche des utilisateurs par nom d'utilisateur ou nom complet

        Args:
            db: Session de base de données
            query: Terme de recherche
            skip: Nombre d'éléments à ignorer
            limit: Nombre maximum d'éléments
            active_only: Seulement les utilisateurs actifs

        Returns:
            Liste des utilisateurs correspondants
        """
        search_term = f"%{query.lower()}%"

        stmt = select(User).where(
            or_(
                User.username.ilike(search_term),
                User.full_name.ilike(search_term)
            )
        )

        if active_only:
            stmt = stmt.where(User.is_active == True)

        stmt = stmt.offset(skip).limit(limit).order_by(desc(User.total_score))

        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_leaderboard(
        self,
        db: AsyncSession,
        limit: int = 10,
        order_by: str = "total_score"
    ) -> List[User]:
        """
        Récupère le classement des utilisateurs

        Args:
            db: Session de base de données
            limit: Nombre d'utilisateurs dans le classement
            order_by: Champ de tri (total_score, quantum_points, win_rate)

        Returns:
            Liste des meilleurs utilisateurs
        """
        order_field = getattr(User, order_by, User.total_score)

        stmt = (
            select(User)
            .where(and_(User.is_active == True, User.total_games > 0))
            .order_by(desc(order_field))
            .limit(limit)
        )

        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_user_stats(self, db: AsyncSession, user_id: UUID) -> Dict[str, Any]:
        """
        Récupère les statistiques détaillées d'un utilisateur

        Args:
            db: Session de base de données
            user_id: UUID de l'utilisateur

        Returns:
            Statistiques de l'utilisateur

        Raises:
            EntityNotFoundError: Si l'utilisateur n'existe pas
        """
        user = await self.get_by_id(db, user_id)
        if not user:
            raise EntityNotFoundError(
                "Utilisateur non trouvé",
                entity_type="User",
                entity_id=user_id
            )

        # Statistiques de base
        stats = {
            "user_id": str(user.id),
            "username": user.username,
            "total_games": user.total_games,
            "games_won": user.games_won,
            "win_rate": user.win_rate,
            "total_score": user.total_score,
            "best_score": user.best_score,
            "average_score": user.average_score,
            "quantum_points": user.quantum_points,
            "rank": user.rank,
            "created_at": user.created_at,
            "last_login": user.last_login
        }

        # TODO: Ajouter des statistiques plus détaillées
        # - Temps de jeu moyen
        # - Types de jeux préférés
        # - Progression dans le temps
        # - Comparaison avec la moyenne

        return stats

    async def update_user_stats(
        self,
        db: AsyncSession,
        user_id: UUID,
        game_won: bool,
        score: int,
        quantum_used: bool = False
    ) -> User:
        """
        Met à jour les statistiques d'un utilisateur après une partie

        Args:
            db: Session de base de données
            user_id: UUID de l'utilisateur
            game_won: True si la partie a été gagnée
            score: Score obtenu
            quantum_used: True si des fonctionnalités quantiques ont été utilisées

        Returns:
            Utilisateur mis à jour

        Raises:
            EntityNotFoundError: Si l'utilisateur n'existe pas
        """
        user = await self.get_by_id(db, user_id)
        if not user:
            raise EntityNotFoundError(
                "Utilisateur non trouvé",
                entity_type="User",
                entity_id=user_id
            )

        # Mise à jour des statistiques
        user.update_stats(game_won, score, quantum_used)

        await db.commit()
        await db.refresh(user)
        return user

    async def get_users_by_ids(
        self,
        db: AsyncSession,
        user_ids: List[UUID]
    ) -> List[User]:
        """
        Récupère plusieurs utilisateurs par leurs IDs

        Args:
            db: Session de base de données
            user_ids: Liste des UUIDs

        Returns:
            Liste des utilisateurs trouvés
        """
        if not user_ids:
            return []

        stmt = select(User).where(User.id.in_(user_ids))
        result = await db.execute(stmt)
        return result.scalars().all()

    async def count_total_users(
        self,
        db: AsyncSession,
        active_only: bool = False,
        verified_only: bool = False
    ) -> int:
        """
        Compte le nombre total d'utilisateurs

        Args:
            db: Session de base de données
            active_only: Compter seulement les utilisateurs actifs
            verified_only: Compter seulement les utilisateurs vérifiés

        Returns:
            Nombre d'utilisateurs
        """
        stmt = select(func.count(User.id))

        if active_only:
            stmt = stmt.where(User.is_active == True)

        if verified_only:
            stmt = stmt.where(User.is_verified == True)

        result = await db.execute(stmt)
        return result.scalar()

    async def get_recent_users(
        self,
        db: AsyncSession,
        days: int = 7,
        limit: int = 50
    ) -> List[User]:
        """
        Récupère les utilisateurs récemment inscrits

        Args:
            db: Session de base de données
            days: Nombre de jours en arrière
            limit: Nombre maximum d'utilisateurs

        Returns:
            Liste des utilisateurs récents
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        stmt = (
            select(User)
            .where(User.created_at >= cutoff_date)
            .order_by(desc(User.created_at))
            .limit(limit)
        )

        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_inactive_users(
        self,
        db: AsyncSession,
        days_inactive: int = 30,
        limit: int = 100
    ) -> List[User]:
        """
        Récupère les utilisateurs inactifs

        Args:
            db: Session de base de données
            days_inactive: Nombre de jours d'inactivité
            limit: Nombre maximum d'utilisateurs

        Returns:
            Liste des utilisateurs inactifs
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_inactive)

        stmt = (
            select(User)
            .where(
                or_(
                    User.last_login < cutoff_date,
                    User.last_login.is_(None)
                )
            )
            .where(User.is_active == True)
            .order_by(asc(User.last_login.nulls_first()))
            .limit(limit)
        )

        result = await db.execute(stmt)
        return result.scalars().all()

    async def update_last_login(
        self,
        db: AsyncSession,
        user_id: UUID,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Met à jour la dernière connexion d'un utilisateur

        Args:
            db: Session de base de données
            user_id: UUID de l'utilisateur
            ip_address: Adresse IP (optionnelle)
        """
        update_data = {
            "last_login": datetime.now(timezone.utc),
            "login_attempts": 0,
            "locked_until": None
        }

        if ip_address:
            update_data["last_ip_address"] = ip_address

        stmt = update(User).where(User.id == user_id).values(**update_data)
        await db.execute(stmt)
        await db.commit()

    async def increment_login_attempts(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> User:
        """
        Incrémente les tentatives de connexion d'un utilisateur

        Args:
            db: Session de base de données
            user_id: UUID de l'utilisateur

        Returns:
            Utilisateur mis à jour
        """
        user = await self.get_by_id(db, user_id)
        if not user:
            raise EntityNotFoundError(
                "Utilisateur non trouvé",
                entity_type="User",
                entity_id=user_id
            )

        user.increment_login_attempts()
        await db.commit()
        await db.refresh(user)
        return user

    async def verify_user_email(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> User:
        """
        Marque l'email d'un utilisateur comme vérifié

        Args:
            db: Session de base de données
            user_id: UUID de l'utilisateur

        Returns:
            Utilisateur mis à jour

        Raises:
            EntityNotFoundError: Si l'utilisateur n'existe pas
        """
        user = await self.get_by_id(db, user_id)
        if not user:
            raise EntityNotFoundError(
                "Utilisateur non trouvé",
                entity_type="User",
                entity_id=user_id
            )

        user.verify_email()
        await db.commit()
        await db.refresh(user)
        return user

    async def batch_update_users(
        self,
        db: AsyncSession,
        user_ids: List[UUID],
        update_data: Dict[str, Any]
    ) -> int:
        """
        Met à jour plusieurs utilisateurs en une fois

        Args:
            db: Session de base de données
            user_ids: Liste des UUIDs à mettre à jour
            update_data: Données à mettre à jour

        Returns:
            Nombre d'utilisateurs mis à jour
        """
        if not user_ids:
            return 0

        update_data["updated_at"] = datetime.now(timezone.utc)

        stmt = (
            update(User)
            .where(User.id.in_(user_ids))
            .values(**update_data)
        )

        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount

    async def get_users_statistics(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Récupère les statistiques globales des utilisateurs

        Args:
            db: Session de base de données

        Returns:
            Statistiques globales
        """
        # Comptages de base
        total_users = await self.count_total_users(db)
        active_users = await self.count_total_users(db, active_only=True)
        verified_users = await self.count_total_users(db, verified_only=True)

        # Utilisateurs récents (7 derniers jours)
        recent_users = await self.get_recent_users(db, days=7)

        # Statistiques de jeu
        game_stats_stmt = select(
            func.avg(User.total_games).label("avg_games"),
            func.avg(User.total_score).label("avg_score"),
            func.avg(User.quantum_points).label("avg_quantum_points"),
            func.max(User.best_score).label("max_score")
        ).where(User.is_active == True)

        result = await db.execute(game_stats_stmt)
        game_stats = result.first()

        return {
            "total_users": total_users,
            "active_users": active_users,
            "verified_users": verified_users,
            "recent_registrations": len(recent_users),
            "average_games_per_user": float(game_stats.avg_games or 0),
            "average_score_per_user": float(game_stats.avg_score or 0),
            "average_quantum_points": float(game_stats.avg_quantum_points or 0),
            "highest_score": int(game_stats.max_score or 0),
            "verification_rate": (verified_users / total_users * 100) if total_users > 0 else 0,
            "activity_rate": (active_users / total_users * 100) if total_users > 0 else 0
        }