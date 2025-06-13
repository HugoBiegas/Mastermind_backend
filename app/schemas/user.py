"""
Schémas Pydantic pour les utilisateurs
Validation et sérialisation des données utilisateur
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# === SCHÉMAS DE BASE ===
class UserBase(BaseModel):
    """Schéma de base pour les utilisateurs"""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r'^[a-zA-Z0-9_-]+$',
        description="Nom d'utilisateur unique"
    )
    email: EmailStr = Field(
        ...,
        description="Adresse email"
    )


class UserCreate(UserBase):
    """Schéma pour la création d'utilisateur"""
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Mot de passe"
    )

    @field_validator('password')
    @classmethod
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

        if errors:
            raise ValueError("; ".join(errors))

        return v


class UserUpdate(BaseModel):
    """Schéma pour la mise à jour d'utilisateur"""
    username: Optional[str] = Field(
        None,
        min_length=3,
        max_length=50,
        pattern=r'^[a-zA-Z0-9_-]+$',
        description="Nouveau nom d'utilisateur"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="Nouvelle adresse email"
    )
    preferences: Optional[Dict[str, Any]] = Field(
        None,
        description="Préférences utilisateur"
    )


class UserPreferences(BaseModel):
    """Schéma pour les préférences utilisateur"""
    theme: Optional[str] = Field(
        "dark",
        pattern=r'^(light|dark|auto)$',
        description="Thème de l'interface"
    )
    language: Optional[str] = Field(
        "fr",
        pattern=r'^(fr|en|es|de)$',
        description="Langue de l'interface"
    )
    sound_enabled: bool = Field(
        True,
        description="Sons activés"
    )
    notifications_enabled: bool = Field(
        True,
        description="Notifications activées"
    )
    difficulty_preference: Optional[str] = Field(
        "normal",
        pattern=r'^(easy|normal|hard|expert)$',
        description="Difficulté préférée"
    )
    quantum_tutorials_completed: List[str] = Field(
        [],
        description="Tutoriels quantiques terminés"
    )
    ui_customization: Optional[Dict[str, Any]] = Field(
        {},
        description="Personnalisation de l'interface"
    )
    performance_tracking: bool = Field(
        True,
        description="Suivi des performances activé"
    )
    leaderboard_visible: bool = Field(
        True,
        description="Visible dans les classements"
    )


class UserProfile(BaseModel):
    """Profil utilisateur public"""
    id: UUID
    username: str
    email: EmailStr
    is_active: bool = True
    is_verified: bool = False
    is_superuser: bool = False
    created_at: datetime
    last_login: Optional[datetime] = None

    # Statistiques de jeu
    total_games: int = 0
    wins: int = 0
    best_time: Optional[float] = None
    average_time: Optional[float] = None
    quantum_score: int = 0

    # Préférences
    preferences: Optional[UserPreferences] = None

    # Métadonnées
    login_count: int = 0
    profile_picture_url: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=100)

    model_config = {"from_attributes": True}

    @property
    def win_rate(self) -> float:
        """Calcule le taux de victoire"""
        if self.total_games == 0:
            return 0.0
        return (self.wins / self.total_games) * 100

    @property
    def display_name(self) -> str:
        """Nom d'affichage"""
        return self.username

    @property
    def is_experienced_player(self) -> bool:
        """Détermine si c'est un joueur expérimenté"""
        return self.total_games >= 10 and self.win_rate >= 30


class UserProfileUpdate(BaseModel):
    """Mise à jour du profil utilisateur"""
    bio: Optional[str] = Field(None, max_length=500, description="Biographie")
    location: Optional[str] = Field(None, max_length=100, description="Localisation")
    profile_picture_url: Optional[str] = Field(None, description="URL de la photo de profil")
    preferences: Optional[UserPreferences] = Field(None, description="Préférences")

    @field_validator('bio')
    @classmethod
    def validate_bio(cls, v):
        """Valide la biographie"""
        if v and len(v.strip()) == 0:
            return None
        return v

    @field_validator('location')
    @classmethod
    def validate_location(cls, v):
        """Valide la localisation"""
        if v and len(v.strip()) == 0:
            return None
        return v


class UserStats(BaseModel):
    """Statistiques détaillées d'un utilisateur"""
    user_id: UUID
    username: str

    # Statistiques générales
    total_games: int
    wins: int
    losses: int
    win_rate: float

    # Temps et performance
    total_play_time: float  # en secondes
    average_game_duration: float
    best_time: Optional[float]
    worst_time: Optional[float]

    # Scores et points
    total_score: int
    average_score: float
    best_score: int
    quantum_score: int

    # Statistiques quantiques
    quantum_measurements_used: int
    grover_algorithms_executed: int
    entanglement_exploitations: int
    quantum_advantage_percentage: float

    # Progression
    level: int
    experience_points: int
    next_level_threshold: int
    achievements_unlocked: List[str]

    # Historique récent
    recent_games: List[Dict[str, Any]]
    improvement_trend: str  # "improving", "stable", "declining"

    model_config = {"from_attributes": True}


class UserAchievement(BaseModel):
    """Succès utilisateur"""
    id: UUID
    user_id: UUID
    achievement_type: str
    achievement_name: str
    description: str
    unlocked_at: datetime
    difficulty: str
    points_awarded: int
    is_rare: bool = False

    model_config = {"from_attributes": True}


class UserSocialProfile(BaseModel):
    """Profil social de l'utilisateur"""
    user_id: UUID
    username: str
    level: int
    quantum_score: int
    total_games: int
    win_rate: float
    favorite_game_mode: str
    recent_achievements: List[UserAchievement]
    is_online: bool
    last_seen: Optional[datetime]
    friends_count: int
    is_friend: bool = False
    can_invite: bool = True

    model_config = {"from_attributes": True}


class UserSearch(BaseModel):
    """Recherche d'utilisateurs"""
    query: str = Field(..., min_length=1, max_length=50, description="Terme de recherche")
    limit: int = Field(10, ge=1, le=50, description="Limite de résultats")
    include_stats: bool = Field(False, description="Inclure les statistiques")
    active_only: bool = Field(True, description="Utilisateurs actifs uniquement")


class UserValidationResult(BaseModel):
    """Résultat de validation utilisateur"""
    is_valid: bool
    is_available: bool
    errors: List[str]
    suggestions: List[str] = []


class UserSecurityInfo(BaseModel):
    """Informations de sécurité utilisateur"""
    user_id: UUID
    last_password_change: Optional[datetime]
    failed_login_attempts: int
    is_locked: bool
    lockout_until: Optional[datetime]
    two_factor_enabled: bool
    email_verified: bool
    security_questions_set: bool
    last_security_audit: Optional[datetime]
    suspicious_activity_count: int

    model_config = {"from_attributes": True}


# === SCHÉMAS DE RÉPONSE ===
class UserListResponse(BaseModel):
    """Réponse de liste d'utilisateurs"""
    users: List[UserProfile]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


class UserStatsResponse(BaseModel):
    """Réponse avec statistiques utilisateur"""
    user: UserProfile
    stats: UserStats
    achievements: List[UserAchievement]
    recent_activity: List[Dict[str, Any]]


# === VALIDATION AVANCÉE ===
class UserRegistrationValidation(BaseModel):
    """Validation complète d'inscription"""
    username_validation: UserValidationResult
    email_validation: UserValidationResult
    password_strength_score: int
    overall_valid: bool
    recommendations: List[str]


# === SCHÉMAS ADMINISTRATEUR ===
class UserAdminView(BaseModel):
    """Vue administrateur d'un utilisateur"""
    id: UUID
    username: str
    email: EmailStr
    is_active: bool
    is_verified: bool
    is_superuser: bool
    created_at: datetime
    last_login: Optional[datetime]
    total_games: int
    quantum_score: int
    failed_login_attempts: int
    is_locked: bool
    security_flags: List[str]
    moderation_notes: Optional[str]

    model_config = {"from_attributes": True}


class UserModerationAction(BaseModel):
    """Action de modération sur un utilisateur"""
    action: str = Field(
        ...,
        pattern=r'^(warn|suspend|ban|verify|unverify|promote|demote)$',
        description="Type d'action"
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Raison de l'action"
    )
    duration: Optional[int] = Field(
        None,
        gt=0,
        description="Durée en heures (pour suspend/ban)"
    )
    private_note: Optional[str] = Field(
        None,
        max_length=1000,
        description="Note privée pour les modérateurs"
    )