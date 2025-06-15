"""
Schémas Pydantic pour l'authentification
Validation et sérialisation des données d'auth
"""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator
from pydantic.config import ConfigDict

from app.schemas.user import UserProfile


# === SCHÉMAS DE BASE ===

class TokenData(BaseModel):
    """Données contenues dans un token JWT"""
    model_config = ConfigDict(from_attributes=True)

    sub: str = Field(..., description="Subject (User ID)")
    username: str = Field(..., description="Nom d'utilisateur")
    exp: datetime = Field(..., description="Date d'expiration")
    iat: datetime = Field(..., description="Date d'émission")
    type: str = Field(..., description="Type de token (access/refresh)")


class RefreshToken(BaseModel):
    """Token de rafraîchissement"""
    model_config = ConfigDict(from_attributes=True)

    refresh_token: str = Field(..., description="Token de rafraîchissement")


class MessageResponse(BaseModel):
    """Réponse avec message générique"""
    model_config = ConfigDict(from_attributes=True)

    message: str = Field(..., description="Message de réponse")
    details: Optional[Dict[str, Any]] = Field(None, description="Détails supplémentaires")


# === SCHÉMAS DE CONNEXION ===

class LoginRequest(BaseModel):
    """Requête de connexion"""
    model_config = ConfigDict(from_attributes=True)

    username_or_email: str = Field(
        ...,
        min_length=3,
        max_length=254,
        description="Nom d'utilisateur ou adresse email"
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Mot de passe"
    )
    remember_me: bool = Field(
        False,
        description="Se souvenir de moi (session persistante)"
    )

    @validator('username_or_email')
    def validate_username_or_email(cls, v):
        """Valide le format du nom d'utilisateur ou email"""
        v = v.strip().lower()
        if not v:
            raise ValueError("Nom d'utilisateur ou email requis")
        return v


class LoginResponse(BaseModel):
    """Réponse de connexion réussie"""
    model_config = ConfigDict(from_attributes=True)

    access_token: str = Field(..., description="Token d'accès JWT")
    refresh_token: str = Field(..., description="Token de rafraîchissement JWT")
    token_type: str = Field(default="bearer", description="Type de token")
    expires_in: int = Field(..., description="Durée de validité en secondes")
    user: UserProfile = Field(..., description="Profil de l'utilisateur connecté")


# === SCHÉMAS D'INSCRIPTION ===

class RegisterRequest(BaseModel):
    """Requête d'inscription"""
    model_config = ConfigDict(from_attributes=True)

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r'^[a-zA-Z0-9_-]+$',
        description="Nom d'utilisateur (lettres, chiffres, _ et - uniquement)"
    )
    email: EmailStr = Field(
        ...,
        description="Adresse email valide"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Mot de passe (minimum 8 caractères)"
    )
    password_confirm: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Confirmation du mot de passe"
    )
    full_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Nom complet (optionnel)"
    )
    accept_terms: bool = Field(
        ...,
        description="Acceptation des conditions d'utilisation"
    )

    @validator('username')
    def validate_username(cls, v):
        """Valide le nom d'utilisateur"""
        v = v.strip().lower()
        if not v:
            raise ValueError("Nom d'utilisateur requis")

        # Mots réservés
        reserved_words = [
            'admin', 'root', 'user', 'test', 'quantum', 'mastermind',
            'api', 'www', 'mail', 'ftp', 'localhost', 'null', 'undefined'
        ]
        if v in reserved_words:
            raise ValueError("Ce nom d'utilisateur est réservé")

        return v

    @validator('email')
    def validate_email(cls, v):
        """Valide et normalise l'email"""
        return v.lower().strip()

    @validator('password_confirm')
    def validate_password_confirm(cls, v, values):
        """Valide que les mots de passe correspondent"""
        if 'password' in values and v != values['password']:
            raise ValueError("Les mots de passe ne correspondent pas")
        return v

    @validator('accept_terms')
    def validate_terms(cls, v):
        """Valide l'acceptation des conditions"""
        if not v:
            raise ValueError("Vous devez accepter les conditions d'utilisation")
        return v

    @validator('full_name')
    def validate_full_name(cls, v):
        """Valide le nom complet"""
        if v:
            v = v.strip()
            if len(v) < 2:
                raise ValueError("Le nom complet doit faire au moins 2 caractères")
        return v


class RegisterResponse(BaseModel):
    """Réponse d'inscription"""
    model_config = ConfigDict(from_attributes=True)

    message: str = Field(..., description="Message de confirmation")
    user: UserProfile = Field(..., description="Profil de l'utilisateur créé")
    access_token: Optional[str] = Field(None, description="Token d'accès (si email vérifié)")
    refresh_token: Optional[str] = Field(None, description="Token de rafraîchissement (si email vérifié)")
    requires_email_verification: bool = Field(
        False,
        description="True si l'email doit être vérifié"
    )


# === SCHÉMAS DE GESTION DES MOTS DE PASSE ===

class PasswordChangeRequest(BaseModel):
    """Requête de changement de mot de passe"""
    model_config = ConfigDict(from_attributes=True)

    current_password: str = Field(
        ...,
        min_length=1,
        description="Mot de passe actuel"
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Nouveau mot de passe"
    )
    new_password_confirm: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Confirmation du nouveau mot de passe"
    )

    @validator('new_password_confirm')
    def validate_new_password_confirm(cls, v, values):
        """Valide que les nouveaux mots de passe correspondent"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError("Les nouveaux mots de passe ne correspondent pas")
        return v


class PasswordResetRequest(BaseModel):
    """Requête de réinitialisation de mot de passe"""
    model_config = ConfigDict(from_attributes=True)

    email: EmailStr = Field(
        ...,
        description="Adresse email pour la réinitialisation"
    )

    @validator('email')
    def validate_email(cls, v):
        """Valide et normalise l'email"""
        return v.lower().strip()


class PasswordResetConfirm(BaseModel):
    """Confirmation de réinitialisation de mot de passe"""
    model_config = ConfigDict(from_attributes=True)

    token: str = Field(
        ...,
        min_length=32,
        description="Token de réinitialisation"
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Nouveau mot de passe"
    )
    new_password_confirm: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Confirmation du nouveau mot de passe"
    )

    @validator('new_password_confirm')
    def validate_new_password_confirm(cls, v, values):
        """Valide que les nouveaux mots de passe correspondent"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError("Les nouveaux mots de passe ne correspondent pas")
        return v


# === SCHÉMAS DE VÉRIFICATION EMAIL ===

class EmailVerificationRequest(BaseModel):
    """Requête de vérification d'email"""
    model_config = ConfigDict(from_attributes=True)

    email: EmailStr = Field(
        ...,
        description="Adresse email à vérifier"
    )


class EmailVerificationConfirm(BaseModel):
    """Confirmation de vérification d'email"""
    model_config = ConfigDict(from_attributes=True)

    token: str = Field(
        ...,
        min_length=32,
        description="Token de vérification"
    )


# === SCHÉMAS DE TOKENS ===

class TokenRefreshRequest(BaseModel):
    """Requête de rafraîchissement de token"""
    model_config = ConfigDict(from_attributes=True)

    refresh_token: str = Field(
        ...,
        description="Token de rafraîchissement"
    )


class TokenRefreshResponse(BaseModel):
    """Réponse de rafraîchissement de token"""
    model_config = ConfigDict(from_attributes=True)

    access_token: str = Field(..., description="Nouveau token d'accès")
    refresh_token: str = Field(..., description="Nouveau token de rafraîchissement")
    token_type: str = Field(default="bearer", description="Type de token")
    expires_in: int = Field(..., description="Durée de validité en secondes")


class LogoutRequest(BaseModel):
    """Requête de déconnexion"""
    model_config = ConfigDict(from_attributes=True)

    refresh_token: Optional[str] = Field(
        None,
        description="Token de rafraîchissement à invalider"
    )
    logout_all_devices: bool = Field(
        False,
        description="Déconnecter de tous les appareils"
    )


# === SCHÉMAS DE VALIDATION ===

class PasswordStrengthResponse(BaseModel):
    """Réponse de validation de force de mot de passe"""
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool = Field(..., description="True si le mot de passe est valide")
    strength: str = Field(..., description="Force du mot de passe (faible/moyen/fort)")
    score: int = Field(..., description="Score de 0 à 7")
    errors: list[str] = Field(default_factory=list, description="Liste des erreurs")
    suggestions: list[str] = Field(default_factory=list, description="Suggestions d'amélioration")


class UsernameAvailabilityResponse(BaseModel):
    """Réponse de disponibilité de nom d'utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    username: str = Field(..., description="Nom d'utilisateur testé")
    available: bool = Field(..., description="True si disponible")
    message: str = Field(..., description="Message explicatif")
    suggestions: list[str] = Field(default_factory=list, description="Suggestions alternatives")


class EmailAvailabilityResponse(BaseModel):
    """Réponse de disponibilité d'email"""
    model_config = ConfigDict(from_attributes=True)

    email: str = Field(..., description="Email testé")
    available: bool = Field(..., description="True si disponible")
    message: str = Field(..., description="Message explicatif")


# === SCHÉMAS D'AUDIT ===

class LoginAttempt(BaseModel):
    """Tentative de connexion pour audit"""
    model_config = ConfigDict(from_attributes=True)

    username_or_email: str = Field(..., description="Identifiant utilisé")
    ip_address: str = Field(..., description="Adresse IP")
    user_agent: str = Field(..., description="User-Agent")
    success: bool = Field(..., description="True si connexion réussie")
    failure_reason: Optional[str] = Field(None, description="Raison de l'échec")
    timestamp: datetime = Field(..., description="Horodatage de la tentative")


class SessionInfo(BaseModel):
    """Informations de session"""
    model_config = ConfigDict(from_attributes=True)

    session_id: str = Field(..., description="ID de session")
    user_id: UUID = Field(..., description="ID de l'utilisateur")
    ip_address: str = Field(..., description="Adresse IP")
    user_agent: str = Field(..., description="User-Agent")
    created_at: datetime = Field(..., description="Date de création")
    last_activity: datetime = Field(..., description="Dernière activité")
    expires_at: datetime = Field(..., description="Date d'expiration")
    is_active: bool = Field(..., description="True si session active")


# === SCHÉMAS DE RÉPONSE D'ERREUR ===

class AuthErrorResponse(BaseModel):
    """Réponse d'erreur d'authentification"""
    model_config = ConfigDict(from_attributes=True)

    error: str = Field(..., description="Code d'erreur")
    message: str = Field(..., description="Message d'erreur")
    details: Optional[Dict[str, Any]] = Field(None, description="Détails de l'erreur")
    timestamp: datetime = Field(..., description="Horodatage de l'erreur")
    path: Optional[str] = Field(None, description="Chemin de la requête")


class ValidationErrorResponse(BaseModel):
    """Réponse d'erreur de validation"""
    model_config = ConfigDict(from_attributes=True)

    error: str = Field(default="VALIDATION_ERROR", description="Code d'erreur")
    message: str = Field(..., description="Message d'erreur principal")
    field_errors: Dict[str, list[str]] = Field(
        default_factory=dict,
        description="Erreurs par champ"
    )
    timestamp: datetime = Field(..., description="Horodatage de l'erreur")


# === SCHÉMAS DE CONFIGURATION ===

class AuthSettings(BaseModel):
    """Paramètres d'authentification exposés au client"""
    model_config = ConfigDict(from_attributes=True)

    registration_enabled: bool = Field(..., description="Inscription activée")
    email_verification_required: bool = Field(..., description="Vérification email requise")
    password_min_length: int = Field(..., description="Longueur minimum du mot de passe")
    password_require_uppercase: bool = Field(..., description="Majuscule requise")
    password_require_lowercase: bool = Field(..., description="Minuscule requise")
    password_require_digits: bool = Field(..., description="Chiffres requis")
    password_require_special: bool = Field(..., description="Caractères spéciaux requis")
    max_login_attempts: int = Field(..., description="Tentatives max avant verrouillage")
    lockout_duration_minutes: int = Field(..., description="Durée de verrouillage en minutes")


# === SCHÉMAS D'API PUBLIQUE ===

class PublicUserInfo(BaseModel):
    """Informations publiques d'un utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de l'utilisateur")
    username: str = Field(..., description="Nom d'utilisateur")
    full_name: Optional[str] = Field(None, description="Nom complet")
    avatar_url: Optional[str] = Field(None, description="URL de l'avatar")
    rank: str = Field(..., description="Rang actuel")
    total_games: int = Field(..., description="Nombre total de parties")
    quantum_points: int = Field(..., description="Points quantiques")
    created_at: datetime = Field(..., description="Date d'inscription")
    is_online: bool = Field(default=False, description="En ligne actuellement")


# === EXPORTS ===

__all__ = [
    # Tokens
    "TokenData", "RefreshToken",

    # Connexion
    "LoginRequest", "LoginResponse",

    # Inscription
    "RegisterRequest", "RegisterResponse",

    # Mots de passe
    "PasswordChangeRequest", "PasswordResetRequest", "PasswordResetConfirm",

    # Email
    "EmailVerificationRequest", "EmailVerificationConfirm",

    # Tokens
    "TokenRefreshRequest", "TokenRefreshResponse", "LogoutRequest",

    # Validation
    "PasswordStrengthResponse", "UsernameAvailabilityResponse",
    "EmailAvailabilityResponse",

    # Audit
    "LoginAttempt", "SessionInfo",

    # Erreurs
    "AuthErrorResponse", "ValidationErrorResponse",

    # Configuration
    "AuthSettings",

    # Public
    "PublicUserInfo",

    # Générique
    "MessageResponse"
]