"""
Schémas Pydantic pour l'authentification
Validation des données de login, tokens, et sécurité
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


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

    @field_validator('username_or_email')
    @classmethod
    def validate_username_or_email(cls, v):
        v = v.strip().lower()
        if not v:
            raise ValueError("Nom d'utilisateur ou email requis")
        return v

    @field_validator('password')
    @classmethod
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

    model_config = {"from_attributes": True}


# === SCHÉMAS D'INSCRIPTION ===
class RegisterRequest(BaseModel):
    """Requête d'inscription"""
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
        description="Mot de passe fort requis"
    )
    password_confirm: str = Field(
        ...,
        description="Confirmation du mot de passe"
    )
    accept_terms: bool = Field(
        ...,
        description="Acceptation des conditions d'utilisation"
    )
    newsletter_opt_in: bool = Field(
        default=False,
        description="Opt-in pour la newsletter"
    )

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        """Validation renforcée du mot de passe"""
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

        if errors:
            raise ValueError("; ".join(errors))
        return v

    @field_validator('password_confirm')
    @classmethod
    def validate_password_match(cls, v, info):
        """Valide que les mots de passe correspondent"""
        data = info.data
        if 'password' in data and v != data['password']:
            raise ValueError("Les mots de passe ne correspondent pas")
        return v

    @field_validator('accept_terms')
    @classmethod
    def validate_terms_accepted(cls, v):
        """Valide l'acceptation des conditions"""
        if not v:
            raise ValueError("Vous devez accepter les conditions d'utilisation")
        return v


class RegisterResponse(BaseModel):
    """Réponse d'inscription réussie"""
    message: str
    user_id: UUID
    email_verification_required: bool
    verification_sent_to: str


# === SCHÉMAS DE RÉINITIALISATION MOT DE PASSE ===
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
        min_length=32,
        max_length=256,
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

    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v):
        # Même validation que pour l'inscription
        return RegisterRequest.validate_password_strength(v)

    @field_validator('new_password_confirm')
    @classmethod
    def validate_password_match(cls, v, info):
        data = info.data
        if 'new_password' in data and v != data['new_password']:
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

    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v):
        return RegisterRequest.validate_password_strength(v)

    @field_validator('new_password_confirm')
    @classmethod
    def validate_password_match(cls, v, info):
        data = info.data
        if 'new_password' in data and v != data['new_password']:
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
        min_length=32,
        max_length=256,
        description="Token de vérification"
    )


class EmailChangeRequest(BaseModel):
    """Demande de changement d'email"""
    new_email: EmailStr = Field(
        ...,
        description="Nouvelle adresse email"
    )
    password: str = Field(
        ...,
        description="Mot de passe actuel pour confirmation"
    )


# === SCHÉMAS DE SÉCURITÉ AVANCÉE ===
class TwoFactorAuthSetup(BaseModel):
    """Configuration de l'authentification à deux facteurs"""
    secret_key: str
    qr_code_url: str
    backup_codes: List[str]


class TwoFactorAuthVerify(BaseModel):
    """Vérification 2FA"""
    code: str = Field(
        ...,
        pattern=r'^\d{6}$',
        description="Code à 6 chiffres"
    )


class TwoFactorAuthLogin(BaseModel):
    """Login avec 2FA"""
    username_or_email: str
    password: str
    two_factor_code: str = Field(
        ...,
        pattern=r'^\d{6}$',
        description="Code 2FA"
    )


class SecurityQuestion(BaseModel):
    """Question de sécurité"""
    id: int
    question: str


class SecurityQuestionSetup(BaseModel):
    """Configuration des questions de sécurité"""
    question_1_id: int
    question_1_answer: str = Field(..., min_length=3, max_length=100)
    question_2_id: int
    question_2_answer: str = Field(..., min_length=3, max_length=100)
    question_3_id: int
    question_3_answer: str = Field(..., min_length=3, max_length=100)

    @field_validator('question_1_answer', 'question_2_answer', 'question_3_answer')
    @classmethod
    def validate_answer(cls, v):
        """Valide les réponses aux questions de sécurité"""
        if len(v.strip()) < 3:
            raise ValueError("La réponse doit faire au moins 3 caractères")
        return v.strip().lower()


class SecurityQuestionChallenge(BaseModel):
    """Défi question de sécurité"""
    question_id: int
    answer: str = Field(..., min_length=3, max_length=100)


# === SCHÉMAS DE SESSION ===
class SessionInfo(BaseModel):
    """Informations de session"""
    session_id: str
    user_id: UUID
    ip_address: str
    user_agent: str
    created_at: datetime
    last_activity: datetime
    is_current: bool
    location: Optional[str] = None
    device_type: Optional[str] = None


class SessionListResponse(BaseModel):
    """Liste des sessions actives"""
    sessions: List[SessionInfo]
    current_session_id: str


class SessionRevoke(BaseModel):
    """Révocation de session"""
    session_id: str = Field(
        ...,
        description="ID de la session à révoquer"
    )


# === SCHÉMAS D'AUDIT DE SÉCURITÉ ===
class SecurityAuditLog(BaseModel):
    """Log d'audit de sécurité"""
    id: UUID
    user_id: Optional[UUID]
    event_type: str
    event_description: str
    ip_address: str
    user_agent: str
    success: bool
    risk_level: str  # "low", "medium", "high", "critical"
    created_at: datetime
    additional_data: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class SuspiciousActivityReport(BaseModel):
    """Rapport d'activité suspecte"""
    user_id: UUID
    activity_type: str
    description: str
    risk_score: int = Field(..., ge=0, le=100)
    evidence: Dict[str, Any]
    recommended_action: str


# === SCHÉMAS DE POLITIQUE DE SÉCURITÉ ===
class PasswordPolicy(BaseModel):
    """Politique de mot de passe"""
    min_length: int = 8
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_numbers: bool = True
    require_special_chars: bool = True
    max_age_days: int = 90
    history_count: int = 5
    lockout_threshold: int = 5
    lockout_duration_minutes: int = 15


class SecuritySettings(BaseModel):
    """Paramètres de sécurité utilisateur"""
    two_factor_enabled: bool = False
    security_questions_set: bool = False
    email_notifications: bool = True
    sms_notifications: bool = False
    login_alerts: bool = True
    suspicious_activity_alerts: bool = True
    password_last_changed: Optional[datetime] = None
    last_security_review: Optional[datetime] = None


# === SCHÉMAS DE RÉPONSE COMPLÈTE ===
class AuthenticationResult(BaseModel):
    """Résultat complet d'authentification"""
    success: bool
    user: Optional["UserProfile"] = None
    tokens: Optional[Token] = None
    requires_2fa: bool = False
    requires_password_change: bool = False
    requires_email_verification: bool = False
    security_warnings: List[str] = []
    next_action: Optional[str] = None


class RegistrationResult(BaseModel):
    """Résultat complet d'inscription"""
    success: bool
    user_id: Optional[UUID] = None
    verification_required: bool = True
    verification_sent: bool = False
    welcome_message: str
    next_steps: List[str]


# === SCHÉMAS DE VALIDATION ===
class CredentialValidation(BaseModel):
    """Validation des credentials"""
    username_valid: bool
    email_valid: bool
    password_strength_score: int
    password_suggestions: List[str]
    overall_score: int
    is_acceptable: bool


# === FORWARD REFERENCES ===
# Ces imports sont nécessaires pour résoudre les références circulaires
from app.schemas.user import UserProfile

# Mise à jour des modèles avec les références
LoginResponse.model_rebuild()
AuthenticationResult.model_rebuild()