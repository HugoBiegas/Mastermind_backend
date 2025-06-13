"""
Repository pour la gestion des utilisateurs
Opérations CRUD et requêtes spécialisées pour les utilisateurs
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserSearch
from .base import BaseRepository


class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    """Repository pour les utilisateurs avec méthodes spécialisées"""

    def __init__(self):
        super().__init__(User)

    # === MÉTHODES DE RECHERCHE SPÉCIALISÉES ===

    async def get_by_unique_field(
            self,
            db: AsyncSession,
            field_value: str
    ) -> Optional[User]:
        """Récupère un utilisateur par username (implémentation abstraite)"""
        return await self.get_by_username(db, field_value)

    async def get_by_username(
            self,
            db: AsyncSession,
            username: str,
            *,
            with_deleted: bool = False
    ) -> Optional[User]:
        """
        Récupère un utilisateur par son nom d'utilisateur

        Args:
            db: Session de base de données
            username: Nom d'utilisateur
            with_deleted: Inclure les utilisateurs supprimés

        Returns:
            L'utilisateur ou None
        """
        query = select(User).where(
            func.lower(User.username) == func.lower(username.strip())
        )

        if not with_deleted:
            query = query.where(User.is_deleted == False)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(
            self,
            db: AsyncSession,
            email: str,
            *,
            with_deleted: bool = False
    ) -> Optional[User]:
        """
        Récupère un utilisateur par son email

        Args:
            db: Session de base de données
            email: Adresse email
            with_deleted: Inclure les utilisateurs supprimés

        Returns:
            L'utilisateur ou None
        """
        query = select(User).where(
            func.lower(User.email) == func.lower(email.strip())
        )

        if not with_deleted:
            query = query.where(User.is_deleted == False)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_username_or_email(
            self,
            db: AsyncSession,
            identifier: str,
            *,
            with_deleted: bool = False
    ) -> Optional[User]:
        """
        Récupère un utilisateur par username ou email

        Args:
            db: Session de base de données
            identifier: Username ou email
            with_deleted: Inclure les utilisateurs supprimés

        Returns:
            L'utilisateur ou None
        """
        identifier = identifier.strip().lower()

        query = select(User).where(
            or_(
                func.lower(User.username) == identifier,
                func.lower(User.email) == identifier
            )
        )

        if not with_deleted:
            query = query.where(User.is_deleted == False)

        result = await db.execute(query)
        return result.scalar_one_or_none()

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
            exclude_user_id: ID utilisateur à exclure (pour les mises à jour)

        Returns:
            True si disponible
        """
        query = select(func.count(User.id)).where(
            and_(
                func.lower(User.username) == func.lower(username.strip()),
                User.is_deleted == False
            )
        )

        if exclude_user_id:
            query = query.where(User.id != exclude_user_id)

        result = await db.execute(query)
        count = result.scalar()
        return count == 0

    async def is_email_available(
            self,
            db: AsyncSession,
            email: str,
            exclude_user_id: Optional[UUID] = None
    ) -> bool:
        """
        Vérifie si un email est disponible

        Args:
            db: Session de base de données
            email: Email à vérifier
            exclude_user_id: ID utilisateur à exclure

        Returns:
            True si disponible
        """
        query = select(func.count(User.id)).where(
            and_(
                func.lower(User.email) == func.lower(email.strip()),
                User.is_deleted == False
            )
        )

        if exclude_user_id:
            query = query.where(User.id != exclude_user_id)

        result = await db.execute(query)
        count = result.scalar()
        return count == 0

    # === MÉTHODES DE STATISTIQUES ===

    async def get_user_stats(
            self,
            db: AsyncSession,
            user_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Récupère les statistiques détaillées d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur

        Returns:
            Dictionnaire des statistiques ou None
        """
        user = await self.get_by_id(db, user_id)
        if not user:
            return None

        # Calcul des statistiques avancées
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        # TODO: Ajouter les requêtes pour les statistiques de jeu
        # Une fois que les modèles Game sont en place

        return {
            'user_id': user.id,
            'username': user.username,
            'total_games': user.total_games,
            'wins': user.wins,
            'losses': user.total_games - user.wins,
            'win_rate': user.win_rate,
            'best_time': user.best_time,
            'average_time': user.average_time,
            'quantum_score': user.quantum_score,
            'games_this_week': 0,  # TODO: Calculer avec requête sur Game
            'games_this_month': 0,  # TODO: Calculer avec requête sur Game
            'account_age_days': (now - user.created_at).days,
            'last_login': user.last_login,
            'login_count': user.login_count,
            'is_verified': user.is_verified,
            'is_active': user.is_active
        }

    async def get_leaderboard(
            self,
            db: AsyncSession,
            *,
            category: str = 'quantum_score',
            limit: int = 100,
            period: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Récupère le leaderboard des utilisateurs

        Args:
            db: Session de base de données
            category: Catégorie de classement ('quantum_score', 'wins', 'win_rate')
            limit: Nombre d'utilisateurs à retourner
            period: Période ('week', 'month', 'all-time')

        Returns:
            Liste des utilisateurs classés
        """
        # Vérification de la catégorie
        valid_categories = ['quantum_score', 'wins', 'win_rate', 'total_games']
        if category not in valid_categories:
            category = 'quantum_score'

        # Construction de la requête de base
        query = select(User).where(
            and_(
                User.is_active == True,
                User.is_deleted == False,
                User.total_games >= 5  # Minimum 5 jeux pour apparaître
            )
        )

        # Tri selon la catégorie
        if category == 'quantum_score':
            query = query.order_by(desc(User.quantum_score))
        elif category == 'wins':
            query = query.order_by(desc(User.wins))
        elif category == 'win_rate':
            # Tri par taux de victoire puis par nombre de victoires
            query = query.order_by(
                desc(User.wins / func.greatest(User.total_games, 1)),
                desc(User.wins)
            )
        elif category == 'total_games':
            query = query.order_by(desc(User.total_games))

        query = query.limit(limit)

        result = await db.execute(query)
        users = result.scalars().all()

        # Formatage des résultats avec rang
        leaderboard = []
        for rank, user in enumerate(users, 1):
            leaderboard.append({
                'rank': rank,
                'user_id': user.id,
                'username': user.username,
                'score': getattr(user, category),
                'total_games': user.total_games,
                'wins': user.wins,
                'win_rate': user.win_rate,
                'quantum_score': user.quantum_score,
                'is_verified': user.is_verified
            })

        return leaderboard

    # === MÉTHODES DE RECHERCHE AVANCÉE ===

    async def search_users(
            self,
            db: AsyncSession,
            search_criteria: UserSearch
    ) -> Dict[str, Any]:
        """
        Recherche avancée d'utilisateurs

        Args:
            db: Session de base de données
            search_criteria: Critères de recherche

        Returns:
            Résultats de recherche paginés
        """
        query = select(User).where(User.is_deleted == False)

        # Filtre par texte (username ou email)
        if search_criteria.query:
            search_term = f"%{search_criteria.query.strip().lower()}%"
            query = query.where(
                or_(
                    func.lower(User.username).like(search_term),
                    func.lower(User.email).like(search_term)
                )
            )

        # Filtres spécifiques
        if search_criteria.is_active is not None:
            query = query.where(User.is_active == search_criteria.is_active)

        if search_criteria.is_verified is not None:
            query = query.where(User.is_verified == search_criteria.is_verified)

        if search_criteria.min_games is not None:
            query = query.where(User.total_games >= search_criteria.min_games)

        if search_criteria.max_games is not None:
            query = query.where(User.total_games <= search_criteria.max_games)

        if search_criteria.min_score is not None:
            query = query.where(User.quantum_score >= search_criteria.min_score)

        # Tri
        if search_criteria.sort_by:
            sort_field = getattr(User, search_criteria.sort_by, User.created_at)
            if search_criteria.sort_order == 'asc':
                query = query.order_by(sort_field)
            else:
                query = query.order_by(desc(sort_field))

        # Pagination
        total_query = select(func.count(User.id)).select_from(query.subquery())
        total_result = await db.execute(total_query)
        total = total_result.scalar()

        offset = (search_criteria.page - 1) * search_criteria.page_size
        query = query.offset(offset).limit(search_criteria.page_size)

        result = await db.execute(query)
        users = result.scalars().all()

        total_pages = (total + search_criteria.page_size - 1) // search_criteria.page_size

        return {
            'users': users,
            'total': total,
            'page': search_criteria.page,
            'page_size': search_criteria.page_size,
            'total_pages': total_pages,
            'query': search_criteria.query
        }

    # === MÉTHODES DE SÉCURITÉ ===

    async def get_locked_users(
            self,
            db: AsyncSession,
            *,
            limit: int = 100
    ) -> List[User]:
        """
        Récupère les utilisateurs verrouillés

        Args:
            db: Session de base de données
            limit: Nombre maximum d'utilisateurs

        Returns:
            Liste des utilisateurs verrouillés
        """
        now = datetime.utcnow()
        query = select(User).where(
            and_(
                User.locked_until.isnot(None),
                User.locked_until > now,
                User.is_deleted == False
            )
        ).order_by(desc(User.locked_until)).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    async def get_users_with_failed_logins(
            self,
            db: AsyncSession,
            *,
            min_attempts: int = 3,
            limit: int = 100
    ) -> List[User]:
        """
        Récupère les utilisateurs avec des tentatives de connexion échouées

        Args:
            db: Session de base de données
            min_attempts: Nombre minimum de tentatives échouées
            limit: Nombre maximum d'utilisateurs

        Returns:
            Liste des utilisateurs avec échecs de connexion
        """
        query = select(User).where(
            and_(
                User.failed_login_attempts >= min_attempts,
                User.is_deleted == False
            )
        ).order_by(desc(User.failed_login_attempts)).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    # === MÉTHODES D'ADMINISTRATION ===

    async def get_admin_user_list(
            self,
            db: AsyncSession,
            *,
            page: int = 1,
            page_size: int = 50,
            filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Récupère la liste des utilisateurs pour l'administration

        Args:
            db: Session de base de données
            page: Page courante
            page_size: Taille de la page
            filters: Filtres additionnels

        Returns:
            Liste paginée avec métadonnées admin
        """
        # Utilise la méthode de pagination héritée avec des champs admin
        return await self.get_paginated(
            db,
            page=page,
            page_size=page_size,
            filters=filters,
            order_by='created_at',
            order_desc=True,
            with_deleted=True  # Les admins peuvent voir les comptes supprimés
        )

    async def bulk_update_user_status(
            self,
            db: AsyncSession,
            user_ids: List[UUID],
            *,
            is_active: Optional[bool] = None,
            is_verified: Optional[bool] = None,
            unlock_accounts: bool = False,
            updated_by: Optional[UUID] = None
    ) -> int:
        """
        Met à jour le statut de plusieurs utilisateurs

        Args:
            db: Session de base de données
            user_ids: Liste des IDs utilisateurs
            is_active: Nouveau statut actif
            is_verified: Nouveau statut vérifié
            unlock_accounts: Déverrouiller les comptes
            updated_by: ID de l'admin effectuant l'action

        Returns:
            Nombre d'utilisateurs mis à jour
        """
        values = {}

        if is_active is not None:
            values['is_active'] = is_active

        if is_verified is not None:
            values['is_verified'] = is_verified

        if unlock_accounts:
            values['locked_until'] = None
            values['failed_login_attempts'] = 0

        if updated_by:
            values['updated_by'] = updated_by

        if not values:
            return 0

        return await self.bulk_update(
            db,
            filters={'id': user_ids},
            values=values
        )

    # === MÉTHODES DE NETTOYAGE ===

    async def cleanup_expired_tokens(
            self,
            db: AsyncSession
    ) -> int:
        """
        Nettoie les tokens expirés

        Args:
            db: Session de base de données

        Returns:
            Nombre de tokens nettoyés
        """
        now = datetime.utcnow()

        # Nettoyage des tokens de reset de mot de passe expirés
        values = {
            'password_reset_token': None,
            'password_reset_expires': None
        }

        return await self.bulk_update(
            db,
            filters={},  # Sera filtré par la condition WHERE dans la requête
            values=values
        )

    async def get_inactive_users(
            self,
            db: AsyncSession,
            *,
            days_inactive: int = 90,
            limit: int = 1000
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
        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)

        query = select(User).where(
            and_(
                User.last_login < cutoff_date,
                User.is_active == True,
                User.is_deleted == False
            )
        ).order_by(User.last_login).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()