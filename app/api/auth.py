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

        # Définir des cookies sécurisés si remember_me
        if login_data.remember_me:
            response.set_cookie(
                key="refresh_token",
                value=login_response.refresh_token,
                max_age=settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 60 * 60,
                httponly=True,
                secure=settings.ENVIRONMENT == "production",
                samesite="lax"
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
    - **full_name**: Nom complet (optionnel)
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
    response_model=TokenRefreshResponse,
    summary="Rafraîchir le token",
    description="Génère un nouveau token d'accès à partir du refresh token"
)
async def refresh_token(
        token_request: TokenRefreshRequest,
        client_info: Dict[str, Any] = Depends(get_client_info),
        db: AsyncSession = Depends(get_database)
) -> TokenRefreshResponse:
    """
    Rafraîchit un token d'accès

    - **refresh_token**: Token de rafraîchissement valide
    """
    try:
        token_data = await auth_service.refresh_access_token(
            db, token_request.refresh_token, client_info
        )
        return TokenRefreshResponse(**token_data)

    except AuthenticationError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du rafraîchissement du token"
        )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Déconnexion",
    description="Déconnecte l'utilisateur et invalide les tokens"
)
async def logout(
        logout_request: LogoutRequest,
        response: Response,
        current_user: User = Depends(get_current_active_user),
        client_info: Dict[str, Any] = Depends(get_client_info),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Déconnecte l'utilisateur actuel

    - **refresh_token**: Token de rafraîchissement à invalider (optionnel)
    - **logout_all_devices**: Déconnecter de tous les appareils
    """
    try:
        # TODO: Récupérer le token actuel de l'en-tête Authorization
        current_token = "token_from_header"  # À implémenter

        result = await auth_service.logout_user(
            db, current_user.id, current_token, client_info
        )

        # Supprimer les cookies
        response.delete_cookie(key="refresh_token")

        return MessageResponse(
            message=result["message"],
            details={"user_id": str(current_user.id)}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la déconnexion"
        )


# === ROUTES DE GESTION DES MOTS DE PASSE ===

@router.post(
    "/password/change",
    response_model=MessageResponse,
    summary="Changer le mot de passe",
    description="Change le mot de passe de l'utilisateur connecté"
)
async def change_password(
        password_data: PasswordChangeRequest,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Change le mot de passe de l'utilisateur connecté

    - **current_password**: Mot de passe actuel
    - **new_password**: Nouveau mot de passe
    - **new_password_confirm**: Confirmation du nouveau mot de passe
    """
    try:
        result = await auth_service.change_password(
            db, current_user.id, password_data
        )
        return MessageResponse(**result)

    except (AuthenticationError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du changement de mot de passe"
        )


@router.post(
    "/password/reset",
    response_model=MessageResponse,
    summary="Demander une réinitialisation",
    description="Envoie un email de réinitialisation de mot de passe"
)
async def reset_password(
        reset_data: PasswordResetRequest,
        client_info: Dict[str, Any] = Depends(get_client_info),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Initie une réinitialisation de mot de passe

    - **email**: Adresse email pour la réinitialisation
    """
    try:
        result = await auth_service.reset_password_request(
            db, reset_data, client_info
        )
        return MessageResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la demande de réinitialisation"
        )


@router.post(
    "/password/reset/confirm",
    response_model=MessageResponse,
    summary="Confirmer la réinitialisation",
    description="Confirme la réinitialisation avec un token"
)
async def confirm_password_reset(
        confirm_data: PasswordResetConfirm,
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Confirme la réinitialisation de mot de passe

    - **token**: Token de réinitialisation reçu par email
    - **new_password**: Nouveau mot de passe
    - **new_password_confirm**: Confirmation du nouveau mot de passe
    """
    try:
        # TODO: Implémenter la confirmation de réinitialisation
        return MessageResponse(
            message="Mot de passe réinitialisé avec succès",
            details={"token_used": confirm_data.token[:8] + "..."}
        )

    except ValidationError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la réinitialisation"
        )


# === ROUTES DE VALIDATION ===

@router.post(
    "/validate/password",
    response_model=PasswordStrengthResponse,
    summary="Valider la force d'un mot de passe",
    description="Évalue la sécurité d'un mot de passe"
)
async def validate_password(
        password: str
) -> PasswordStrengthResponse:
    """
    Valide la force d'un mot de passe

    - **password**: Mot de passe à évaluer
    """
    validation_result = password_manager.validate_password_strength(password)

    suggestions = []
    if not validation_result["is_valid"]:
        if len(password) < 8:
            suggestions.append("Utilisez au moins 8 caractères")
        if not any(c.isupper() for c in password):
            suggestions.append("Ajoutez au moins une majuscule")
        if not any(c.islower() for c in password):
            suggestions.append("Ajoutez au moins une minuscule")
        if not any(c.isdigit() for c in password):
            suggestions.append("Ajoutez au moins un chiffre")
        if not any(c in "!@#$%^&*(),.?\":{}|<>" for c in password):
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
    description="Récupère le profil de l'utilisateur actuellement connecté"
)
async def get_current_user_profile(
        current_user: User = Depends(get_current_active_user)
) -> UserProfile:
    """
    Récupère le profil de l'utilisateur connecté

    Nécessite un token d'authentification valide
    """
    return UserProfile.model_validate(current_user)


@router.get(
    "/settings",
    response_model=AuthSettings,
    summary="Paramètres d'authentification",
    description="Récupère les paramètres publics d'authentification"
)
async def get_auth_settings() -> AuthSettings:
    """
    Récupère les paramètres d'authentification du système

    Accessible sans authentification
    """
    return AuthSettings(
        registration_enabled=settings.ENABLE_REGISTRATION,
        email_verification_required=settings.ENABLE_EMAIL_VERIFICATION,
        password_min_length=security_config.PASSWORD_MIN_LENGTH,
        password_require_uppercase=security_config.PASSWORD_REQUIRE_UPPERCASE,
        password_require_lowercase=security_config.PASSWORD_REQUIRE_LOWERCASE,
        password_require_digits=security_config.PASSWORD_REQUIRE_DIGITS,
        password_require_special=security_config.PASSWORD_REQUIRE_SPECIAL,
        max_login_attempts=security_config.MAX_LOGIN_ATTEMPTS,
        lockout_duration_minutes=security_config.LOCKOUT_DURATION_MINUTES
    )


# === ROUTES DE VÉRIFICATION EMAIL ===

@router.post(
    "/email/verify",
    response_model=MessageResponse,
    summary="Demander une vérification d'email",
    description="Envoie un email de vérification"
)
async def request_email_verification(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Demande une vérification d'email pour l'utilisateur connecté

    Envoie un nouveau lien de vérification si l'email n'est pas encore vérifié
    """
    if current_user.is_verified:
        return MessageResponse(
            message="Email déjà vérifié",
            details={"verified_at": current_user.email_verified_at.isoformat() if current_user.email_verified_at else None}
        )

    # TODO: Générer et envoyer le lien de vérification
    # Pour l'instant, simulation

    return MessageResponse(
        message="Email de vérification envoyé",
        details={"email": current_user.email}
    )


@router.get(
    "/email/verify/{token}",
    response_model=MessageResponse,
    summary="Vérifier l'email",
    description="Vérifie l'email avec un token"
)
async def verify_email(
        token: str,
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Vérifie l'email avec un token de vérification

    - **token**: Token de vérification reçu par email
    """
    try:
        result = await auth_service.verify_email(db, token)
        return MessageResponse(**result)

    except ValidationError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la vérification de l'email"
        )


# === ROUTES DE DEBUG (développement uniquement) ===

@router.post(
    "/debug/generate-password",
    response_model=Dict[str, str],
    summary="Générer un mot de passe sécurisé (DEBUG)",
    description="Génère un mot de passe aléatoire sécurisé",
    include_in_schema=settings.DEBUG
)
async def generate_secure_password(
        length: int = 16
) -> Dict[str, str]:
    """
    Génère un mot de passe sécurisé aléatoire

    Disponible uniquement en mode développement
    """
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Route non disponible en production"
        )

    if length < 8 or length > 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La longueur doit être entre 8 et 64 caractères"
        )

    password = password_manager.generate_secure_password(length)
    validation = password_manager.validate_password_strength(password)

    return {
        "password": password,
        "strength": validation["strength"],
        "score": str(validation["score"])
    }


@router.get(
    "/debug/token-info",
    response_model=Dict[str, Any],
    summary="Informations sur le token (DEBUG)",
    description="Affiche les informations du token actuel",
    include_in_schema=settings.DEBUG
)
async def debug_token_info(
        current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Affiche les informations sur le token actuel

    Disponible uniquement en mode développement
    """
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Route non disponible en production"
        )

    # TODO: Extraire les informations du token JWT actuel
    return {
        "user_id": str(current_user.id),
        "username": current_user.username,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "is_superuser": current_user.is_superuser,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "created_at": current_user.created_at.isoformat()
    }


# === ROUTES DE HEALTH CHECK ===

@router.get(
    "/health",
    response_model=Dict[str, Any],
    summary="État de santé de l'authentification",
    description="Vérifie l'état des services d'authentification"
)
async def auth_health_check(
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Vérifie l'état de santé des services d'authentification

    Accessible sans authentification
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": "unknown",
            "jwt": "healthy",
            "password_hashing": "healthy"
        }
    }

    # Test de la base de données
    try:
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        health_status["services"]["database"] = "healthy"
    except Exception:
        health_status["services"]["database"] = "unhealthy"
        health_status["status"] = "degraded"

    # Test JWT
    try:
        test_token = jwt_manager.create_access_token({"sub": "test"})
        jwt_manager.verify_token(test_token)
        health_status["services"]["jwt"] = "healthy"
    except Exception:
        health_status["services"]["jwt"] = "unhealthy"
        health_status["status"] = "degraded"

    # Test hachage de mot de passe
    try:
        test_hash = password_manager.get_password_hash("test123")
        password_manager.verify_password("test123", test_hash)
        health_status["services"]["password_hashing"] = "healthy"
    except Exception:
        health_status["services"]["password_hashing"] = "unhealthy"
        health_status["status"] = "degraded"

    return health_status