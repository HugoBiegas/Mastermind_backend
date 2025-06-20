"""
Routes de gestion des utilisateurs pour Quantum Mastermind
Profils, préférences, statistiques, recherche, administration
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_database, get_current_active_user, get_current_superuser,
    get_pagination_params, create_http_exception_from_error, PaginationParams
)
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.user import (
    UserUpdate, UserPreferences, UserStats, UserSearch,
    UserPublic, UserProfile, UserList, Leaderboard,
    UserBulkAction, UserValidation, UserValidationResult, UserSummary
)
from app.services.user import user_service
from app.utils.exceptions import EntityNotFoundError, ValidationError

# Configuration du router
router = APIRouter(prefix="/users", tags=["Utilisateurs"])


# =====================================================
# ROUTES SPÉCIFIQUES - DOIVENT ÊTRE EN PREMIER
# =====================================================
# CORRECTION CRITIQUE : Ces routes doivent être AVANT /{user_id}

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
    return UserProfile.model_validate(current_user)


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
        return UserProfile.model_validate(updated_user)

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
    description="Supprime définitivement le compte de l'utilisateur connecté"
)
async def delete_my_account(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Supprime définitivement le compte de l'utilisateur connecté

    ⚠️ ATTENTION: Cette action est irréversible !
    """
    try:
        await user_service.delete_user_account(db, current_user.id)
        return MessageResponse(
            message="Votre compte a été supprimé avec succès",
            details={"user_id": str(current_user.id)}
        )

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la suppression du compte"
        )


@router.get(
    "/me/stats",
    response_model=UserStats,
    summary="Mes statistiques",
    description="Récupère les statistiques détaillées de l'utilisateur connecté"
)
async def get_my_stats(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> UserStats:
    """
    Récupère les statistiques détaillées de l'utilisateur connecté

    Inclut les performances, temps de jeu, classements, etc.
    """
    try:
        stats = await user_service.get_user_statistics(db, current_user.id)
        return UserStats.model_validate(stats)

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des statistiques"
        )


@router.get(
    "/me/preferences",
    response_model=UserPreferences,
    summary="Mes préférences",
    description="Récupère les préférences de l'utilisateur connecté"
)
async def get_my_preferences(
        current_user: User = Depends(get_current_active_user)
) -> UserPreferences:
    """
    Récupère les préférences de l'utilisateur connecté

    Inclut les paramètres de jeu, notifications, etc.
    """
    return UserPreferences.model_validate(current_user.preferences)


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

    - **language**: Langue de l'interface
    - **theme**: Thème visuel
    - **notifications**: Paramètres de notifications
    """
    try:
        updated_user = await user_service.update_user_preferences(
            db, current_user.id, preferences
        )
        return UserPreferences.model_validate(updated_user.preferences)

    except (EntityNotFoundError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la mise à jour des préférences"
        )


@router.get(
    "/search",
    response_model=UserList,
    summary="Rechercher des utilisateurs",
    description="Recherche d'utilisateurs avec filtres et pagination"
)
async def search_users(
        search_params: UserSearch = Depends(),
        pagination: PaginationParams = Depends(get_pagination_params),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> UserList:
    """
    Recherche des utilisateurs avec filtres

    - **query**: Terme de recherche (nom, email)
    - **min_score**: Score minimum
    - **rank**: Rang spécifique
    - **active_only**: Utilisateurs actifs seulement
    """
    try:
        users, total = await user_service.search_users(
            db, search_params, pagination.skip, pagination.limit
        )

        user_summaries = [UserSummary.model_validate(user) for user in users]

        return UserList(
            users=user_summaries,
            total=total,
            page=pagination.page,
            per_page=pagination.limit,
            pages=(total + pagination.limit - 1) // pagination.limit
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la recherche d'utilisateurs"
        )


@router.get(
    "/leaderboard",
    response_model=Leaderboard,
    summary="Classement des joueurs",
    description="Récupère le classement des meilleurs joueurs"
)
async def get_leaderboard(
        period: str = Query(default="all", description="Période du classement"),
        limit: int = Query(default=50, ge=1, le=100, description="Nombre d'entrées"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Leaderboard:
    """
    Récupère le classement des joueurs

    - **period**: Période (all, month, week, day)
    - **limit**: Nombre de joueurs à retourner
    """
    try:
        leaderboard_data = await user_service.get_leaderboard(db, period, limit)
        return Leaderboard.model_validate(leaderboard_data)

    except ValidationError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération du classement"
        )


@router.get(
    "/validate",
    response_model=UserValidationResult,
    summary="Valider des données utilisateur",
    description="Valide la disponibilité d'un nom d'utilisateur ou email"
)
async def validate_user_data(
        validation_data: UserValidation,
        db: AsyncSession = Depends(get_database)
) -> UserValidationResult:
    """
    Valide des données utilisateur

    - **field**: Champ à valider (username, email)
    - **value**: Valeur à valider
    """
    try:
        result = await user_service.validate_user_field(
            db, validation_data.field, validation_data.value
        )
        return UserValidationResult.model_validate(result)

    except ValidationError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la validation"
        )


# === ROUTES D'ADMINISTRATION SPÉCIFIQUES ===

@router.get(
    "/admin/list",
    response_model=UserList,
    summary="Liste administrative des utilisateurs",
    description="Liste complète des utilisateurs pour les administrateurs"
)
async def admin_list_users(
        search_params: UserSearch = Depends(),
        pagination: PaginationParams = Depends(get_pagination_params),
        current_user: User = Depends(get_current_superuser),
        db: AsyncSession = Depends(get_database)
) -> UserList:
    """
    Liste administrative des utilisateurs

    Accès réservé aux super-utilisateurs
    """
    try:
        users, total = await user_service.admin_search_users(
            db, search_params, pagination.skip, pagination.limit
        )

        user_profiles = [UserSummary.model_validate(user) for user in users]

        return UserList(
            users=user_profiles,
            total=total,
            page=pagination.page,
            per_page=pagination.limit,
            pages=(total + pagination.limit - 1) // pagination.limit
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des utilisateurs"
        )


@router.post(
    "/admin/bulk-action",
    response_model=MessageResponse,
    summary="Action en lot sur les utilisateurs",
    description="Effectue une action sur plusieurs utilisateurs"
)
async def admin_bulk_action(
        bulk_action: UserBulkAction,
        current_user: User = Depends(get_current_superuser),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Action en lot sur les utilisateurs

    Actions disponibles: activate, deactivate, verify, ban, etc.
    """
    try:
        result = await user_service.admin_bulk_action(
            db, bulk_action, performed_by=current_user.id
        )

        return MessageResponse(
            message=f"Action '{bulk_action.action}' effectuée sur {len(bulk_action.user_ids)} utilisateurs",
            details=result
        )

    except (ValidationError, EntityNotFoundError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'exécution de l'action en lot"
        )


# =====================================================
# ROUTES AVEC PARAMÈTRES UUID - À LA FIN
# =====================================================
# CORRECTION CRITIQUE : Ces routes doivent être EN DERNIER

@router.get(
    "/{user_id}",
    response_model=UserPublic,
    summary="Profil public d'un utilisateur",
    description="Récupère le profil public d'un utilisateur par son ID"
)
async def get_user_profile(
        user_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> UserPublic:
    """
    Récupère le profil public d'un utilisateur

    Accessible à tous les utilisateurs connectés
    """
    try:
        user = await user_service.get_user_public_profile(db, user_id)
        return UserPublic.model_validate(user)

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération du profil"
        )


@router.get(
    "/{user_id}/stats",
    response_model=UserStats,
    summary="Statistiques d'un utilisateur",
    description="Récupère les statistiques publiques d'un utilisateur"
)
async def get_user_stats(
        user_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> UserStats:
    """
    Récupère les statistiques publiques d'un utilisateur

    Seules les statistiques publiques sont accessibles
    """
    try:
        stats = await user_service.get_user_public_statistics(db, user_id)
        return UserStats.model_validate(stats)

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des statistiques"
        )


@router.put(
    "/{user_id}",
    response_model=UserProfile,
    summary="Modifier un utilisateur (Admin)",
    description="Met à jour les informations d'un utilisateur (admin seulement)"
)
async def admin_update_user(
        user_id: UUID,
        user_update: UserUpdate,
        current_user: User = Depends(get_current_superuser),
        db: AsyncSession = Depends(get_database)
) -> UserProfile:
    """
    Met à jour les informations d'un utilisateur

    Accès réservé aux administrateurs
    """
    try:
        updated_user = await user_service.admin_update_user(
            db, user_id, user_update, updated_by=current_user.id
        )
        return UserProfile.model_validate(updated_user)

    except (EntityNotFoundError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la modification de l'utilisateur"
        )


@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="Supprimer un utilisateur (Admin)",
    description="Supprime un utilisateur (admin seulement)"
)
async def admin_delete_user(
        user_id: UUID,
        current_user: User = Depends(get_current_superuser),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Supprime un utilisateur

    Accès réservé aux administrateurs
    ⚠️ ATTENTION: Cette action est irréversible !
    """
    try:
        await user_service.admin_delete_user(
            db, user_id, deleted_by=current_user.id
        )
        return MessageResponse(
            message="Utilisateur supprimé avec succès",
            details={"user_id": str(user_id), "deleted_by": str(current_user.id)}
        )

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la suppression de l'utilisateur"
        )


@router.post(
    "/{user_id}/moderate",
    response_model=MessageResponse,
    summary="Modérer un utilisateur",
    description="Effectue des actions de modération sur un utilisateur"
)
async def moderate_user(
        user_id: UUID,
        action: str = Query(..., description="Action de modération"),
        reason: str = Query(..., description="Raison de l'action"),
        duration: int = Query(None, description="Durée en jours (optionnel)"),
        current_user: User = Depends(get_current_superuser),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Effectue des actions de modération sur un utilisateur

    Actions disponibles:
    - warn: Avertissement
    - mute: Réduire au silence
    - ban: Bannir temporairement
    - permanent_ban: Bannir définitivement
    - unban: Lever le ban
    - verify: Vérifier le compte
    - lock: Verrouiller le compte

    - **action**: Action à effectuer
    - **reason**: Raison de l'action (obligatoire)
    - **duration**: Durée en jours pour les actions temporaires
    """
    try:
        await user_service.moderate_user(
            db, user_id, action, reason, duration, current_user.id
        )

        return MessageResponse(
            message=f"Action '{action}' effectuée sur l'utilisateur {user_id}",
            details={
                "action": action,
                "reason": reason,
                "duration": duration,
                "moderator": str(current_user.id)
            }
        )

    except (EntityNotFoundError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'action de modération"
        )