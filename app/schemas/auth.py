"""
Schémas Pydantic pour l'authentification
Validation et sérialisation des données d'auth
"""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict

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

    @field_validator('username_or_email')
    @classmethod
    def validate_username_or_email(cls, v: str) -> str:
        """Valide le format du nom d'utilisateur ou email"""
        v = v.strip().lower()
        if not v:
            raise ValueError("Nom d'utilisateur ou email requis")
        return v


class LoginResponse(BaseModel):
    """Réponse de connexion réussie"""
    model_config = ConfigDict(from_attributes=True)

    access_token: str = Field(..., description="Token d'accès JWT")
    refresh_token: str = Field(..., description="Token de rafraîchissement")
    token_type: str = Field(default="bearer", description="Type de token")
    expires_in: int = Field(..., description="Durée de validité en secondes")
    user: UserProfile = Field(..., description="Profil utilisateur")


# === SCHÉMAS D'INSCRIPTION ===

class RegisterRequest(BaseModel):
    """Requête d'inscription"""
    model_config = ConfigDict(from_attributes=True)

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Nom d'utilisateur"
    )
    email: EmailStr = Field(
        ...,
        description="Adresse email"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Mot de passe"
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
        description="Nom complet"
    )
    accept_terms: bool = Field(
        ...,
        description="Acceptation des conditions d'utilisation"
    )

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Valide le nom d'utilisateur"""
        v = v.strip().lower()
        if not v:
            raise ValueError("Nom d'utilisateur requis")
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError("Nom d'utilisateur doit être alphanumérique (- et _ autorisés)")
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Valide et normalise l'email"""
        return v.lower().strip()

    @field_validator('password_confirm')
    @classmethod
    def validate_password_confirm(cls, v: str, info) -> str:
        """Valide que les mots de passe correspondent"""
        if 'password' in info.data and v != info.data['password']:
            raise ValueError("Les mots de passe ne correspondent pas")
        return v

    @field_validator('accept_terms')
    @classmethod
    def validate_accept_terms(cls, v: bool) -> bool:
        """Valide que les conditions sont acceptées"""
        if not v:
            raise ValueError("Vous devez accepter les conditions d'utilisation")
        return v


class RegisterResponse(BaseModel):
    """Réponse d'inscription réussie"""
    model_config = ConfigDict(from_attributes=True)

    message: str = Field(..., description="Message de confirmation")
    user: UserProfile = Field(..., description="Profil utilisateur créé")
    access_token: Optional[str] = Field(
        None,
        description="Token d'accès JWT"
    )
    refresh_token: Optional[str] = Field(
        None,
        description="Token de rafraîchissement"
    )
    requires_email_verification: bool = Field(
        default=True,
        description="Email de vérification requis"
    )


# === SCHÉMAS DE CHANGEMENT DE MOT DE PASSE ===

class PasswordChangeRequest(BaseModel):
    """Requête de changement de mot de passe"""
    model_config = ConfigDict(from_attributes=True)

    current_password: str = Field(
        ...,
        min_length=1,
        max_length=128,
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

    @field_validator('new_password_confirm')
    @classmethod
    def validate_new_password_confirm(cls, v: str, info) -> str:
        """Valide que les nouveaux mots de passe correspondent"""
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError("Les nouveaux mots de passe ne correspondent pas")
        return v


# === SCHÉMAS DE RÉINITIALISATION ===

class PasswordResetRequest(BaseModel):
    """Requête de réinitialisation de mot de passe"""
    model_config = ConfigDict(from_attributes=True)

    email: EmailStr = Field(
        ...,
        description="Adresse email pour la réinitialisation"
    )

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
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

    @field_validator('new_password_confirm')
    @classmethod
    def validate_new_password_confirm(cls, v: str, info) -> str:
        """Valide que les nouveaux mots de passe correspondent"""
        if 'new_password' in info.data and v != info.data['new_password']:
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
    user_agent: str = Field(..., description="User Agent du navigateur")
    success: bool = Field(..., description="Connexion réussie")
    timestamp: datetime = Field(..., description="Horodatage")


class AuthSettings(BaseModel):
    """Paramètres d'authentification"""
    model_config = ConfigDict(from_attributes=True)

    password_min_length: int = Field(..., description="Longueur minimale du mot de passe")
    password_require_uppercase: bool = Field(..., description="Majuscule requise")
    password_require_lowercase: bool = Field(..., description="Minuscule requise")
    password_require_numbers: bool = Field(..., description="Chiffres requis")
    password_require_symbols: bool = Field(..., description="Symboles requis")
    max_login_attempts: int = Field(..., description="Nombre max de tentatives")
    lockout_duration: int = Field(..., description="Durée de verrouillage en minutes")