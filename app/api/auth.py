"""
Routes d'authentification pour Quantum Mastermind
Login, register, reset password, token management
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_database, get_client_info, get_current_user,
    get_current_active_user, create_http_exception_from_error
)
from app.models.user import User
from app.services.auth import auth_service
from app.schemas.auth import (
    LoginRequest, LoginResponse, RegisterRequest, RegisterResponse,
    PasswordResetRequest, PasswordResetConfirm, PasswordChangeRequest,
    RefreshToken, TokenData, MessageResponse
)
from app.schemas.user import UserProfile
from app.utils.exceptions import (
    AuthenticationError, ValidationError, AccountLockedError
)

# Configuration du router
router = APIRouter(prefix="/auth", tags=["Authentification"])


# === ROUTES D'AUTHENTIFICATION ===

@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Connexion utilisateur",
    description="Authentifie un utilisateur avec username/email et mot de passe"
)
async def login(
        login_data: LoginRequest,
        client_info: Dict[str, Any] = Depends(get_client_info),
        db: AsyncSession = Depends(get_database)
) -> LoginResponse:
    """
    Authentifie un utilisateur et retourne les tokens d'accès

    - **username_or_email**: Nom d'utilisateur ou adresse email
    - **password**: Mot de passe
    - **remember_me**: Session persistante (optionnel)
    """
    try:
        login_response = await auth_service.authenticate_user(
            db, login_data, client_info
        )
        return login_response

    except (AuthenticationError, AccountLockedError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'authentification"
        )


@router.post(
    "/register",
    response_model=RegisterResponse,
    summary="Inscription utilisateur",
    description="Crée un nouveau compte utilisateur"
)
async def register(
        register_data: RegisterRequest,
        client_info: Dict[str, Any] = Depends(get_client_info),
        db: AsyncSession = Depends(get_database)
) -> RegisterResponse:
    """
    Crée un nouveau compte utilisateur

    - **username**: Nom d'utilisateur unique (3-50 caractères)
    - **email**: Adresse email valide
    - **password**: Mot de passe sécurisé (min 8 caractères)
    - **password_confirm**: Confirmation du mot de passe
    - **accept_terms**: Acceptation des conditions d'utilisation
    """
    try:
        register_response = await auth_service.register_user(
            db, register_data, client_info
        )
        return register_response

    except ValidationError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'inscription"
        )


@router.post(
    "/refresh",
    response_model=Dict[str, Any],
    summary="Renouvellement de token",
    description="Renouvelle un token d'accès avec un refresh token"
)
async def refresh_token(
        refresh_data: RefreshToken,
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Renouvelle un token d'accès à l'aide d'un refresh token

    - **refresh_token**: Token de renouvellement valide
    """
    try:
        token_response = await auth_service.refresh_access_token(db, refresh_data)
        return token_response

    except AuthenticationError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du renouvellement du token"
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Déconnexion",
    description="Déconnecte l'utilisateur (invalide les tokens côté client)"
)
async def logout(
        current_user: User = Depends(get_current_user)
) -> MessageResponse:
    """
    Déconnecte l'utilisateur actuel

    Note: Cette route invalide principalement les tokens côté client.
    Pour une invalidation côté serveur, un système de blacklist serait nécessaire.
    """
    # TODO: Implémenter la blacklist des tokens si nécessaire
    # Pour l'instant, la déconnexion se fait côté client

    return MessageResponse(
        message="Déconnexion réussie",
        details={"user_id": str(current_user.id)}
    )


# === ROUTES DE GESTION DES MOTS DE PASSE ===

@router.post(
    "/password/change",
    response_model=MessageResponse,
    summary="Changement de mot de passe",
    description="Change le mot de passe d'un utilisateur connecté"
)
async def change_password(
        password_data: PasswordChangeRequest,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Change le mot de passe de l'utilisateur connecté

    - **current_password**: Mot de passe actuel
    - **new_password**: Nouveau mot de passe sécurisé
    - **new_password_confirm**: Confirmation du nouveau mot de passe
    """
    try:
        result = await auth_service.change_password(
            db, current_user.id, password_data
        )
        return MessageResponse(message=result['message'])

    except (AuthenticationError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du changement de mot de passe"
        )


@router.post(
    "/password/reset/request",
    response_model=MessageResponse,
    summary="Demande de réinitialisation",
    description="Demande un lien de réinitialisation de mot de passe par email"
)
async def request_password_reset(
        reset_data: PasswordResetRequest,
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Demande une réinitialisation de mot de passe

    - **email**: Adresse email du compte à réinitialiser

    Note: Cette route retourne toujours un succès pour éviter l'énumération d'emails
    """
    try:
        result = await auth_service.request_password_reset(db, reset_data)
        return MessageResponse(message=result['message'])

    except Exception as e:
        # Toujours retourner un succès pour éviter l'énumération
        return MessageResponse(
            message="Si cette adresse email existe, vous recevrez un email de réinitialisation"
        )


@router.post(
    "/password/reset/confirm",
    response_model=MessageResponse,
    summary="Confirmation de réinitialisation",
    description="Confirme la réinitialisation avec le token reçu par email"
)
async def confirm_password_reset(
        reset_data: PasswordResetConfirm,
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Confirme la réinitialisation de mot de passe

    - **token**: Token de réinitialisation reçu par email
    - **new_password**: Nouveau mot de passe sécurisé
    - **new_password_confirm**: Confirmation du nouveau mot de passe
    """
    try:
        result = await auth_service.confirm_password_reset(db, reset_data)
        return MessageResponse(message=result['message'])

    except (AuthenticationError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la réinitialisation du mot de passe"
        )


# === ROUTES D'INFORMATION ===

@router.get(
    "/me",
    response_model=UserProfile,
    summary="Profil utilisateur",
    description="Retourne le profil de l'utilisateur connecté"
)
async def get_current_user_profile(
        current_user: User = Depends(get_current_active_user)
) -> UserProfile:
    """
    Récupère le profil de l'utilisateur connecté

    Retourne toutes les informations du profil utilisateur incluant :
    - Informations personnelles
    - Statistiques de jeu
    - Paramètres de compte
    """
    return UserProfile.from_orm(current_user)


@router.get(
    "/verify-token",
    response_model=TokenData,
    summary="Vérification de token",
    description="Vérifie la validité d'un token et retourne ses données"
)
async def verify_token(
        current_user: User = Depends(get_current_user)
) -> TokenData:
    """
    Vérifie la validité du token d'accès et retourne les données utilisateur

    Utile pour vérifier l'état de l'authentification côté client
    """
    from datetime import datetime, timedelta
    from app.core.config import settings

    return TokenData(
        user_id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_verified=current_user.is_verified,
        is_superuser=current_user.is_superuser,
        exp=datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
        jti="current_token"  # En réalité, ceci viendrait du token JWT
    )


# === ROUTES DE VALIDATION ===

@router.get(
    "/check-username/{username}",
    response_model=Dict[str, Any],
    summary="Vérification nom d'utilisateur",
    description="Vérifie la disponibilité d'un nom d'utilisateur"
)
async def check_username_availability(
        username: str,
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Vérifie si un nom d'utilisateur est disponible

    - **username**: Nom d'utilisateur à vérifier
    """
    try:
        from app.services.user import user_service
        from app.schemas.user import UserValidation

        validation_data = UserValidation(field="username", value=username)
        result = await user_service.validate_user_field(db, validation_data)

        return {
            "username": username,
            "available": result.is_available,
            "valid": result.is_valid,
            "errors": result.errors,
            "suggestions": result.suggestions
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la vérification du nom d'utilisateur"
        )


@router.get(
    "/check-email/{email}",
    response_model=Dict[str, Any],
    summary="Vérification email",
    description="Vérifie la disponibilité d'une adresse email"
)
async def check_email_availability(
        email: str,
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Vérifie si une adresse email est disponible

    - **email**: Adresse email à vérifier
    """
    try:
        from app.services.user import user_service
        from app.schemas.user import UserValidation

        validation_data = UserValidation(field="email", value=email)
        result = await user_service.validate_user_field(db, validation_data)

        return {
            "email": email,
            "available": result.is_available,
            "valid": result.is_valid,
            "errors": result.errors
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la vérification de l'email"
        )


# === ROUTES DE SÉCURITÉ ===

@router.get(
    "/security/status",
    response_model=Dict[str, Any],
    summary="Statut de sécurité",
    description="Retourne les informations de sécurité du compte"
)
async def get_security_status(
        current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Récupère le statut de sécurité du compte utilisateur

    Inclut les informations sur :
    - Tentatives de connexion échouées
    - Dernière connexion
    - État de vérification
    - Verrouillage de compte
    """
    return {
        "user_id": str(current_user.id),
        "is_verified": current_user.is_verified,
        "is_locked": current_user.is_locked,
        "failed_login_attempts": current_user.failed_login_attempts,
        "locked_until": current_user.locked_until.isoformat() if current_user.locked_until else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "last_ip_address": current_user.last_ip_address,
        "login_count": current_user.login_count,
        "password_changed_at": current_user.password_changed_at.isoformat() if current_user.password_changed_at else None,
        "account_age_days": (current_user.updated_at - current_user.created_at).days if current_user.updated_at else 0
    }


# === ROUTES D'ADMINISTRATION (pour les admins) ===

@router.post(
    "/admin/unlock-user/{user_id}",
    response_model=MessageResponse,
    summary="Déverrouiller utilisateur",
    description="Déverrouille un compte utilisateur (admin uniquement)"
)
async def unlock_user_account(
        user_id: str,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Déverrouille un compte utilisateur (admin uniquement)

    - **user_id**: ID de l'utilisateur à déverrouiller
    """
    # Vérification des permissions admin
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissions administrateur requises"
        )

    try:
        from app.services.user import user_service
        from uuid import UUID

        # Récupération de l'utilisateur cible
        target_user_uuid = UUID(user_id)

        # Déverrouillage via le service utilisateur
        await user_service.bulk_user_action(
            db,
            user_ids=[target_user_uuid],
            action="unlock",
            admin_user_id=current_user.id
        )

        return MessageResponse(
            message=f"Compte utilisateur {user_id} déverrouillé avec succès"
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID utilisateur invalide"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du déverrouillage du compte"
        )


# === ROUTES DE DÉVELOPPEMENT (à désactiver en production) ===

if False:  # Activer uniquement en développement
    @router.get(
        "/dev/token-info",
        summary="Informations token (DEV)",
        description="Affiche les informations détaillées du token (développement uniquement)"
    )
    async def get_token_info_dev(
            request: Request,
            current_user: User = Depends(get_current_user)
    ) -> Dict[str, Any]:
        """Route de développement pour déboguer les tokens"""
        from app.core.security import jwt_manager

        # Extraction du token de l'en-tête
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

        if not token:
            return {"error": "Aucun token trouvé"}

        # Décodage du token (sans vérification de signature pour le debug)
        try:
            import jwt
            from app.core.config import settings

            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )

            return {
                "token_payload": payload,
                "current_user_id": str(current_user.id),
                "current_user_username": current_user.username,
                "token_length": len(token)
            }
        except Exception as e:
            return {"error": f"Erreur de décodage: {str(e)}"}