"""
Routes d'authentification pour Quantum Mastermind
Login, register, reset password, token management
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_database, get_client_info, get_current_user,
    get_current_active_user, create_http_exception_from_error
)
from app.models.user import User
from app.services.auth import auth_service
from app.core.config import settings, security_config
from app.core.security import password_manager, secure_generator
from app.schemas.auth import (
    LoginRequest, LoginResponse, RegisterRequest, RegisterResponse,
    PasswordResetRequest, PasswordResetConfirm, PasswordChangeRequest,
    RefreshToken, TokenData, MessageResponse, TokenRefreshRequest,
    TokenRefreshResponse, LogoutRequest, PasswordStrengthResponse,
    UsernameAvailabilityResponse, EmailAvailabilityResponse, AuthSettings
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
        request: Request,
        response: Response,
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

        # Définir des cookies sécurisés pour le refresh token si remember_me
        if login_data.remember_me:
            response.set_cookie(
                key="refresh_token",
                value=login_response.refresh_token,
                max_age=settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 3600,
                httponly=True,
                secure=settings.ENVIRONMENT == "production",
                samesite="strict"
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

    - **username**: Nom d'utilisateur unique
    - **email**: Adresse email unique
    - **password**: Mot de passe sécurisé
    - **password_confirm**: Confirmation du mot de passe
    """
    try:
        register_response = await auth_service.register_user(
            db, register_data, client_info
        )
        return register_response

    except (ValidationError, AuthenticationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'inscription"
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Déconnexion utilisateur",
    description="Déconnecte l'utilisateur et invalide ses tokens"
)
async def logout(
        logout_data: LogoutRequest,
        response: Response,
        current_user: User = Depends(get_current_user),
        client_info: Dict[str, Any] = Depends(get_client_info),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Déconnecte l'utilisateur et invalide ses tokens

    - **refresh_token**: Token de rafraîchissement à invalider
    - **logout_all_devices**: Déconnecter de tous les appareils
    """
    try:
        await auth_service.logout_user(
            db, current_user.id, logout_data, client_info
        )

        # Supprimer le cookie refresh_token
        response.delete_cookie(
            key="refresh_token",
            httponly=True,
            secure=settings.ENVIRONMENT == "production",
            samesite="strict"
        )

        return MessageResponse(
            message="Déconnexion réussie",
            details={"logout_all_devices": logout_data.logout_all_devices}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la déconnexion"
        )


# === ROUTES DE GESTION DES TOKENS ===

@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    summary="Rafraîchir le token d'accès",
    description="Génère un nouveau token d'accès à partir du refresh token"
)
async def refresh_token(
        refresh_data: TokenRefreshRequest,
        client_info: Dict[str, Any] = Depends(get_client_info),
        db: AsyncSession = Depends(get_database)
) -> TokenRefreshResponse:
    """
    Rafraîchit le token d'accès

    - **refresh_token**: Token de rafraîchissement valide
    """
    try:
        refresh_response = await auth_service.refresh_access_token(
            db, refresh_data.refresh_token, client_info
        )
        return refresh_response

    except AuthenticationError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du rafraîchissement du token"
        )


# === ROUTES DE GESTION DU MOT DE PASSE ===

@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Changer le mot de passe",
    description="Change le mot de passe de l'utilisateur connecté"
)
async def change_password(
        password_data: PasswordChangeRequest,
        current_user: User = Depends(get_current_active_user),
        client_info: Dict[str, Any] = Depends(get_client_info),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Change le mot de passe de l'utilisateur connecté

    - **current_password**: Mot de passe actuel
    - **new_password**: Nouveau mot de passe
    - **new_password_confirm**: Confirmation du nouveau mot de passe
    """
    try:
        await auth_service.change_user_password(
            db, current_user.id, password_data, client_info
        )

        return MessageResponse(
            message="Mot de passe modifié avec succès",
            details={"user_id": str(current_user.id)}
        )

    except (AuthenticationError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du changement de mot de passe"
        )


@router.post(
    "/reset-password-request",
    response_model=MessageResponse,
    summary="Demander la réinitialisation du mot de passe",
    description="Envoie un email de réinitialisation de mot de passe"
)
async def request_password_reset(
        reset_data: PasswordResetRequest,
        client_info: Dict[str, Any] = Depends(get_client_info),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Demande la réinitialisation du mot de passe

    - **email**: Adresse email du compte à réinitialiser
    """
    try:
        await auth_service.request_password_reset(
            db, reset_data.email, client_info
        )

        return MessageResponse(
            message="Si cette adresse email existe, un lien de réinitialisation a été envoyé",
            details={"email": reset_data.email}
        )

    except Exception as e:
        # On ne révèle pas si l'email existe ou non pour des raisons de sécurité
        return MessageResponse(
            message="Si cette adresse email existe, un lien de réinitialisation a été envoyé",
            details={"email": reset_data.email}
        )


@router.post(
    "/reset-password-confirm",
    response_model=MessageResponse,
    summary="Confirmer la réinitialisation du mot de passe",
    description="Réinitialise le mot de passe avec le token reçu"
)
async def confirm_password_reset(
        reset_data: PasswordResetConfirm,
        client_info: Dict[str, Any] = Depends(get_client_info),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Confirme la réinitialisation du mot de passe

    - **token**: Token de réinitialisation reçu par email
    - **new_password**: Nouveau mot de passe
    - **new_password_confirm**: Confirmation du nouveau mot de passe
    """
    try:
        await auth_service.confirm_password_reset(
            db, reset_data, client_info
        )

        return MessageResponse(
            message="Mot de passe réinitialisé avec succès",
            details={}
        )

    except (AuthenticationError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la réinitialisation du mot de passe"
        )


# === ROUTES DE VALIDATION ===

@router.post(
    "/validate/password",
    response_model=PasswordStrengthResponse,
    summary="Valider la force d'un mot de passe",
    description="Valide la force et la conformité d'un mot de passe"
)
async def validate_password_strength(
        password: str
) -> PasswordStrengthResponse:
    """
    Valide la force d'un mot de passe

    - **password**: Mot de passe à valider
    """
    validation_result = password_manager.validate_password_strength(password)

    # Génération de suggestions basées sur la validation
    suggestions = []
    if validation_result["score"] < 4:
        if len(password) < settings.PASSWORD_MIN_LENGTH:
            suggestions.append(f"Utilisez au moins {settings.PASSWORD_MIN_LENGTH} caractères")
        if not any(c.isupper() for c in password):
            suggestions.append("Ajoutez une lettre majuscule")
        if not any(c.islower() for c in password):
            suggestions.append("Ajoutez une lettre minuscule")
        if not any(c.isdigit() for c in password):
            suggestions.append("Ajoutez un chiffre")
        if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?\":{}|<>" for c in password):
            suggestions.append("Ajoutez un caractère spécial")

    return PasswordStrengthResponse(
        is_valid=validation_result["is_valid"],
        strength=validation_result["strength"],
        score=validation_result["score"],
        errors=validation_result["errors"],
        suggestions=suggestions
    )


@router.get(
    "/validate/username/{username}",
    response_model=UsernameAvailabilityResponse,
    summary="Vérifier la disponibilité d'un nom d'utilisateur",
    description="Vérifie si un nom d'utilisateur est disponible"
)
async def check_username_availability(
        username: str,
        db: AsyncSession = Depends(get_database)
) -> UsernameAvailabilityResponse:
    """
    Vérifie la disponibilité d'un nom d'utilisateur

    - **username**: Nom d'utilisateur à vérifier
    """
    from app.repositories.user import UserRepository

    user_repo = UserRepository()

    # Vérifier si l'utilisateur existe
    existing_user = await user_repo.get_by_username(db, username)
    available = existing_user is None

    # Générer des suggestions si non disponible
    suggestions = []
    if not available:
        for i in range(1, 4):
            suggestions.append(f"{username}{i}")
            suggestions.append(f"{username}_{secure_generator.generate_verification_code(2)}")

    message = "Nom d'utilisateur disponible" if available else "Nom d'utilisateur déjà pris"

    return UsernameAvailabilityResponse(
        username=username,
        available=available,
        message=message,
        suggestions=suggestions
    )


@router.get(
    "/validate/email/{email}",
    response_model=EmailAvailabilityResponse,
    summary="Vérifier la disponibilité d'un email",
    description="Vérifie si une adresse email est disponible"
)
async def check_email_availability(
        email: str,
        db: AsyncSession = Depends(get_database)
) -> EmailAvailabilityResponse:
    """
    Vérifie la disponibilité d'une adresse email

    - **email**: Adresse email à vérifier
    """
    from app.repositories.user import UserRepository

    user_repo = UserRepository()

    # Vérifier si l'email existe
    existing_user = await user_repo.get_by_email(db, email)
    available = existing_user is None

    message = "Adresse email disponible" if available else "Adresse email déjà utilisée"

    return EmailAvailabilityResponse(
        email=email,
        available=available,
        message=message
    )


# === ROUTES D'INFORMATION ===

@router.get(
    "/me",
    response_model=UserProfile,
    summary="Profil de l'utilisateur connecté",
    description="Récupère le profil de l'utilisateur connecté"
)
async def get_current_user_profile(
        current_user: User = Depends(get_current_active_user)
) -> UserProfile:
    """
    Récupère le profil de l'utilisateur connecté

    Nécessite une authentification valide
    """
    return UserProfile.model_validate(current_user)


@router.get(
    "/settings",
    response_model=AuthSettings,
    summary="Paramètres d'authentification",
    description="Récupère les paramètres de sécurité de l'application"
)
async def get_auth_settings() -> AuthSettings:
    """
    Récupère les paramètres d'authentification publics

    Utile pour configurer l'interface utilisateur
    """
    return AuthSettings(
        password_min_length=settings.PASSWORD_MIN_LENGTH,
        password_require_uppercase=settings.PASSWORD_REQUIRE_UPPERCASE,
        password_require_lowercase=settings.PASSWORD_REQUIRE_LOWERCASE,
        password_require_numbers=settings.PASSWORD_REQUIRE_NUMBERS,
        password_require_symbols=settings.PASSWORD_REQUIRE_SYMBOLS,
        max_login_attempts=settings.MAX_LOGIN_ATTEMPTS,
        lockout_duration=settings.LOCKOUT_DURATION_MINUTES
    )


# === ROUTES DE VÉRIFICATION EMAIL ===

@router.post(
    "/verify-email-request",
    response_model=MessageResponse,
    summary="Demander la vérification d'email",
    description="Envoie un nouvel email de vérification"
)
async def request_email_verification(
        current_user: User = Depends(get_current_user),
        client_info: Dict[str, Any] = Depends(get_client_info),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Demande un nouvel email de vérification

    Nécessite une authentification valide
    """
    try:
        if current_user.is_verified:
            return MessageResponse(
                message="Email déjà vérifié",
                details={"email": current_user.email}
            )

        await auth_service.request_email_verification(
            db, current_user.id, client_info
        )

        return MessageResponse(
            message="Email de vérification envoyé",
            details={"email": current_user.email}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'envoi de l'email de vérification"
        )


@router.post(
    "/verify-email-confirm/{token}",
    response_model=MessageResponse,
    summary="Confirmer la vérification d'email",
    description="Vérifie l'email avec le token reçu"
)
async def confirm_email_verification(
        token: str,
        client_info: Dict[str, Any] = Depends(get_client_info),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Confirme la vérification d'email

    - **token**: Token de vérification reçu par email
    """
    try:
        user = await auth_service.confirm_email_verification(
            db, token, client_info
        )

        return MessageResponse(
            message="Email vérifié avec succès",
            details={"user_id": str(user.id), "email": user.email}
        )

    except AuthenticationError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la vérification de l'email"
        )