"""
Schémas Pydantic pour les utilisateurs
Validation et sérialisation des données utilisateur
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator, ConfigDict


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

    @validator('username')
    def validate_username(cls, v):
        if v is not None:
            v = v.strip().lower()
            if not v:
                raise ValueError("Le nom d'utilisateur ne peut pas être vide")
        return v

    @validator('email')
    def validate_email(cls, v):
        if v is not None:
            v = v.lower().strip()
        return v


# === SCHÉMAS DE PROFIL ===

class UserProfile(BaseModel):
    """Profil complet d'un utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID unique de l'utilisateur")
    username: str = Field(..., description="Nom d'utilisateur")
    email: str = Field(..., description="Adresse email")
    full_name: Optional[str] = Field(None, description="Nom complet")
    avatar_url: Optional[str] = Field(None, description="URL de l'avatar")
    bio: Optional[str] = Field(None, description="Biographie")

    # Statut et permissions
    is_active: bool = Field(..., description="Compte actif")
    is_verified: bool = Field(..., description="Email vérifié")
    is_superuser: bool = Field(..., description="Super-utilisateur")

    # Statistiques de jeu
    total_games: int = Field(..., description="Nombre total de parties")
    games_won: int = Field(..., description="Parties gagnées")
    total_score: int = Field(..., description="Score total")
    best_score: int = Field(..., description="Meilleur score")
    quantum_points: int = Field(..., description="Points quantiques")

    # Propriétés calculées
    win_rate: float = Field(..., description="Taux de victoire (%)")
    average_score: float = Field(..., description="Score moyen")
    rank: str = Field(..., description="Rang actuel")

    # Paramètres et préférences
    preferences: Optional[Dict[str, Any]] = Field(None, description="Préférences utilisateur")
    settings: Optional[Dict[str, Any]] = Field(None, description="Paramètres utilisateur")

    # Dates
    created_at: datetime = Field(..., description="Date de création")
    updated_at: datetime = Field(..., description="Dernière mise à jour")
    last_login: Optional[datetime] = Field(None, description="Dernière connexion")


class UserPublic(BaseModel):
    """Profil public d'un utilisateur (visible par les autres)"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID unique de l'utilisateur")
    username: str = Field(..., description="Nom d'utilisateur")
    full_name: Optional[str] = Field(None, description="Nom complet")
    avatar_url: Optional[str] = Field(None, description="URL de l'avatar")
    bio: Optional[str] = Field(None, description="Biographie")

    # Statistiques publiques
    total_games: int = Field(..., description="Nombre total de parties")
    games_won: int = Field(..., description="Parties gagnées")
    best_score: int = Field(..., description="Meilleur score")
    quantum_points: int = Field(..., description="Points quantiques")

    # Propriétés calculées
    win_rate: float = Field(..., description="Taux de victoire (%)")
    rank: str = Field(..., description="Rang actuel")

    # Date d'inscription
    created_at: datetime = Field(..., description="Date d'inscription")


class UserSummary(BaseModel):
    """Résumé d'un utilisateur pour les listes"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID unique")
    username: str = Field(..., description="Nom d'utilisateur")
    full_name: Optional[str] = Field(None, description="Nom complet")
    avatar_url: Optional[str] = Field(None, description="URL de l'avatar")
    rank: str = Field(..., description="Rang")
    quantum_points: int = Field(..., description="Points quantiques")
    is_online: bool = Field(default=False, description="En ligne")


# === SCHÉMAS DE STATISTIQUES ===

class UserStats(BaseModel):
    """Statistiques détaillées d'un utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID = Field(..., description="ID de l'utilisateur")
    username: str = Field(..., description="Nom d'utilisateur")

    # Statistiques de base
    total_games: int = Field(..., description="Parties totales")
    games_won: int = Field(..., description="Parties gagnées")
    games_lost: int = Field(..., description="Parties perdues")
    win_rate: float = Field(..., description="Taux de victoire")

    # Scores
    total_score: int = Field(..., description="Score total")
    best_score: int = Field(..., description="Meilleur score")
    average_score: float = Field(..., description="Score moyen")

    # Points quantiques
    quantum_points: int = Field(..., description="Points quantiques")
    quantum_games: int = Field(default=0, description="Parties avec fonctionnalités quantiques")
    quantum_usage_rate: float = Field(default=0.0, description="Taux d'utilisation quantique")

    # Progression
    rank: str = Field(..., description="Rang actuel")
    rank_progress: float = Field(default=0.0, description="Progression vers le rang suivant")

    # Temps de jeu
    total_playtime_minutes: int = Field(default=0, description="Temps de jeu total (minutes)")
    average_game_duration: float = Field(default=0.0, description="Durée moyenne d'une partie")

    # Activité récente
    games_this_week: int = Field(default=0, description="Parties cette semaine")
    games_this_month: int = Field(default=0, description="Parties ce mois")
    last_game_date: Optional[datetime] = Field(None, description="Date de la dernière partie")


class UserGameHistory(BaseModel):
    """Historique de jeu d'un utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    game_type: str = Field(..., description="Type de jeu")
    difficulty: str = Field(..., description="Niveau de difficulté")
    score: int = Field(..., description="Score obtenu")
    attempts: int = Field(..., description="Nombre de tentatives")
    duration_minutes: int = Field(..., description="Durée en minutes")
    quantum_used: bool = Field(..., description="Fonctionnalités quantiques utilisées")
    won: bool = Field(..., description="Partie gagnée")
    created_at: datetime = Field(..., description="Date de la partie")


# === SCHÉMAS DE PRÉFÉRENCES ===

class UserPreferences(BaseModel):
    """Préférences utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    # Interface
    theme: str = Field(default="dark", description="Thème (dark/light)")
    language: str = Field(default="fr", description="Langue (fr/en)")

    # Notifications
    email_notifications: bool = Field(default=True, description="Notifications par email")
    push_notifications: bool = Field(default=True, description="Notifications push")
    game_invites: bool = Field(default=True, description="Invitations de jeu")
    tournament_alerts: bool = Field(default=True, description="Alertes de tournois")

    # Confidentialité
    show_stats: bool = Field(default=True, description="Afficher les statistiques publiquement")
    show_online_status: bool = Field(default=True, description="Afficher le statut en ligne")
    allow_friend_requests: bool = Field(default=True, description="Autoriser les demandes d'amis")

    # Jeu
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
    change: int = Field(default=0, description="Changement de position")


class Leaderboard(BaseModel):
    """Classement des utilisateurs"""
    model_config = ConfigDict(from_attributes=True)

    type: str = Field(..., description="Type de classement")
    period: str = Field(..., description="Période (all/month/week)")
    entries: List[LeaderboardEntry] = Field(..., description="Entrées du classement")
    user_position: Optional[int] = Field(None, description="Position de l'utilisateur actuel")
    updated_at: datetime = Field(..., description="Dernière mise à jour")


# === SCHÉMAS D'ADMINISTRATION ===

class UserBulkAction(BaseModel):
    """Action en lot sur les utilisateurs"""
    model_config = ConfigDict(from_attributes=True)

    user_ids: List[UUID] = Field(..., description="IDs des utilisateurs")
    action: str = Field(..., description="Action à effectuer")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Paramètres de l'action")
    reason: Optional[str] = Field(None, description="Raison de l'action")


class UserValidation(BaseModel):
    """Validation d'utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    username: Optional[str] = Field(None, description="Nom d'utilisateur à valider")
    email: Optional[EmailStr] = Field(None, description="Email à valider")
    check_availability: bool = Field(default=True, description="Vérifier la disponibilité")


class UserValidationResult(BaseModel):
    """Résultat de validation d'utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    username_valid: bool = Field(default=True, description="Nom d'utilisateur valide")
    username_available: bool = Field(default=True, description="Nom d'utilisateur disponible")
    username_errors: List[str] = Field(default_factory=list, description="Erreurs nom d'utilisateur")

    email_valid: bool = Field(default=True, description="Email valide")
    email_available: bool = Field(default=True, description="Email disponible")
    email_errors: List[str] = Field(default_factory=list, description="Erreurs email")


# === SCHÉMAS D'EXPORT ===

class UserExport(BaseModel):
    """Export des données utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID = Field(..., description="ID de l'utilisateur")
    format: str = Field(default="json", description="Format d'export")
    include_games: bool = Field(default=True, description="Inclure les parties")
    include_stats: bool = Field(default=True, description="Inclure les statistiques")
    include_preferences: bool = Field(default=True, description="Inclure les préférences")
    date_range: Optional[Dict[str, datetime]] = Field(None, description="Plage de dates")


class UserImport(BaseModel):
    """Import des données utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    data: Dict[str, Any] = Field(..., description="Données à importer")
    overwrite_existing: bool = Field(default=False, description="Écraser les données existantes")
    validate_data: bool = Field(default=True, description="Valider les données")


# === SCHÉMAS DE NOTIFICATION ===

class UserNotification(BaseModel):
    """Notification utilisateur"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la notification")
    user_id: UUID = Field(..., description="ID de l'utilisateur")
    type: str = Field(..., description="Type de notification")
    title: str = Field(..., description="Titre")
    message: str = Field(..., description="Message")
    data: Optional[Dict[str, Any]] = Field(None, description="Données additionnelles")
    read: bool = Field(default=False, description="Lue")
    created_at: datetime = Field(..., description="Date de création")


# === EXPORTS ===

__all__ = [
    # Base
    "UserBase", "UserCreate", "UserUpdate",

    # Profils
    "UserProfile", "UserPublic", "UserSummary",

    # Statistiques
    "UserStats", "UserGameHistory",

    # Préférences
    "UserPreferences", "UserSettings",

    # Recherche
    "UserSearch", "UserList",

    # Classement
    "LeaderboardEntry", "Leaderboard",

    # Administration
    "UserBulkAction", "UserValidation", "UserValidationResult",

    # Export/Import
    "UserExport", "UserImport",

    # Notifications
    "UserNotification"
]