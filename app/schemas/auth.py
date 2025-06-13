"""
Schémas Pydantic pour l'authentification
Validation des données de login, tokens, et sécurité
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator


# === SCHÉMAS DE BASE ===
class TokenBase(BaseModel):
    """Schéma de base pour les tokens"""
    access_token: str
    token_type: str = "bearer"


class Token(TokenBase):
    """Token complet avec refresh"""
    refresh_token: Optional[str] = None
    expires_in: int  # en secondes


class TokenData(BaseModel):
    """Données contenues dans un token"""
    user_id: UUID
    username: str
    email: str
    is_verified: bool
    is_superuser: bool = False
    exp: datetime
    jti: str  # JWT ID


class RefreshToken(BaseModel):
    """Schéma pour le refresh token"""
    refresh_token: str


# === SCHÉMAS DE LOGIN ===
class LoginRequest(BaseModel):
    """Requête de connexion"""
    username_or_email: str = Field(
        ...,
        min_length=3,
        max_length=254,
        description="Nom d'utilisateur ou email"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Mot de passe"
    )
    remember_me: bool = Field(
        default=False,
        description="Session persistante"
    )

    @validator('username_or_email')
    def validate_username_or_email(cls, v):
        v = v.strip().lower()
        if not v:
            raise ValueError("Nom d'utilisateur ou email requis")
        return v

    @validator('password')
    def validate_password(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Mot de passe requis")
        return v


class LoginResponse(BaseModel):
    """Réponse de connexion réussie"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserProfile"  # Forward reference

    class Config:
        from_attributes = True


# === SCHÉMAS D'INSCRIPTION ===
class RegisterRequest(BaseModel):
    """Requête d'inscription"""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        regex=r'^[a-zA-Z0-9_-]+$',
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
        description="Confirmation du mot de passe"
    )
    accept_terms: bool = Field(
        ...,
        description="Acceptation des conditions d'utilisation"
    )

    @validator('username')
    def validate_username(cls, v):
        v = v.strip()

        # Mots réservés
        reserved = ['admin', 'root', 'system', 'quantum', 'mastermind', 'api', 'www']
        if v.lower() in reserved:
            raise ValueError("Nom d'utilisateur réservé")

        return v

    @validator('password')
    def validate_password_strength(cls, v):
        """Validation de la force du mot de passe"""
        errors = []

        if len(v) < 8:
            errors.append("Minimum 8 caractères")

        if not any(c.isupper() for c in v):
            errors.append("Au moins une majuscule")

        if not any(c.islower() for c in v):
            errors.append("Au moins une minuscule")

        if not any(c.isdigit() for c in v):
            errors.append("Au moins un chiffre")

        if not any(c in '!@#$%^&*(),.?":{}|<>' for c in v):
            errors.append("Au moins un caractère spécial")

        # Mots de passe courants
        common = ['password', '123456', 'password123', 'qwerty', 'letmein']
        if v.lower() in common:
            errors.append("Mot de passe trop commun")

        if errors:
            raise ValueError("; ".join(errors))

        return v

    @validator('password_confirm')
    def validate_password_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError("Les mots de passe ne correspondent pas")
        return v

    @validator('accept_terms')
    def validate_terms_accepted(cls, v):
        if not v:
            raise ValueError("Vous devez accepter les conditions d'utilisation")
        return v


class RegisterResponse(BaseModel):
    """Réponse d'inscription réussie"""
    message: str
    user_id: UUID
    email_verification_required: bool = True

    class Config:
        from_attributes = True


# === SCHÉMAS DE RÉINITIALISATION ===
class PasswordResetRequest(BaseModel):
    """Demande de réinitialisation de mot de passe"""
    email: EmailStr = Field(
        ...,
        description="Adresse email du compte"
    )


class PasswordResetConfirm(BaseModel):
    """Confirmation de réinitialisation de mot de passe"""
    token: str = Field(
        ...,
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
        description="Confirmation du nouveau mot de passe"
    )

    @validator('new_password')
    def validate_password_strength(cls, v):
        # Même validation que pour l'inscription
        return RegisterRequest.validate_password_strength(v)

    @validator('new_password_confirm')
    def validate_password_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError("Les mots de passe ne correspondent pas")
        return v


class PasswordChangeRequest(BaseModel):
    """Changement de mot de passe (utilisateur connecté)"""
    current_password: str = Field(
        ...,
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
        description="Confirmation du nouveau mot de passe"
    )

    @validator('new_password')
    def validate_password_strength(cls, v):
        return RegisterRequest.validate_password_strength(v)

    @validator('new_password_confirm')
    def validate_password_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError("Les mots de passe ne correspondent pas")
        return v


# === SCHÉMAS DE VÉRIFICATION EMAIL ===
class EmailVerificationRequest(BaseModel):
    """Demande de vérification d'email"""
    email: EmailStr = Field(
        ...,
        description="Adresse email à vérifier"
    )


class EmailVerificationConfirm(BaseModel):
    """Confirmation de vérification d'email"""
    token: str = Field(
        ...,
        description="Token de vérification"
    )


# === SCHÉMAS DE SÉCURITÉ ===
class SecurityEvent(BaseModel):
    """Événement de sécurité"""
    event_type: str
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    severity: str = "INFO"  # INFO, WARNING, ERROR, CRITICAL

    class Config:
        from_attributes = True


class LoginAttempt(BaseModel):
    """Tentative de connexion"""
    username: str
    ip_address: str
    user_agent: str
    success: bool
    failure_reason: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class AccountSecurity(BaseModel):
    """Informations de sécurité du compte"""
    failed_login_attempts: int
    last_login: Optional[datetime] = None
    last_ip_address: Optional[str] = None
    is_locked: bool
    locked_until: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None
    login_count: int

    class Config:
        from_attributes = True


# === SCHÉMAS DE VALIDATION ===
class PasswordStrengthCheck(BaseModel):
    """Vérification de la force d'un mot de passe"""
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Mot de passe à vérifier"
    )


class PasswordStrengthResponse(BaseModel):
    """Réponse de vérification de force"""
    is_valid: bool
    strength_score: int  # 0-100
    errors: List[str]
    suggestions: List[str]


class UsernameAvailability(BaseModel):
    """Vérification de disponibilité du nom d'utilisateur"""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Nom d'utilisateur à vérifier"
    )


class UsernameAvailabilityResponse(BaseModel):
    """Réponse de disponibilité"""
    available: bool
    suggestions: List[str] = []


class EmailAvailability(BaseModel):
    """Vérification de disponibilité de l'email"""
    email: EmailStr = Field(
        ...,
        description="Email à vérifier"
    )


class EmailAvailabilityResponse(BaseModel):
    """Réponse de disponibilité email"""
    available: bool


# === SCHÉMAS DE RÉPONSE GÉNÉRIQUES ===
class MessageResponse(BaseModel):
    """Réponse avec message simple"""
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Réponse d'erreur"""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    code: Optional[str] = None


class SuccessResponse(BaseModel):
    """Réponse de succès"""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None


# === IMPORT POUR FORWARD REFERENCE ===
# Ceci sera défini dans user.py
from .user import UserProfile

# Mise à jour des forward references
LoginResponse.model_rebuild()