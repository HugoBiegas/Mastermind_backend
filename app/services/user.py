"""
Service utilisateur pour Quantum Mastermind
Gestion des profils, préférences, statistiques et actions utilisateur
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import (
    UserUpdate, UserPreferences, UserSearch, UserStats,
    UserValidation, UserValidationResult, UserBulkAction
)
from app.utils.exceptions import (
    EntityNotFoundError, ValidationError, AuthorizationError
)


class UserService:
    """Service pour la gestion des utilisateurs"""

    def __init__(self):
        self.user_repo = UserRepository()

    # === MÉTHODES DE PROFIL ===

    async def get_user_profile(
            self,
            db: AsyncSession,
            user_id: UUID,
            *,
            requesting_user_id: Optional[UUID] = None,
            is_admin: bool = False
    ) -> Dict[str, Any]:
        """
        Récupère le profil d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur
            requesting_user_id: ID de l'utilisateur demandeur
            is_admin: Si la demande vient d'un admin

        Returns:
            Profil utilisateur (public ou privé selon les droits)

        Raises:
            EntityNotFoundError: Si l'utilisateur n'existe pas
        """
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise EntityNotFoundError("Utilisateur non trouvé")

        # Détermine le niveau de détail selon les droits
        if user_id == requesting_user_id or is_admin:
            # Profil complet pour le propriétaire ou admin
            return user.to_profile_dict()
        else:
            # Profil public pour les autres
            return user.to_public_dict()

    async def update_user_profile(
            self,
            db: AsyncSession,
            user_id: UUID,
            update_data: UserUpdate,
            *,
            updated_by: UUID
    ) -> User:
        """
        Met à jour le profil d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur à modifier
            update_data: Nouvelles données
            updated_by: ID de l'utilisateur modificateur

        Returns:
            Utilisateur mis à jour

        Raises:
            EntityNotFoundError: Si l'utilisateur n'existe pas
            ValidationError: Si les données sont invalides
        """
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise EntityNotFoundError("Utilisateur non trouvé")

        # Validation des données
        await self._validate_update_data(db, update_data, user_id)

        # Mise à jour
        updated_user = await self.user_repo.update(
            db,
            db_obj=user,
            obj_in=update_data,
            updated_by=updated_by
        )

        return updated_user

    async def delete_user_account(
            self,
            db: AsyncSession,
            user_id: UUID,
            *,
            soft_delete: bool = True,
            deleted_by: Optional[UUID] = None
    ) -> bool:
        """
        Supprime un compte utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur à supprimer
            soft_delete: Suppression logique ou physique
            deleted_by: ID de l'utilisateur effectuant la suppression

        Returns:
            True si supprimé avec succès

        Raises:
            EntityNotFoundError: Si l'utilisateur n'existe pas
        """
        return await self.user_repo.delete(
            db,
            id=user_id,
            soft_delete=soft_delete,
            deleted_by=deleted_by
        )

    # === MÉTHODES DE PRÉFÉRENCES ===

    async def get_user_preferences(
            self,
            db: AsyncSession,
            user_id: UUID
    ) -> UserPreferences:
        """
        Récupère les préférences d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur

        Returns:
            Préférences utilisateur

        Raises:
            EntityNotFoundError: Si l'utilisateur n'existe pas
        """
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise EntityNotFoundError("Utilisateur non trouvé")

        # Préférences par défaut si aucune préférence définie
        default_preferences = UserPreferences()
        user_prefs = user.preferences or {}

        # Fusion des préférences par défaut avec celles de l'utilisateur
        final_preferences = default_preferences.dict()
        final_preferences.update(user_prefs)

        return UserPreferences(**final_preferences)

    async def update_user_preferences(
            self,
            db: AsyncSession,
            user_id: UUID,
            preferences: UserPreferences
    ) -> UserPreferences:
        """
        Met à jour les préférences d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur
            preferences: Nouvelles préférences

        Returns:
            Préférences mises à jour

        Raises:
            EntityNotFoundError: Si l'utilisateur n'existe pas
        """
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise EntityNotFoundError("Utilisateur non trouvé")

        # Mise à jour des préférences
        preferences_dict = preferences.dict(exclude_unset=True)

        await self.user_repo.update(
            db,
            db_obj=user,
            obj_in={'preferences': preferences_dict},
            updated_by=user_id
        )

        return preferences

    # === MÉTHODES DE STATISTIQUES ===

    async def get_user_statistics(
            self,
            db: AsyncSession,
            user_id: UUID
    ) -> UserStats:
        """
        Récupère les statistiques détaillées d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur

        Returns:
            Statistiques complètes

        Raises:
            EntityNotFoundError: Si l'utilisateur n'existe pas
        """
        # Récupération des stats de base
        basic_stats = await self.user_repo.get_user_stats(db, user_id)
        if not basic_stats:
            raise EntityNotFoundError("Utilisateur non trouvé")

        # Enrichissement avec des statistiques calculées
        # TODO: Ajouter des requêtes pour les stats avancées quand les modèles Game seront connectés

        return UserStats(
            user_id=UUID(basic_stats['user_id']),
            username=basic_stats['username'],
            total_games=basic_stats['total_games'],
            wins=basic_stats['wins'],
            losses=basic_stats['losses'],
            win_rate=basic_stats['win_rate'],
            best_time=basic_stats['best_time'],
            average_time=basic_stats['average_time'],
            quantum_score=basic_stats['quantum_score'],
            total_score=basic_stats['quantum_score'],  # Pour l'instant, même chose
            best_game_score=0,  # TODO: Calculer
            average_game_score=0.0,  # TODO: Calculer
            total_quantum_measurements=0,  # TODO: Calculer
            total_grover_hints=0,  # TODO: Calculer
            total_entanglement_uses=0,  # TODO: Calculer
            quantum_advantage_score=0.0,  # TODO: Calculer
            games_this_week=basic_stats['games_this_week'],
            games_this_month=basic_stats['games_this_month'],
            improvement_rate=0.0,  # TODO: Calculer
            rank=1,  # TODO: Calculer le rang
            classic_games=0,  # TODO: Calculer
            quantum_games=0,  # TODO: Calculer
            multiplayer_games=0,  # TODO: Calculer
            tournament_games=0  # TODO: Calculer
        )

    async def update_user_game_stats(
            self,
            db: AsyncSession,
            user_id: UUID,
            game_result: Dict[str, Any]
    ) -> None:
        """
        Met à jour les statistiques de jeu d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur
            game_result: Résultats de la partie

        Raises:
            EntityNotFoundError: Si l'utilisateur n'existe pas
        """
        user = await self.user_repo.get_by_id(db, user_id)
        if not user:
            raise EntityNotFoundError("Utilisateur non trouvé")

        # Mise à jour des statistiques
        user.update_game_stats(
            won=game_result.get('won', False),
            game_time=game_result.get('game_time', 0.0),
            quantum_points=game_result.get('quantum_points', 0)
        )

        await db.commit()

    # === MÉTHODES DE RECHERCHE ===

    async def search_users(
            self,
            db: AsyncSession,
            search_criteria: UserSearch
    ) -> Dict[str, Any]:
        """
        Recherche des utilisateurs avec critères

        Args:
            db: Session de base de données
            search_criteria: Critères de recherche

        Returns:
            Résultats de recherche paginés
        """
        return await self.user_repo.search_users(db, search_criteria)

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
            category: Catégorie de classement
            limit: Nombre d'utilisateurs
            period: Période de temps

        Returns:
            Leaderboard ordonné
        """
        return await self.user_repo.get_leaderboard(
            db,
            category=category,
            limit=limit,
            period=period
        )

    # === MÉTHODES DE VALIDATION ===

    async def validate_user_field(
            self,
            db: AsyncSession,
            validation_data: UserValidation,
            exclude_user_id: Optional[UUID] = None
    ) -> UserValidationResult:
        """
        Valide un champ utilisateur (username, email)

        Args:
            db: Session de base de données
            validation_data: Données à valider
            exclude_user_id: ID utilisateur à exclure (pour les mises à jour)

        Returns:
            Résultat de validation avec suggestions
        """
        field = validation_data.field
        value = validation_data.value

        if field == 'username':
            return await self._validate_username(db, value, exclude_user_id)
        elif field == 'email':
            return await self._validate_email(db, value, exclude_user_id)
        else:
            return UserValidationResult(
                is_valid=False,
                is_available=False,
                errors=["Champ non supporté"]
            )

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
        Récupère la liste des utilisateurs pour l'admin

        Args:
            db: Session de base de données
            page: Page courante
            page_size: Taille de la page
            filters: Filtres additionnels

        Returns:
            Liste paginée avec métadonnées
        """
        return await self.user_repo.get_admin_user_list(
            db,
            page=page,
            page_size=page_size,
            filters=filters
        )

    async def bulk_user_action(
            self,
            db: AsyncSession,
            action_data: UserBulkAction,
            admin_user_id: UUID
    ) -> Dict[str, Any]:
        """
        Effectue une action en lot sur des utilisateurs

        Args:
            db: Session de base de données
            action_data: Données de l'action
            admin_user_id: ID de l'admin effectuant l'action

        Returns:
            Résultats de l'action

        Raises:
            AuthorizationError: Si l'action n'est pas autorisée
            ValidationError: Si les données sont invalides
        """
        action = action_data.action
        user_ids = action_data.user_ids

        success_count = 0
        errors = []

        try:
            if action == 'activate':
                success_count = await self.user_repo.bulk_update_user_status(
                    db, user_ids, is_active=True, updated_by=admin_user_id
                )
            elif action == 'deactivate':
                success_count = await self.user_repo.bulk_update_user_status(
                    db, user_ids, is_active=False, updated_by=admin_user_id
                )
            elif action == 'verify':
                success_count = await self.user_repo.bulk_update_user_status(
                    db, user_ids, is_verified=True, updated_by=admin_user_id
                )
            elif action == 'unlock':
                success_count = await self.user_repo.bulk_update_user_status(
                    db, user_ids, unlock_accounts=True, updated_by=admin_user_id
                )
            else:
                raise ValidationError(f"Action non supportée: {action}")

        except Exception as e:
            errors.append({'action': action, 'error': str(e)})

        return {
            'success_count': success_count,
            'error_count': len(errors),
            'errors': errors,
            'message': f"Action '{action}' effectuée sur {success_count} utilisateurs"
        }

    # === MÉTHODES DE MAINTENANCE ===

    async def cleanup_inactive_users(
            self,
            db: AsyncSession,
            *,
            days_inactive: int = 365,
            dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Nettoie les comptes inactifs

        Args:
            db: Session de base de données
            days_inactive: Jours d'inactivité avant nettoyage
            dry_run: Mode simulation (ne supprime pas vraiment)

        Returns:
            Rapport de nettoyage
        """
        inactive_users = await self.user_repo.get_inactive_users(
            db, days_inactive=days_inactive, limit=1000
        )

        if dry_run:
            return {
                'action': 'simulation',
                'users_found': len(inactive_users),
                'users_cleaned': 0,
                'details': [
                    {
                        'user_id': str(user.id),
                        'username': user.username,
                        'last_login': user.last_login.isoformat() if user.last_login else None
                    }
                    for user in inactive_users[:10]  # Limite à 10 pour l'affichage
                ]
            }

        # Suppression réelle (soft delete)
        cleaned_count = 0
        for user in inactive_users:
            try:
                await self.user_repo.delete(db, id=user.id, soft_delete=True)
                cleaned_count += 1
            except Exception:
                continue

        return {
            'action': 'cleanup',
            'users_found': len(inactive_users),
            'users_cleaned': cleaned_count,
            'details': []
        }

    # === MÉTHODES PRIVÉES ===

    async def _validate_update_data(
            self,
            db: AsyncSession,
            update_data: UserUpdate,
            exclude_user_id: UUID
    ) -> None:
        """Valide les données de mise à jour"""
        errors = []

        if update_data.username:
            username_available = await self.user_repo.is_username_available(
                db, update_data.username, exclude_user_id
            )
            if not username_available:
                errors.append("Nom d'utilisateur déjà utilisé")

        if update_data.email:
            email_available = await self.user_repo.is_email_available(
                db, update_data.email, exclude_user_id
            )
            if not email_available:
                errors.append("Adresse email déjà utilisée")

        if errors:
            raise ValidationError("; ".join(errors))

    async def _validate_username(
            self,
            db: AsyncSession,
            username: str,
            exclude_user_id: Optional[UUID]
    ) -> UserValidationResult:
        """Valide un nom d'utilisateur"""
        from app.core.security import input_validator

        # Validation format
        validation = input_validator.validate_username(username)
        if not validation['is_valid']:
            return UserValidationResult(
                is_valid=False,
                is_available=False,
                errors=validation['errors']
            )

        # Vérification disponibilité
        is_available = await self.user_repo.is_username_available(
            db, username, exclude_user_id
        )

        suggestions = []
        if not is_available:
            # Génération de suggestions
            for i in range(1, 4):
                suggestion = f"{username}{i}"
                if await self.user_repo.is_username_available(db, suggestion):
                    suggestions.append(suggestion)

        return UserValidationResult(
            is_valid=True,
            is_available=is_available,
            errors=[],
            suggestions=suggestions
        )

    async def _validate_email(
            self,
            db: AsyncSession,
            email: str,
            exclude_user_id: Optional[UUID]
    ) -> UserValidationResult:
        """Valide une adresse email"""
        from app.core.security import input_validator

        # Validation format
        validation = input_validator.validate_email(email)
        if not validation['is_valid']:
            return UserValidationResult(
                is_valid=False,
                is_available=False,
                errors=validation['errors']
            )

        # Vérification disponibilité
        is_available = await self.user_repo.is_email_available(
            db, email, exclude_user_id
        )

        return UserValidationResult(
            is_valid=True,
            is_available=is_available,
            errors=[] if is_available else ["Email déjà utilisé"],
            suggestions=[]
        )


# Instance globale du service
user_service = UserService()