"""
Schémas Pydantic pour les utilisateurs
Validation et sérialisation des données utilisateur
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict


# === SCHÉMAS DE BASE ===

class UserBase(BaseModel):
    """Schéma de base pour les utilisateurs"""
    model_config = ConfigDict(from_attributes=True)

    username: str = Field(..., min_length=3, max_length=50, description="Nom d'utilisateur")
    email: EmailStr = Field(..., description="Adresse email")
    full_name: Optional[str] = Field(None, max_length=100, description="Nom complet")
    bio: Optional[str] = Field(None, max_length=500, description="Biographie")


class UserCreate(UserBase):
    """Schéma pour la création d'utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    password: str = Field(..., min_length=8, max_length=128, description="Mot de passe")
    is_verified: bool = Field(default=False, description="Email vérifié")
    is_superuser: bool = Field(default=False, description="Super-utilisateur")


class UserUpdate(BaseModel):
    """Schéma pour la mise à jour d'utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = Field(None)
    full_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = Field(None)
    preferences: Optional[Dict[str, Any]] = Field(None)
    settings: Optional[Dict[str, Any]] = Field(None)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().lower()
            if not v:
                raise ValueError("Le nom d'utilisateur ne peut pas être vide")
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.lower().strip()
        return v


# === SCHÉMAS DE PROFIL ===

class UserProfile(BaseModel):
    """Profil complet d'un utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID unique de l'utilisateur")
    username: str = Field(..., description="Nom d'utilisateur")
    email: EmailStr = Field(..., description="Adresse email")
    full_name: Optional[str] = Field(None, description="Nom complet")
    bio: Optional[str] = Field(None, description="Biographie")
    avatar_url: Optional[str] = Field(None, description="URL de l'avatar")

    # Statut
    is_active: bool = Field(..., description="Compte actif")
    is_verified: bool = Field(..., description="Email vérifié")
    is_superuser: bool = Field(..., description="Super-utilisateur")

    # Métadonnées
    created_at: datetime = Field(..., description="Date de création")
    updated_at: datetime = Field(..., description="Dernière mise à jour")
    last_login: Optional[datetime] = Field(None, description="Dernière connexion")

    # Données de jeu
    score: int = Field(default=0, description="Score total")
    rank: str = Field(default="Bronze", description="Rang actuel")
    games_played: int = Field(default=0, description="Parties jouées")
    games_won: int = Field(default=0, description="Parties gagnées")

    # Préférences
    preferences: Dict[str, Any] = Field(default_factory=dict, description="Préférences utilisateur")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Paramètres système")


class UserPublic(BaseModel):
    """Profil public d'un utilisateur (informations limitées)"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID unique")
    username: str = Field(..., description="Nom d'utilisateur")
    full_name: Optional[str] = Field(None, description="Nom complet")
    bio: Optional[str] = Field(None, description="Biographie")
    avatar_url: Optional[str] = Field(None, description="URL de l'avatar")

    # Statistiques publiques
    score: int = Field(..., description="Score total")
    rank: str = Field(..., description="Rang actuel")
    games_played: int = Field(..., description="Parties jouées")
    games_won: int = Field(..., description="Parties gagnées")
    created_at: datetime = Field(..., description="Date d'inscription")


class UserSummary(BaseModel):
    """Résumé d'un utilisateur pour les listes"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID unique")
    username: str = Field(..., description="Nom d'utilisateur")
    full_name: Optional[str] = Field(None, description="Nom complet")
    avatar_url: Optional[str] = Field(None, description="URL de l'avatar")
    score: int = Field(..., description="Score total")
    rank: str = Field(..., description="Rang actuel")
    is_online: bool = Field(default=False, description="En ligne")


# === SCHÉMAS DE STATISTIQUES ===

class UserStats(BaseModel):
    """Statistiques détaillées d'un utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    # Statistiques générales
    total_games: int = Field(..., description="Total des parties")
    games_won: int = Field(..., description="Parties gagnées")
    games_lost: int = Field(..., description="Parties perdues")
    win_rate: float = Field(..., description="Taux de victoire")

    # Temps de jeu
    total_time_played: int = Field(..., description="Temps total joué (secondes)")
    average_game_duration: float = Field(..., description="Durée moyenne d'une partie")

    # Performance
    best_score: int = Field(..., description="Meilleur score")
    average_score: float = Field(..., description="Score moyen")
    best_time: Optional[int] = Field(None, description="Meilleur temps")
    fastest_win: Optional[int] = Field(None, description="Victoire la plus rapide")

    # Tentatives
    total_attempts: int = Field(..., description="Total des tentatives")
    successful_attempts: int = Field(..., description="Tentatives réussies")
    average_attempts_per_game: float = Field(..., description="Tentatives moyennes par partie")

    # Modes de jeu
    classic_games: int = Field(default=0, description="Parties classiques")
    quantum_games: int = Field(default=0, description="Parties quantiques")
    multiplayer_games: int = Field(default=0, description="Parties multijoueur")

    # Utilisation quantique
    quantum_hints_used: int = Field(default=0, description="Indices quantiques utilisés")
    quantum_algorithms_used: int = Field(default=0, description="Algorithmes quantiques utilisés")

    # Classements
    current_rank: str = Field(..., description="Rang actuel")
    highest_rank: str = Field(..., description="Meilleur rang atteint")
    leaderboard_position: Optional[int] = Field(None, description="Position au classement")

    # Progression
    experience_points: int = Field(default=0, description="Points d'expérience")
    level: int = Field(default=1, description="Niveau actuel")
    achievements_unlocked: int = Field(default=0, description="Succès débloqués")


class UserPreferences(BaseModel):
    """Préférences utilisateur pour l'interface et le gameplay"""
    model_config = ConfigDict(from_attributes=True)

    # Interface
    theme: str = Field(default="dark", description="Thème de l'interface")
    language: str = Field(default="fr", description="Langue préférée")
    timezone: str = Field(default="Europe/Paris", description="Fuseau horaire")

    # Notifications
    email_notifications: bool = Field(default=True, description="Notifications par email")
    push_notifications: bool = Field(default=True, description="Notifications push")
    game_invitations: bool = Field(default=True, description="Invitations de jeu")
    achievement_notifications: bool = Field(default=True, description="Notifications de succès")

    # Gameplay
    auto_save: bool = Field(default=True, description="Sauvegarde automatique")
    show_hints: bool = Field(default=True, description="Afficher les indices")
    quantum_mode_default: bool = Field(default=False, description="Mode quantique par défaut")
    auto_quantum_hints: bool = Field(default=False, description="Suggestions quantiques automatiques")
    difficulty_preference: str = Field(default="normal", description="Difficulté préférée")
    sound_effects: bool = Field(default=True, description="Effets sonores")
    animations: bool = Field(default=True, description="Animations")


class UserSettings(BaseModel):
    """Paramètres système de l'utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    # Sécurité
    two_factor_enabled: bool = Field(default=False, description="Authentification à deux facteurs")
    login_notifications: bool = Field(default=True, description="Notifications de connexion")

    # API
    api_key_enabled: bool = Field(default=False, description="Clé API activée")
    api_rate_limit: int = Field(default=100, description="Limite de taux API")

    # Données
    data_retention_days: int = Field(default=365, description="Rétention des données (jours)")
    export_format: str = Field(default="json", description="Format d'export préféré")


# === SCHÉMAS DE RECHERCHE ===

class UserSearch(BaseModel):
    """Paramètres de recherche d'utilisateurs"""
    model_config = ConfigDict(from_attributes=True)

    query: Optional[str] = Field(None, description="Terme de recherche")
    min_score: Optional[int] = Field(None, description="Score minimum")
    max_score: Optional[int] = Field(None, description="Score maximum")
    rank: Optional[str] = Field(None, description="Rang spécifique")
    active_only: bool = Field(default=True, description="Utilisateurs actifs seulement")
    verified_only: bool = Field(default=False, description="Utilisateurs vérifiés seulement")


class UserList(BaseModel):
    """Liste paginée d'utilisateurs"""
    model_config = ConfigDict(from_attributes=True)

    users: List[UserSummary] = Field(..., description="Liste des utilisateurs")
    total: int = Field(..., description="Nombre total d'utilisateurs")
    page: int = Field(..., description="Page actuelle")
    per_page: int = Field(..., description="Éléments par page")
    pages: int = Field(..., description="Nombre total de pages")


# === SCHÉMAS DE CLASSEMENT ===

class LeaderboardEntry(BaseModel):
    """Entrée du classement"""
    model_config = ConfigDict(from_attributes=True)

    position: int = Field(..., description="Position dans le classement")
    user: UserSummary = Field(..., description="Utilisateur")
    score: int = Field(..., description="Score")
    change: Optional[int] = Field(None, description="Changement de position")


class Leaderboard(BaseModel):
    """Classement des joueurs"""
    model_config = ConfigDict(from_attributes=True)

    entries: List[LeaderboardEntry] = Field(..., description="Entrées du classement")
    period: str = Field(..., description="Période du classement")
    last_updated: datetime = Field(..., description="Dernière mise à jour")
    total_players: int = Field(..., description="Nombre total de joueurs")


# === SCHÉMAS D'ADMINISTRATION ===

class UserBulkAction(BaseModel):
    """Action en lot sur les utilisateurs"""
    model_config = ConfigDict(from_attributes=True)

    user_ids: List[UUID] = Field(..., description="IDs des utilisateurs")
    action: str = Field(..., description="Action à effectuer")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Paramètres de l'action")

    @field_validator('action')
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed_actions = {
            'activate', 'deactivate', 'verify', 'unverify',
            'ban', 'unban', 'delete', 'export'
        }
        if v not in allowed_actions:
            raise ValueError(f"Action non autorisée. Actions valides: {allowed_actions}")
        return v


class UserValidation(BaseModel):
    """Validation des données utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    field: str = Field(..., description="Champ à valider")
    value: str = Field(..., description="Valeur à valider")


class UserValidationResult(BaseModel):
    """Résultat de validation"""
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool = Field(..., description="Valeur valide")
    message: str = Field(..., description="Message de validation")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions")