"""
Schémas Pydantic pour les utilisateurs
Validation et sérialisation des données utilisateur
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator


# === SCHÉMAS DE BASE ===
class UserBase(BaseModel):
    """Schéma de base pour les utilisateurs"""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        regex=r'^[a-zA-Z0-9_-]+$',
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

        if errors:
            raise ValueError("; ".join(errors))

        return v


class UserUpdate(BaseModel):
    """Schéma pour la mise à jour d'utilisateur"""
    username: Optional[str] = Field(
        None,
        min_length=3,
        max_length=50,
        regex=r'^[a-zA-Z0-9_-]+$',
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
        regex=r'^(light|dark|auto)$',
        description="Thème de l'interface"
    )
    language: Optional[str] = Field(
        "fr",
        regex=r'^(fr|en|es|de)$',
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
        regex=r'^(easy|normal|hard|expert)$',
        description="Difficulté préférée"
    )
    quantum_hints_enabled: bool = Field(
        True,
        description="Indices quantiques activés par défaut"
    )
    auto_save_games: bool = Field(
        True,
        description="Sauvegarde automatique des parties"
    )


# === SCHÉMAS DE RÉPONSE ===
class UserProfile(BaseModel):
    """Profil public d'un utilisateur"""
    id: UUID
    username: str
    email: str
    is_active: bool
    is_verified: bool
    total_games: int
    wins: int
    win_rate: float
    best_time: Optional[float]
    quantum_score: int
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True

    @validator('win_rate', pre=True, always=True)
    def calculate_win_rate(cls, v, values):
        """Calcule le taux de victoire"""
        total_games = values.get('total_games', 0)
        wins = values.get('wins', 0)
        if total_games == 0:
            return 0.0
        return round((wins / total_games) * 100, 2)


class UserPublic(BaseModel):
    """Informations publiques d'un utilisateur"""
    id: UUID
    username: str
    total_games: int
    wins: int
    win_rate: float
    quantum_score: int
    created_at: datetime
    is_verified: bool

    class Config:
        from_attributes = True


class UserPrivate(UserProfile):
    """Profil privé complet d'un utilisateur"""
    login_count: int
    average_time: Optional[float]
    preferences: Optional[Dict[str, Any]]
    updated_at: datetime
    failed_login_attempts: int
    is_locked: bool

    class Config:
        from_attributes = True


class UserStats(BaseModel):
    """Statistiques détaillées d'un utilisateur"""
    user_id: UUID
    username: str

    # Statistiques de base
    total_games: int
    wins: int
    losses: int
    win_rate: float

    # Temps
    best_time: Optional[float]
    average_time: Optional[float]
    total_play_time: Optional[float]

    # Scores
    quantum_score: int
    total_score: int
    best_game_score: int
    average_game_score: float

    # Quantique
    total_quantum_measurements: int
    total_grover_hints: int
    total_entanglement_uses: int
    quantum_advantage_score: float

    # Progression
    games_this_week: int
    games_this_month: int
    improvement_rate: float
    rank: int

    # Modes de jeu
    classic_games: int
    quantum_games: int
    multiplayer_games: int
    tournament_games: int

    class Config:
        from_attributes = True


class UserRanking(BaseModel):
    """Classement d'un utilisateur"""
    rank: int
    user: UserPublic
    score: int
    category: str  # 'global', 'quantum', 'speed', etc.

    class Config:
        from_attributes = True


# === SCHÉMAS DE LISTE ===
class UserList(BaseModel):
    """Liste paginée d'utilisateurs"""
    users: List[UserPublic]
    total: int
    page: int
    page_size: int
    total_pages: int

    class Config:
        from_attributes = True


class LeaderboardEntry(BaseModel):
    """Entrée du leaderboard"""
    rank: int
    user: UserPublic
    score: int
    games_played: int
    win_rate: float
    badge: Optional[str] = None  # 'new', 'rising', 'legend', etc.

    class Config:
        from_attributes = True


class Leaderboard(BaseModel):
    """Leaderboard complet"""
    entries: List[LeaderboardEntry]
    category: str
    period: str  # 'all-time', 'monthly', 'weekly'
    updated_at: datetime

    class Config:
        from_attributes = True


# === SCHÉMAS D'ACTIVITÉ ===
class UserActivity(BaseModel):
    """Activité d'un utilisateur"""
    id: UUID
    user_id: UUID
    activity_type: str  # 'game_started', 'game_won', 'achievement_unlocked', etc.
    description: str
    data: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserActivityList(BaseModel):
    """Liste d'activités"""
    activities: List[UserActivity]
    total: int
    page: int
    page_size: int

    class Config:
        from_attributes = True


# === SCHÉMAS DE RECHERCHE ===
class UserSearch(BaseModel):
    """Critères de recherche d'utilisateurs"""
    query: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Terme de recherche"
    )
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    min_games: Optional[int] = Field(None, ge=0)
    max_games: Optional[int] = Field(None, ge=0)
    min_score: Optional[int] = Field(None, ge=0)
    sort_by: Optional[str] = Field(
        "created_at",
        regex=r'^(created_at|username|total_games|wins|quantum_score|last_login)$'
    )
    sort_order: Optional[str] = Field(
        "desc",
        regex=r'^(asc|desc)$'
    )
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class UserSearchResult(BaseModel):
    """Résultats de recherche d'utilisateurs"""
    users: List[UserPublic]
    total: int
    page: int
    page_size: int
    total_pages: int
    query: Optional[str]

    class Config:
        from_attributes = True


# === SCHÉMAS D'ADMINISTRATION ===
class UserAdmin(BaseModel):
    """Schéma admin pour les utilisateurs"""
    id: UUID
    username: str
    email: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    total_games: int
    wins: int
    quantum_score: int
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    login_count: int
    failed_login_attempts: int
    locked_until: Optional[datetime]
    last_ip_address: Optional[str]

    class Config:
        from_attributes = True


class UserAdminUpdate(BaseModel):
    """Mise à jour admin d'un utilisateur"""
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_superuser: Optional[bool] = None
    locked_until: Optional[datetime] = None
    reset_password: bool = False
    reset_stats: bool = False


class UserBulkAction(BaseModel):
    """Action en lot sur les utilisateurs"""
    user_ids: List[UUID] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="Liste des IDs utilisateurs"
    )
    action: str = Field(
        ...,
        regex=r'^(activate|deactivate|verify|lock|unlock|delete)$',
        description="Action à effectuer"
    )
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Raison de l'action"
    )


class UserBulkActionResult(BaseModel):
    """Résultat d'une action en lot"""
    success_count: int
    error_count: int
    errors: List[Dict[str, str]] = []
    message: str

    class Config:
        from_attributes = True


# === SCHÉMAS DE VALIDATION ===
class UserValidation(BaseModel):
    """Validation des données utilisateur"""
    field: str = Field(
        ...,
        regex=r'^(username|email)$',
        description="Champ à valider"
    )
    value: str = Field(
        ...,
        min_length=1,
        max_length=254,
        description="Valeur à valider"
    )


class UserValidationResult(BaseModel):
    """Résultat de validation"""
    is_valid: bool
    is_available: bool
    errors: List[str] = []
    suggestions: List[str] = []


# === SCHÉMAS DE BADGE ET ACHIEVEMENT ===
class UserBadge(BaseModel):
    """Badge utilisateur"""
    id: UUID
    name: str
    description: str
    icon: str
    rarity: str  # 'common', 'rare', 'epic', 'legendary'
    earned_at: datetime

    class Config:
        from_attributes = True


class UserAchievement(BaseModel):
    """Achievement utilisateur"""
    id: UUID
    title: str
    description: str
    category: str
    progress: float  # 0.0 à 1.0
    target: int
    current: int
    completed: bool
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# === SCHÉMAS DE NOTIFICATION ===
class UserNotification(BaseModel):
    """Notification utilisateur"""
    id: UUID
    user_id: UUID
    title: str
    message: str
    type: str  # 'info', 'success', 'warning', 'error'
    read: bool
    data: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserNotificationList(BaseModel):
    """Liste de notifications"""
    notifications: List[UserNotification]
    unread_count: int
    total: int

    class Config:
        from_attributes = True


# === SCHÉMAS D'EXPORTATION ===
class UserExport(BaseModel):
    """Export des données utilisateur (RGPD)"""
    personal_data: Dict[str, Any]
    game_history: List[Dict[str, Any]]
    preferences: Dict[str, Any]
    statistics: Dict[str, Any]
    export_date: datetime

    class Config:
        from_attributes = True


class UserDeletion(BaseModel):
    """Demande de suppression de compte"""
    password: str = Field(
        ...,
        description="Mot de passe pour confirmation"
    )
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Raison de la suppression (optionnel)"
    )
    delete_immediately: bool = Field(
        False,
        description="Suppression immédiate (sinon 30 jours de grâce)"
    )


# === SCHÉMAS DE RÉPONSE D'ERREUR ===
class UserErrorResponse(BaseModel):
    """Réponse d'erreur spécifique aux utilisateurs"""
    error_code: str
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True