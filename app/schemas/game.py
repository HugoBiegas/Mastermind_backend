"""
Schémas Pydantic pour les jeux
Validation et sérialisation des données de jeu
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, validator, ConfigDict

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

    @validator('room_code')
    def validate_room_code(cls, v):
        if v is not None:
            v = v.strip().upper()
            if not v.isalnum():
                raise ValueError("Le code de room doit être alphanumérique")
        return v

    @validator('settings')
    def validate_settings(cls, v):
        if v is None:
            return v

        # Paramètres autorisés
        allowed_keys = {
            'allow_duplicates', 'allow_blanks', 'quantum_enabled',
            'hint_cost', 'auto_reveal_pegs', 'show_statistics'
        }

        for key in v.keys():
            if key not in allowed_keys:
                raise ValueError(f"Paramètre non autorisé: {key}")

        return v


class GameJoin(BaseModel):
    """Schéma pour rejoindre une partie"""
    model_config = ConfigDict(from_attributes=True)

    password: Optional[str] = Field(None, description="Mot de passe si requis")
    player_name: Optional[str] = Field(None, max_length=50, description="Nom d'affichage")


class GameUpdate(BaseModel):
    """Schéma pour mettre à jour une partie"""
    model_config = ConfigDict(from_attributes=True)

    max_players: Optional[int] = Field(None, ge=1, le=8)
    time_limit: Optional[int] = Field(None, ge=10)
    is_private: Optional[bool] = Field(None)
    password: Optional[str] = Field(None, min_length=4, max_length=50)
    settings: Optional[Dict[str, Any]] = Field(None)


# === SCHÉMAS DE GAMEPLAY ===

class AttemptCreate(BaseModel):
    """Schéma pour créer une tentative"""
    model_config = ConfigDict(from_attributes=True)

    combination: List[int] = Field(..., description="Combinaison proposée")
    use_quantum_hint: bool = Field(default=False, description="Utiliser un hint quantique")

    @validator('combination')
    def validate_combination(cls, v):
        if not v:
            raise ValueError("La combinaison ne peut pas être vide")

        if len(v) > 10:  # Limite raisonnable
            raise ValueError("Combinaison trop longue")

        for color in v:
            if not isinstance(color, int) or color < 0:
                raise ValueError("Les couleurs doivent être des entiers positifs")

        return v


class AttemptResult(BaseModel):
    """Résultat d'une tentative"""
    model_config = ConfigDict(from_attributes=True)

    attempt_number: int = Field(..., description="Numéro de la tentative")
    combination: List[int] = Field(..., description="Combinaison proposée")
    black_pegs: int = Field(..., description="Pions noirs (bonne couleur, bonne position)")
    white_pegs: int = Field(..., description="Pions blancs (bonne couleur, mauvaise position)")
    is_solution: bool = Field(..., description="True si c'est la solution")
    attempts_remaining: int = Field(..., description="Tentatives restantes")
    time_taken: Optional[float] = Field(None, description="Temps pris en secondes")
    score_gained: Optional[int] = Field(None, description="Score obtenu pour cette tentative")


class SolutionHint(BaseModel):
    """Hint sur la solution"""
    model_config = ConfigDict(from_attributes=True)

    hint_type: str = Field(..., description="Type de hint")
    hint_data: Dict[str, Any] = Field(..., description="Données du hint")
    cost: int = Field(..., description="Coût en points")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Niveau de confiance")


class SolutionReveal(BaseModel):
    """Révélation de la solution (debug)"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    classical_solution: List[int] = Field(..., description="Solution classique")
    quantum_solution: Optional[str] = Field(None, description="Solution quantique")
    solution_hash: str = Field(..., description="Hash de vérification")


# === SCHÉMAS D'INFORMATION ===

class GameInfo(BaseModel):
    """Informations de base sur une partie"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de room")
    status: GameStatus = Field(..., description="Statut de la partie")
    game_type: GameType = Field(..., description="Type de jeu")
    game_mode: GameMode = Field(..., description="Mode de jeu")
    difficulty: Difficulty = Field(..., description="Niveau de difficulté")

    # Participants
    current_players: int = Field(..., description="Nombre de joueurs actuels")
    max_players: int = Field(..., description="Nombre maximum de joueurs")

    # Timing
    created_at: datetime = Field(..., description="Date de création")
    started_at: Optional[datetime] = Field(None, description="Date de début")
    duration_minutes: Optional[float] = Field(None, description="Durée en minutes")

    # Créateur
    creator_username: str = Field(..., description="Nom du créateur")

    # Paramètres
    is_private: bool = Field(..., description="Partie privée")
    has_password: bool = Field(..., description="Protégée par mot de passe")


class GamePublic(BaseModel):
    """Informations publiques d'une partie (pour la liste)"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de room")
    status: GameStatus = Field(..., description="Statut")
    game_type: GameType = Field(..., description="Type de jeu")
    difficulty: Difficulty = Field(..., description="Difficulté")
    current_players: int = Field(..., description="Joueurs actuels")
    max_players: int = Field(..., description="Joueurs maximum")
    created_at: datetime = Field(..., description="Date de création")
    creator_username: str = Field(..., description="Créateur")
    has_password: bool = Field(..., description="Protégée par mot de passe")


class GameFull(BaseModel):
    """Informations complètes d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    # Informations de base
    id: UUID = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de room")
    status: GameStatus = Field(..., description="Statut")
    game_type: GameType = Field(..., description="Type de jeu")
    game_mode: GameMode = Field(..., description="Mode de jeu")
    difficulty: Difficulty = Field(..., description="Difficulté")

    # Configuration
    max_attempts: int = Field(..., description="Tentatives maximum")
    combination_length: int = Field(..., description="Longueur de la combinaison")
    color_count: int = Field(..., description="Nombre de couleurs")
    time_limit_seconds: Optional[int] = Field(None, description="Limite de temps")

    # Participants
    participants: List['ParticipantInfo'] = Field(..., description="Liste des participants")
    max_players: int = Field(..., description="Joueurs maximum")

    # Progression
    current_turn: int = Field(..., description="Tour actuel")
    total_attempts: int = Field(..., description="Tentatives totales")

    # Historique des tentatives (limité)
    recent_attempts: List['AttemptInfo'] = Field(..., description="Tentatives récentes")

    # Timing
    created_at: datetime = Field(..., description="Date de création")
    started_at: Optional[datetime] = Field(None, description="Date de début")
    finished_at: Optional[datetime] = Field(None, description="Date de fin")
    duration_minutes: Optional[float] = Field(None, description="Durée")

    # Paramètres
    settings: Dict[str, Any] = Field(..., description="Paramètres de jeu")
    is_private: bool = Field(..., description="Partie privée")


class ParticipantInfo(BaseModel):
    """Informations sur un participant"""
    model_config = ConfigDict(from_attributes=True)

    player_id: UUID = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom d'utilisateur")
    player_name: Optional[str] = Field(None, description="Nom d'affichage")
    status: ParticipationStatus = Field(..., description="Statut de participation")

    # Statistiques
    attempts_made: int = Field(..., description="Tentatives effectuées")
    score: int = Field(..., description="Score actuel")
    is_winner: bool = Field(..., description="A gagné")
    finish_position: Optional[int] = Field(None, description="Position de fin")

    # Métadonnées
    joined_at: datetime = Field(..., description="Date de participation")
    finished_at: Optional[datetime] = Field(None, description="Date de fin")


class AttemptInfo(BaseModel):
    """Informations sur une tentative"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la tentative")
    player_id: UUID = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom du joueur")
    attempt_number: int = Field(..., description="Numéro de tentative")

    # Résultat (combinaison cachée pour les autres joueurs)
    black_pegs: int = Field(..., description="Pions noirs")
    white_pegs: int = Field(..., description="Pions blancs")
    is_solution: bool = Field(..., description="Est la solution")

    # Métadonnées
    used_quantum_hint: bool = Field(..., description="A utilisé un hint quantique")
    time_taken_seconds: Optional[float] = Field(None, description="Temps pris")
    created_at: datetime = Field(..., description="Date de la tentative")


# === SCHÉMAS DE RECHERCHE ===

class GameSearch(BaseModel):
    """Paramètres de recherche de parties"""
    model_config = ConfigDict(from_attributes=True)

    query: Optional[str] = Field(None, description="Terme de recherche")
    game_type: Optional[GameType] = Field(None, description="Type de jeu")
    game_mode: Optional[GameMode] = Field(None, description="Mode de jeu")
    status: Optional[GameStatus] = Field(None, description="Statut")
    difficulty: Optional[Difficulty] = Field(None, description="Difficulté")
    has_slots: Optional[bool] = Field(None, description="A des places libres")
    is_public: Optional[bool] = Field(None, description="Parties publiques uniquement")


class GameList(BaseModel):
    """Liste paginée de parties"""
    model_config = ConfigDict(from_attributes=True)

    games: List[GamePublic] = Field(..., description="Liste des parties")
    total: int = Field(..., description="Nombre total de parties")
    page: int = Field(..., description="Page actuelle")
    per_page: int = Field(..., description="Éléments par page")
    pages: int = Field(..., description="Nombre total de pages")
    filters_applied: Dict[str, Any] = Field(..., description="Filtres appliqués")


# === SCHÉMAS DE STATISTIQUES ===

class GameStatistics(BaseModel):
    """Statistiques d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")

    # Statistiques générales
    total_attempts: int = Field(..., description="Tentatives totales")
    average_attempts_per_player: float = Field(..., description="Moyenne de tentatives par joueur")
    fastest_solution_time: Optional[float] = Field(None, description="Temps de solution le plus rapide")

    # Statistiques quantiques
    quantum_hints_used: int = Field(..., description="Hints quantiques utilisés")
    quantum_advantage_percentage: float = Field(..., description="Pourcentage d'avantage quantique")

    # Classement des joueurs
    player_rankings: List[Dict[str, Any]] = Field(..., description="Classement des joueurs")

    # Analyse des patterns
    color_frequency: Dict[str, int] = Field(..., description="Fréquence des couleurs tentées")
    position_accuracy: List[float] = Field(..., description="Précision par position")

    # Durée et timing
    total_duration_minutes: Optional[float] = Field(None, description="Durée totale")
    average_time_per_attempt: Optional[float] = Field(None, description="Temps moyen par tentative")


class PlayerGameStats(BaseModel):
    """Statistiques d'un joueur dans une partie"""
    model_config = ConfigDict(from_attributes=True)

    player_id: UUID = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom d'utilisateur")

    # Performance
    attempts_made: int = Field(..., description="Tentatives effectuées")
    score: int = Field(..., description="Score final")
    won: bool = Field(..., description="A gagné")
    finish_position: Optional[int] = Field(None, description="Position finale")

    # Timing
    total_time_minutes: Optional[float] = Field(None, description="Temps total")
    average_time_per_attempt: Optional[float] = Field(None, description="Temps moyen par tentative")

    # Quantique
    quantum_hints_used: int = Field(..., description="Hints quantiques utilisés")
    quantum_advantage: bool = Field(..., description="A bénéficié d'avantage quantique")

    # Progression
    improvement_trend: List[float] = Field(..., description="Tendance d'amélioration")
    consistency_score: float = Field(..., description="Score de régularité")


# === SCHÉMAS D'EXPORT ===

class GameExport(BaseModel):
    """Export des données d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_info: GameFull = Field(..., description="Informations de la partie")
    all_attempts: List[AttemptInfo] = Field(..., description="Toutes les tentatives")
    final_statistics: GameStatistics = Field(..., description="Statistiques finales")
    export_metadata: Dict[str, Any] = Field(..., description="Métadonnées d'export")


class GameReplay(BaseModel):
    """Replay d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    chronological_events: List[Dict[str, Any]] = Field(..., description="Événements chronologiques")
    key_moments: List[Dict[str, Any]] = Field(..., description="Moments clés")
    final_outcome: Dict[str, Any] = Field(..., description="Résultat final")


# === SCHÉMAS D'ADMINISTRATION ===

class GameModerationAction(BaseModel):
    """Action de modération sur une partie"""
    model_config = ConfigDict(from_attributes=True)

    action: str = Field(..., description="Action à effectuer")
    reason: str = Field(..., description="Raison de l'action")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Paramètres de l'action")

    @validator('action')
    def validate_action(cls, v):
        allowed_actions = ['pause', 'resume', 'terminate', 'kick_player', 'ban_player', 'reset']
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