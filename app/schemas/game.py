"""
Schémas Pydantic pour les jeux
Validation et sérialisation des données de jeu
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models.game import GameType, GameMode, GameStatus, Difficulty, ParticipationStatus


# === SCHÉMAS DE CRÉATION ===

class GameCreate(BaseModel):
    """Schéma pour créer une nouvelle partie"""
    model_config = ConfigDict(from_attributes=True)

    game_type: GameType = Field(..., description="Type de jeu")
    game_mode: GameMode = Field(..., description="Mode de jeu")
    difficulty: Difficulty = Field(default=Difficulty.NORMAL, description="Niveau de difficulté")

    # Paramètres optionnels
    max_attempts: Optional[int] = Field(None, ge=1, le=50, description="Nombre maximum de tentatives")
    time_limit: Optional[int] = Field(None, ge=10, description="Limite de temps en secondes")
    max_players: int = Field(default=1, ge=1, le=8, description="Nombre maximum de joueurs")

    # Personnalisation
    room_code: Optional[str] = Field(None, min_length=4, max_length=10, description="Code de room personnalisé")
    is_private: bool = Field(default=False, description="Partie privée")
    password: Optional[str] = Field(None, min_length=4, max_length=50, description="Mot de passe")

    # Paramètres avancés
    settings: Optional[Dict[str, Any]] = Field(None, description="Paramètres personnalisés")

    @field_validator('room_code')
    @classmethod
    def validate_room_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().upper()
            if not v.isalnum():
                raise ValueError("Le code de room doit être alphanumérique")
        return v

    @field_validator('settings')
    @classmethod
    def validate_settings(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is None:
            return v

        # CORRECTION CRITIQUE : Paramètres autorisés étendus
        allowed_keys = {
            # Paramètres de base du jeu
            'combination_length', 'color_count', 'max_attempts', 'time_limit',

            # Paramètres de gameplay
            'allow_duplicates', 'allow_blanks', 'quantum_enabled', 'quantum_hints_enabled',

            # Paramètres d'interface et aide
            'hint_cost', 'auto_reveal_pegs', 'show_statistics',

            # Paramètres avancés
            'difficulty_multiplier', 'scoring_mode', 'bonus_enabled'
        }

        for key in v.keys():
            if key not in allowed_keys:
                raise ValueError(f"Paramètre non autorisé: {key}")

        return v


class GameJoin(BaseModel):
    """Schéma pour rejoindre une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie à rejoindre")
    password: Optional[str] = Field(None, description="Mot de passe si partie privée")
    role: str = Field(default="player", description="Rôle dans la partie")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed_roles = {'player', 'spectator'}
        if v not in allowed_roles:
            raise ValueError(f"Rôle non autorisé. Rôles valides: {allowed_roles}")
        return v


class GameUpdate(BaseModel):
    """Schéma pour mettre à jour une partie"""
    model_config = ConfigDict(from_attributes=True)

    status: Optional[GameStatus] = Field(None, description="Nouveau statut")
    settings: Optional[Dict[str, Any]] = Field(None, description="Nouveaux paramètres")
    max_players: Optional[int] = Field(None, ge=1, le=8, description="Nouveau max de joueurs")
    time_limit: Optional[int] = Field(None, ge=10, description="Nouvelle limite de temps")


# === SCHÉMAS DE GAMEPLAY ===

class AttemptCreate(BaseModel):
    """Schéma pour créer une tentative"""
    model_config = ConfigDict(from_attributes=True)

    combination: List[int] = Field(..., min_length=4, max_length=6, description="Combinaison proposée")
    quantum_hint_used: bool = Field(default=False, description="Indice quantique utilisé")
    time_taken: Optional[int] = Field(None, description="Temps pris pour cette tentative")

    @field_validator('combination')
    @classmethod
    def validate_combination(cls, v: List[int]) -> List[int]:
        """Valide la combinaison proposée"""
        if not v:
            raise ValueError("La combinaison ne peut pas être vide")

        for color in v:
            if not (1 <= color <= 8):
                raise ValueError("Les couleurs doivent être entre 1 et 8")

        return v


class AttemptResult(BaseModel):
    """Résultat d'une tentative"""
    model_config = ConfigDict(from_attributes=True)

    attempt_number: int = Field(..., description="Numéro de la tentative")
    combination: List[int] = Field(..., description="Combinaison proposée")
    correct_positions: int = Field(..., description="Positions correctes (pions noirs)")
    correct_colors: int = Field(..., description="Couleurs correctes (pions blancs)")
    is_winning: bool = Field(..., description="Tentative gagnante")
    score_gained: int = Field(default=0, description="Points gagnés")
    time_taken: Optional[int] = Field(None, description="Temps pris")
    quantum_bonus: Optional[int] = Field(None, description="Bonus quantique")


class SolutionHint(BaseModel):
    """Indice sur la solution"""
    model_config = ConfigDict(from_attributes=True)

    hint_type: str = Field(..., description="Type d'indice")
    message: str = Field(..., description="Message de l'indice")
    cost: int = Field(default=0, description="Coût en points")
    quantum_data: Optional[Dict[str, Any]] = Field(None, description="Données quantiques")


class SolutionReveal(BaseModel):
    """Révélation de la solution"""
    model_config = ConfigDict(from_attributes=True)

    solution: List[int] = Field(..., description="Solution complète")
    attempts_used: int = Field(..., description="Tentatives utilisées")
    time_elapsed: int = Field(..., description="Temps écoulé")
    score: int = Field(..., description="Score final")


# === SCHÉMAS D'INFORMATION ===

class GameInfo(BaseModel):
    """Informations de base sur une partie"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID unique de la partie")
    game_type: GameType = Field(..., description="Type de jeu")
    game_mode: GameMode = Field(..., description="Mode de jeu")
    status: GameStatus = Field(..., description="Statut actuel")
    difficulty: Difficulty = Field(..., description="Niveau de difficulté")

    # Timing
    created_at: datetime = Field(..., description="Date de création")
    started_at: Optional[datetime] = Field(None, description="Date de début")
    finished_at: Optional[datetime] = Field(None, description="Date de fin")

    # Joueurs
    current_players: int = Field(..., description="Nombre de joueurs actuels")
    max_players: int = Field(..., description="Nombre maximum de joueurs")

    # Paramètres
    max_attempts: Optional[int] = Field(None, description="Tentatives maximales")
    time_limit: Optional[int] = Field(None, description="Limite de temps")
    is_private: bool = Field(..., description="Partie privée")
    room_code: Optional[str] = Field(None, description="Code de la room")


class ParticipantInfo(BaseModel):
    """Information sur un participant"""
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID = Field(..., description="ID de l'utilisateur")
    username: str = Field(..., description="Nom d'utilisateur")
    avatar_url: Optional[str] = Field(None, description="Avatar")
    status: ParticipationStatus = Field(..., description="Statut de participation")
    score: int = Field(default=0, description="Score dans cette partie")
    attempts_used: int = Field(default=0, description="Tentatives utilisées")
    is_ready: bool = Field(default=False, description="Prêt à jouer")
    role: str = Field(default="player", description="Rôle dans la partie")


class AttemptInfo(BaseModel):
    """Information sur une tentative"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la tentative")
    attempt_number: int = Field(..., description="Numéro de tentative")
    user_id: UUID = Field(..., description="ID de l'utilisateur")
    combination: List[int] = Field(..., description="Combinaison proposée")
    correct_positions: int = Field(..., description="Positions correctes")
    correct_colors: int = Field(..., description="Couleurs correctes")
    timestamp: datetime = Field(..., description="Horodatage")
    is_winning: bool = Field(..., description="Tentative gagnante")


class GamePublic(BaseModel):
    """Vue publique d'une partie (pour la recherche)"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la partie")
    game_type: GameType = Field(..., description="Type de jeu")
    game_mode: GameMode = Field(..., description="Mode de jeu")
    status: GameStatus = Field(..., description="Statut")
    difficulty: Difficulty = Field(..., description="Difficulté")
    current_players: int = Field(..., description="Joueurs actuels")
    max_players: int = Field(..., description="Max joueurs")
    created_at: datetime = Field(..., description="Date de création")
    creator_username: str = Field(..., description="Créateur")
    room_code: Optional[str] = Field(None, description="Code de room")
    is_joinable: bool = Field(..., description="Peut être rejoint")


class GameFull(BaseModel):
    """Vue complète d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    # Informations de base
    id: UUID = Field(..., description="ID de la partie")
    game_type: GameType = Field(..., description="Type de jeu")
    game_mode: GameMode = Field(..., description="Mode de jeu")
    status: GameStatus = Field(..., description="Statut")
    difficulty: Difficulty = Field(..., description="Difficulté")

    # Paramètres
    max_attempts: Optional[int] = Field(None, description="Tentatives max")
    time_limit: Optional[int] = Field(None, description="Limite de temps")
    max_players: int = Field(..., description="Joueurs max")
    is_private: bool = Field(..., description="Partie privée")
    room_code: Optional[str] = Field(None, description="Code de room")

    # Timing
    created_at: datetime = Field(..., description="Date de création")
    started_at: Optional[datetime] = Field(None, description="Date de début")
    finished_at: Optional[datetime] = Field(None, description="Date de fin")
    duration: Optional[int] = Field(None, description="Durée en secondes")

    # Participants et tentatives
    participants: List[ParticipantInfo] = Field(..., description="Participants")
    attempts: List[AttemptInfo] = Field(..., description="Tentatives")
    current_turn: Optional[UUID] = Field(None, description="Tour actuel")

    # Solution (si révélée)
    solution: Optional[List[int]] = Field(None, description="Solution")

    # Paramètres avancés
    settings: Dict[str, Any] = Field(default_factory=dict, description="Paramètres")
    quantum_data: Optional[Dict[str, Any]] = Field(None, description="Données quantiques")


# === SCHÉMAS DE RECHERCHE ===

class GameSearch(BaseModel):
    """Paramètres de recherche de parties"""
    model_config = ConfigDict(from_attributes=True)

    game_type: Optional[GameType] = Field(None, description="Type de jeu")
    game_mode: Optional[GameMode] = Field(None, description="Mode de jeu")
    status: Optional[GameStatus] = Field(None, description="Statut")
    difficulty: Optional[Difficulty] = Field(None, description="Difficulté")
    min_players: Optional[int] = Field(None, description="Minimum de joueurs")
    max_players: Optional[int] = Field(None, description="Maximum de joueurs")
    creator_id: Optional[UUID] = Field(None, description="ID du créateur")
    room_code: Optional[str] = Field(None, description="Code de room")
    public_only: bool = Field(default=True, description="Parties publiques seulement")


class GameList(BaseModel):
    """Liste paginée de parties"""
    model_config = ConfigDict(from_attributes=True)

    games: List[GamePublic] = Field(..., description="Liste des parties")
    total: int = Field(..., description="Nombre total de parties")
    page: int = Field(..., description="Page actuelle")
    per_page: int = Field(..., description="Éléments par page")
    pages: int = Field(..., description="Nombre total de pages")


# === SCHÉMAS DE STATISTIQUES ===

class GameStatistics(BaseModel):
    """Statistiques d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    total_attempts: int = Field(..., description="Total des tentatives")
    average_attempts_per_player: float = Field(..., description="Tentatives moyennes par joueur")
    fastest_solution: Optional[int] = Field(None, description="Solution la plus rapide")
    best_score: int = Field(..., description="Meilleur score")
    quantum_hints_used: int = Field(default=0, description="Indices quantiques utilisés")
    completion_rate: float = Field(..., description="Taux de complétion")


class PlayerGameStats(BaseModel):
    """Statistiques d'un joueur dans une partie"""
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID = Field(..., description="ID de l'utilisateur")
    attempts_made: int = Field(..., description="Tentatives effectuées")
    best_attempt: Optional[AttemptResult] = Field(None, description="Meilleure tentative")
    total_score: int = Field(..., description="Score total")
    time_spent: int = Field(..., description="Temps passé")
    quantum_bonuses: int = Field(default=0, description="Bonus quantiques")
    achievements: List[str] = Field(default_factory=list, description="Succès obtenus")


# === SCHÉMAS D'EXPORT ===

class GameExport(BaseModel):
    """Export d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_data: GameFull = Field(..., description="Données complètes de la partie")
    export_format: str = Field(..., description="Format d'export")
    generated_at: datetime = Field(..., description="Date de génération")
    file_size: Optional[int] = Field(None, description="Taille du fichier")


class GameReplay(BaseModel):
    """Rejeu d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    replay_data: List[AttemptResult] = Field(..., description="Données de rejeu")
    metadata: Dict[str, Any] = Field(..., description="Métadonnées")
    duration: int = Field(..., description="Durée totale")


# === SCHÉMAS D'ADMINISTRATION ===

class GameModerationAction(BaseModel):
    """Action de modération sur une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    action: str = Field(..., description="Action à effectuer")
    reason: str = Field(..., description="Raison de l'action")
    moderator_note: Optional[str] = Field(None, description="Note du modérateur")

    @field_validator('action')
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed_actions = {
            'pause', 'resume', 'terminate', 'kick_player',
            'ban_player', 'reset', 'force_end'
        }
        if v not in allowed_actions:
            raise ValueError(f"Action non autorisée. Actions valides: {allowed_actions}")
        return v


class GameAuditLog(BaseModel):
    """Log d'audit pour une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    action: str = Field(..., description="Action effectuée")
    user_id: UUID = Field(..., description="ID de l'utilisateur")
    timestamp: datetime = Field(..., description="Horodatage")
    details: Dict[str, Any] = Field(..., description="Détails de l'action")
    ip_address: Optional[str] = Field(None, description="Adresse IP")


# === SCHÉMAS DE VALIDATION ===

class GameValidation(BaseModel):
    """Validation des données de jeu"""
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool = Field(..., description="Données valides")
    errors: List[str] = Field(default_factory=list, description="Erreurs détectées")
    warnings: List[str] = Field(default_factory=list, description="Avertissements")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions")


class SolutionValidation(BaseModel):
    """Validation d'une solution"""
    model_config = ConfigDict(from_attributes=True)

    is_valid_solution: bool = Field(..., description="Solution valide")
    combination: List[int] = Field(..., description="Combinaison validée")
    matches_constraints: bool = Field(..., description="Respecte les contraintes")
    difficulty_appropriate: bool = Field(..., description="Appropriée à la difficulté")


# === RÉSOLUTION DES RÉFÉRENCES FORWARD ===

# Mise à jour des références forward pour les modèles imbriqués
GameFull.model_rebuild()
ParticipantInfo.model_rebuild()
AttemptInfo.model_rebuild()


# === EXPORTS ===

__all__ = [
    # Création et modification
    "GameCreate", "GameJoin", "GameUpdate",

    # Gameplay
    "AttemptCreate", "AttemptResult", "SolutionHint", "SolutionReveal",

    # Information
    "GameInfo", "GamePublic", "GameFull", "ParticipantInfo", "AttemptInfo",

    # Recherche
    "GameSearch", "GameList",

    # Statistiques
    "GameStatistics", "PlayerGameStats",

    # Export
    "GameExport", "GameReplay",

    # Administration
    "GameModerationAction", "GameAuditLog",

    # Validation
    "GameValidation", "SolutionValidation"
]