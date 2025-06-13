"""
Routes de gestion des utilisateurs pour Quantum Mastermind
Profils, préférences, statistiques, recherche, administration
"""
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_database, get_current_active_user, get_current_superuser,
    validate_user_access, get_pagination_params, get_search_params,
    create_http_exception_from_error, PaginationParams, SearchParams
)
from app.models.user import User
from app.services.user import user_service
from app.schemas.user import (
    UserUpdate, UserPreferences, UserStats, UserSearch,
    UserPublic, UserProfile, UserList, Leaderboard,
    UserBulkAction, UserValidation, UserValidationResult
)
from app.schemas.auth import MessageResponse
from app.utils.exceptions import EntityNotFoundError, ValidationError

# Configuration du router
router = APIRouter(prefix="/users", tags=["Utilisateurs"])


# === ROUTES DE PROFIL UTILISATEUR ===

@router.get(
    "/me",
    response_model=UserProfile,
    summary="Mon profil",
    description="Récupère le profil complet de l'utilisateur connecté"
)
async def get_my_profile(
        current_user: User = Depends(get_current_active_user)
) -> UserProfile:
    """
    Récupère le profil complet de l'utilisateur connecté

    Inclut toutes les informations personnelles et statistiques
    """
    return UserProfile.from_orm(current_user)


@router.put(
    "/me",
    response_model=UserProfile,
    summary="Modifier mon profil",
    description="Met à jour le profil de l'utilisateur connecté"
)
async def update_my_profile(
        user_update: UserUpdate,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> UserProfile:
    """
    Met à jour le profil de l'utilisateur connecté

    - **username**: Nouveau nom d'utilisateur (optionnel)
    - **email**: Nouvelle adresse email (optionnel)
    - **preferences**: Nouvelles préférences (optionnel)
    """
    try:
        updated_user = await user_service.update_user_profile(
            db, current_user.id, user_update, updated_by=current_user.id
        )
        return UserProfile.from_orm(updated_user)

    except (EntityNotFoundError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la mise à jour du profil"
        )


@router.delete(
    "/me",
    response_model=MessageResponse,
    summary="Supprimer mon compte",
    description="Supprime le compte de l'utilisateur connecté"
)
async def delete_my_account(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Supprime le compte de l'utilisateur connecté

    Note: Effectue une suppression logique par défaut
    """
    try:
        await user_service.delete_user_account(
            db, current_user.id, soft_delete=True, deleted_by=current_user.id
        )

        return MessageResponse(
            message="Compte supprimé avec succès",
            details={"user_id": str(current_user.id)}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la suppression du compte"
        )


# === ROUTES DE PRÉFÉRENCES ===

@router.get(
    "/me/preferences",
    response_model=UserPreferences,
    summary="Mes préférences",
    description="Récupère les préférences de l'utilisateur connecté"
)
async def get_my_preferences(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> UserPreferences:
    """
    Récupère les préférences de l'utilisateur connecté
    """
    try:
        preferences = await user_service.get_user_preferences(db, current_user.id)
        return preferences

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des préférences"
        )


@router.put(
    "/me/preferences",
    response_model=UserPreferences,
    summary="Modifier mes préférences",
    description="Met à jour les préférences de l'utilisateur connecté"
)
async def update_my_preferences(
        preferences: UserPreferences,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> UserPreferences:
    """
    Met à jour les préférences de l'utilisateur connecté

    - **theme**: Thème de l'interface (light/dark/auto)
    - **language**: Langue de l'interface
    - **sound_enabled**: Sons activés
    - **notifications_enabled**: Notifications activées
    - **difficulty_preference**: Difficulté préférée
    - **quantum_hints_enabled**: Indices quantiques par défaut
    - **auto_save_games**: Sauvegarde automatique
    """
    try:
        updated_preferences = await user_service.update_user_preferences(
            db, current_user.id, preferences
        )
        return updated_preferences

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la mise à jour des préférences"
        )


# === ROUTES DE STATISTIQUES ===

@router.get(
    "/me/stats",
    response_model=UserStats,
    summary="Mes statistiques",
    description="Récupère les statistiques détaillées de l'utilisateur connecté"
)
async def get_my_statistics(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> UserStats:
    """
    Récupère les statistiques détaillées de l'utilisateur connecté

    Inclut :
    - Statistiques de base (parties, victoires, temps)
    - Statistiques quantiques (mesures, algorithmes utilisés)
    - Progression et amélioration
    - Classement
    """
    try:
        stats = await user_service.get_user_statistics(db, current_user.id)
        return stats

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des statistiques"
        )


@router.get(
    "/{user_id}/stats",
    response_model=UserStats,
    summary="Statistiques utilisateur",
    description="Récupère les statistiques publiques d'un utilisateur"
)
async def get_user_statistics(
        user_id: UUID,
        db: AsyncSession = Depends(get_database)
) -> UserStats:
    """
    Récupère les statistiques publiques d'un utilisateur

    - **user_id**: ID de l'utilisateur
    """
    try:
        stats = await user_service.get_user_statistics(db, user_id)
        return stats

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des statistiques"
        )


# === ROUTES DE CONSULTATION PUBLIQUE ===

@router.get(
    "/{user_id}",
    response_model=UserPublic,
    summary="Profil public utilisateur",
    description="Récupère le profil public d'un utilisateur"
)
async def get_user_public_profile(
        user_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> UserPublic:
    """
    Récupère le profil public d'un utilisateur

    - **user_id**: ID de l'utilisateur
    """
    try:
        # Détermine si c'est le profil de l'utilisateur actuel ou non
        requesting_user_id = current_user.id if current_user else None
        is_admin = current_user.is_superuser if current_user else False

        profile_data = await user_service.get_user_profile(
            db, user_id, requesting_user_id=requesting_user_id, is_admin=is_admin
        )

        # Si c'est les données publiques, on crée un UserPublic
        if requesting_user_id != user_id and not is_admin:
            return UserPublic(**profile_data)
        else:
            # Sinon on retourne le profil complet mais on le convertit
            return UserPublic(**profile_data)

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération du profil"
        )


# === ROUTES DE RECHERCHE ===

@router.get(
    "/search",
    response_model=Dict[str, Any],
    summary="Rechercher des utilisateurs",
    description="Recherche des utilisateurs avec critères multiples"
)
async def search_users(
        q: str = Query(None, description="Terme de recherche"),
        is_active: bool = Query(None, description="Utilisateurs actifs uniquement"),
        is_verified: bool = Query(None, description="Utilisateurs vérifiés uniquement"),
        min_games: int = Query(None, ge=0, description="Nombre minimum de parties"),
        max_games: int = Query(None, ge=0, description="Nombre maximum de parties"),
        min_score: int = Query(None, ge=0, description="Score quantique minimum"),
        sort_by: str = Query("created_at", description="Champ de tri"),
        sort_order: str = Query("desc", description="Ordre de tri (asc/desc)"),
        pagination: PaginationParams = Depends(get_pagination_params),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Recherche des utilisateurs avec critères multiples

    Permet de filtrer par :
    - Terme de recherche (username ou email)
    - Statut (actif, vérifié)
    - Statistiques de jeu
    - Tri personnalisé
    """
    try:
        search_criteria = UserSearch(
            query=q,
            is_active=is_active,
            is_verified=is_verified,
            min_games=min_games,
            max_games=max_games,
            min_score=min_score,
            sort_by=sort_by,
            sort_order=sort_order,
            page=pagination.page,
            page_size=pagination.page_size
        )

        results = await user_service.search_users(db, search_criteria)

        # Conversion en UserPublic pour la réponse
        public_users = [
            UserPublic.from_orm(user) for user in results['users']
        ]

        return {
            'users': public_users,
            'total': results['total'],
            'page': results['page'],
            'page_size': results['page_size'],
            'total_pages': results['total_pages'],
            'query': results['query']
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la recherche d'utilisateurs"
        )


# === ROUTES DE CLASSEMENT ===

@router.get(
    "/leaderboard",
    response_model=List[Dict[str, Any]],
    summary="Classement des joueurs",
    description="Récupère le leaderboard des meilleurs joueurs"
)
async def get_leaderboard(
        category: str = Query("quantum_score", description="Catégorie de classement"),
        limit: int = Query(100, ge=1, le=1000, description="Nombre de joueurs"),
        period: str = Query(None, description="Période (week/month/all-time)"),
        db: AsyncSession = Depends(get_database)
) -> List[Dict[str, Any]]:
    """
    Récupère le classement des meilleurs joueurs

    - **category**: Catégorie de classement (quantum_score, wins, win_rate, total_games)
    - **limit**: Nombre de joueurs à retourner (max 1000)
    - **period**: Période de temps (optionnel)
    """
    try:
        leaderboard = await user_service.get_leaderboard(
            db, category=category, limit=limit, period=period
        )
        return leaderboard

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération du classement"
        )


# === ROUTES DE VALIDATION ===

@router.post(
    "/validate",
    response_model=UserValidationResult,
    summary="Validation de champs",
    description="Valide la disponibilité d'un champ utilisateur"
)
async def validate_user_field(
        validation_data: UserValidation,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> UserValidationResult:
    """
    Valide la disponibilité d'un champ utilisateur

    - **field**: Champ à valider (username ou email)
    - **value**: Valeur à vérifier
    """
    try:
        # Exclure l'utilisateur actuel pour permettre de garder ses propres valeurs
        result = await user_service.validate_user_field(
            db, validation_data, exclude_user_id=current_user.id
        )
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la validation"
        )


# === ROUTES D'ADMINISTRATION ===

@router.get(
    "/admin/list",
    response_model=Dict[str, Any],
    summary="Liste admin des utilisateurs",
    description="Liste complète des utilisateurs pour l'administration"
)
async def get_admin_user_list(
        is_active: bool = Query(None, description="Filtrer par statut actif"),
        is_verified: bool = Query(None, description="Filtrer par statut vérifié"),
        is_superuser: bool = Query(None, description="Filtrer par super-utilisateurs"),
        pagination: PaginationParams = Depends(get_pagination_params),
        current_user: User = Depends(get_current_superuser),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Récupère la liste complète des utilisateurs pour l'administration

    Accessible uniquement aux super-utilisateurs
    """
    try:
        filters = {}
        if is_active is not None:
            filters['is_active'] = is_active
        if is_verified is not None:
            filters['is_verified'] = is_verified
        if is_superuser is not None:
            filters['is_superuser'] = is_superuser

        results = await user_service.get_admin_user_list(
            db,
            page=pagination.page,
            page_size=pagination.page_size,
            filters=filters
        )

        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération de la liste admin"
        )


@router.post(
    "/admin/bulk-action",
    response_model=Dict[str, Any],
    summary="Actions en lot",
    description="Effectue des actions en lot sur des utilisateurs"
)
async def bulk_user_action(
        action_data: UserBulkAction,
        current_user: User = Depends(get_current_superuser),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Effectue des actions en lot sur des utilisateurs

    Actions disponibles :
    - activate: Activer les comptes
    - deactivate: Désactiver les comptes
    - verify: Vérifier les emails
    - unlock: Déverrouiller les comptes
    - delete: Supprimer les comptes

    Accessible uniquement aux super-utilisateurs
    """
    try:
        result = await user_service.bulk_user_action(
            db, action_data, admin_user_id=current_user.id
        )
        return result

    except (ValidationError, EntityNotFoundError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'exécution de l'action en lot"
        )


@router.get(
    "/admin/{user_id}",
    response_model=UserProfile,
    summary="Profil admin utilisateur",
    description="Récupère le profil complet d'un utilisateur (admin)"
)
async def get_admin_user_profile(
        user_id: UUID,
        current_user: User = Depends(get_current_superuser),
        db: AsyncSession = Depends(get_database)
) -> UserProfile:
    """
    Récupère le profil complet d'un utilisateur pour l'administration

    Accessible uniquement aux super-utilisateurs
    """
    try:
        profile_data = await user_service.get_user_profile(
            db, user_id, requesting_user_id=current_user.id, is_admin=True
        )
        return UserProfile(**profile_data)

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération du profil admin"
        )


@router.put(
    "/admin/{user_id}",
    response_model=UserProfile,
    summary="Modifier utilisateur (admin)",
    description="Met à jour un utilisateur via l'interface admin"
)
async def update_admin_user(
        user_id: UUID,
        user_update: UserUpdate,
        current_user: User = Depends(get_current_superuser),
        db: AsyncSession = Depends(get_database)
) -> UserProfile:
    """
    Met à jour un utilisateur via l'interface d'administration

    Accessible uniquement aux super-utilisateurs
    """
    try:
        updated_user = await user_service.update_user_profile(
            db, user_id, user_update, updated_by=current_user.id
        )
        return UserProfile.from_orm(updated_user)

    except (EntityNotFoundError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la mise à jour admin"
        )


# === ROUTES DE MAINTENANCE ===

@router.post(
    "/admin/cleanup-inactive",
    response_model=Dict[str, Any],
    summary="Nettoyage des comptes inactifs",
    description="Nettoie les comptes inactifs (admin)"
)
async def cleanup_inactive_users(
        days_inactive: int = Query(365, ge=30, description="Jours d'inactivité"),
        dry_run: bool = Query(True, description="Mode simulation"),
        current_user: User = Depends(get_current_superuser),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Nettoie les comptes utilisateurs inactifs

    - **days_inactive**: Nombre de jours d'inactivité avant nettoyage
    - **dry_run**: Mode simulation (ne supprime pas vraiment)

    Accessible uniquement aux super-utilisateurs
    """
    try:
        result = await user_service.cleanup_inactive_users(
            db, days_inactive=days_inactive, dry_run=dry_run
        )
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du nettoyage des comptes inactifs"
        )