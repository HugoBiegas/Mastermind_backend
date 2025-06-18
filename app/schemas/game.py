"""
Schémas Pydantic pour les jeux Quantum Mastermind
Validation et sérialisation des données avec support quantique complet
CORRECTION ENUM: Utilisation des vrais Enums pour FastAPI
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, validator

from app.models.game import GameType, GameMode, GameStatus, Difficulty, ParticipationStatus


# === SCHÉMAS DE BASE ===

class GameCreate(BaseModel):
    """Schéma pour créer une nouvelle partie avec support quantique"""
    model_config = ConfigDict(from_attributes=True)

    game_type: GameType = Field(default=GameType.CLASSIC, description="Type de jeu")
    game_mode: GameMode = Field(default=GameMode.SINGLE, description="Mode de jeu")
    difficulty: Difficulty = Field(default=Difficulty.MEDIUM, description="Niveau de difficulté")

    # Paramètres de jeu
    combination_length: int = Field(default=4, ge=2, le=8, description="Longueur de la combinaison")
    available_colors: int = Field(default=6, ge=3, le=15, description="Nombre de couleurs disponibles")
    max_attempts: Optional[int] = Field(default=12, ge=1, le=50, description="Tentatives maximales")
    time_limit: Optional[int] = Field(default=None, ge=60, le=3600, description="Limite de temps (secondes)")
    max_players: int = Field(default=1, ge=1, le=8, description="Nombre maximum de joueurs")

    # Configuration
    is_private: bool = Field(default=False, description="Partie privée")
    allow_spectators: bool = Field(default=True, description="Autoriser les spectateurs")
    enable_chat: bool = Field(default=True, description="Activer le chat")

    #  Support quantique ajouté
    quantum_enabled: bool = Field(default=False, description="Activer le mode quantique")
    quantum_shots: Optional[int] = Field(default=1024, ge=100, le=8192, description="Nombre de shots quantiques")

    # Paramètres avancés
    settings: Optional[Dict[str, Any]] = Field(default=None, description="Paramètres avancés")

    @validator('game_type')
    def validate_quantum_consistency(cls, v, values):
        """Valide la cohérence entre game_type et quantum_enabled"""
        if v == GameType.QUANTUM:
            values['quantum_enabled'] = True
        return v


class GameUpdate(BaseModel):
    """Schéma pour modifier une partie"""
    model_config = ConfigDict(from_attributes=True)

    max_attempts: Optional[int] = Field(default=None, ge=1, le=50, description="Tentatives max")
    time_limit: Optional[int] = Field(default=None, ge=60, le=3600, description="Limite de temps")
    is_private: Optional[bool] = Field(default=None, description="Partie privée")
    password: Optional[str] = Field(default=None, description="Mot de passe")
    allow_spectators: Optional[bool] = Field(default=None, description="Autoriser spectateurs")
    enable_chat: Optional[bool] = Field(default=None, description="Activer chat")
    settings: Optional[Dict[str, Any]] = Field(default=None, description="Paramètres")


class AttemptCreate(BaseModel):
    """Schéma pour créer une tentative avec support quantique"""
    model_config = ConfigDict(from_attributes=True)

    combination: List[int] = Field(..., min_length=1, max_length=8, description="Combinaison proposée")
    use_quantum_hint: bool = Field(default=False, description="Utiliser un hint quantique")
    hint_type: Optional[str] = Field(default=None, description="Type de hint quantique")

    @validator('combination')
    def validate_combination_values(cls, v):
        """Valide que les valeurs de combinaison sont positives"""
        for color in v:
            if color < 1 or color > 10:  # Maximum 10 couleurs
                raise ValueError("Les couleurs doivent être entre 1 et 10")
        return v


class AttemptResult(BaseModel):
    """
    Résultat d'une tentative avec informations quantiques
     Champs synchronisés avec les modèles
    """
    model_config = ConfigDict(from_attributes=True)

    attempt_number: int = Field(..., description="Numéro de la tentative")
    combination: List[int] = Field(..., description="Combinaison proposée")
    exact_matches: int = Field(..., description="Couleurs bien placées (pegs noirs)")
    position_matches: int = Field(..., description="Couleurs mal placées (pegs blancs)")
    is_correct: bool = Field(..., description="Solution trouvée")

    #  Champs quantiques ajoutés
    quantum_calculated: bool = Field(default=False, description="Calculé avec algorithmes quantiques")
    quantum_hint_used: bool = Field(default=False, description="Hint quantique utilisé")
    quantum_efficiency: Optional[float] = Field(None, description="Efficacité quantique (0-1)")

    remaining_attempts: Optional[int] = Field(None, description="Tentatives restantes")
    game_finished: bool = Field(default=False, description="Partie terminée")


class GameCreateResponse(BaseModel):
    """Réponse de création de partie avec tous les champs nécessaires"""
    model_config = ConfigDict(from_attributes=True)

    # Identification
    id: str = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de la room")

    # Configuration de base
    game_type: str = Field(..., description="Type de jeu")
    game_mode: str = Field(..., description="Mode de jeu")
    difficulty: str = Field(..., description="Difficulté")
    status: str = Field(..., description="Statut")
    quantum_enabled: bool = Field(..., description="Mode quantique activé")

    # Paramètres de jeu
    combination_length: int = Field(..., description="Longueur de la combinaison")
    available_colors: int = Field(..., description="Couleurs disponibles")
    max_players: int = Field(..., description="Joueurs maximum")

    # Configuration avancée
    is_private: bool = Field(..., description="Partie privée")
    allow_spectators: bool = Field(..., description="Spectateurs autorisés")
    enable_chat: bool = Field(..., description="Chat activé")

    # Créateur
    creator_id: str = Field(..., description="ID du créateur")
    creator_username: str = Field(..., description="Nom du créateur")

    # Timestamps
    created_at: str = Field(..., description="Date de création")
    started_at: Optional[str] = Field(None, description="Date de début")
    finished_at: Optional[str] = Field(None, description="Date de fin")

    # Statistiques
    current_players: int = Field(default=0, description="Joueurs actuels")

    # Message
    message: str = Field(..., description="Message de succès")


class GameJoin(BaseModel):
    """Schéma pour rejoindre une partie"""
    model_config = ConfigDict(from_attributes=True)

    password: Optional[str] = Field(default=None, description="Mot de passe de la partie")
    player_name: Optional[str] = Field(default=None, max_length=50, description="Nom d'affichage")


# === SCHÉMAS D'INFORMATION ===

class AttemptInfo(BaseModel):
    """Informations d'une tentative"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la tentative")
    attempt_number: int = Field(..., description="Numéro de la tentative")
    combination: List[int] = Field(..., description="Combinaison proposée")
    correct_positions: int = Field(..., description="Couleurs bien placées")
    correct_colors: int = Field(..., description="Couleurs mal placées")
    is_correct: bool = Field(..., description="Solution trouvée")

    #  Champs quantiques
    used_quantum_hint: bool = Field(default=False, description="Hint quantique utilisé")
    hint_type: Optional[str] = Field(None, description="Type de hint")
    quantum_data: Optional[Dict[str, Any]] = Field(None, description="Données quantiques")

    attempt_score: int = Field(default=0, description="Score de la tentative")
    time_taken: Optional[int] = Field(None, description="Temps pris (ms)")
    created_at: datetime = Field(..., description="Date de création")


class ParticipantInfo(BaseModel):
    """Informations d'un participant"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la participation")
    player_id: UUID = Field(..., description="ID du joueur")
    player_username: str = Field(..., description="Nom d'utilisateur")
    player_full_name: Optional[str] = Field(None, description="Nom complet")

    status: ParticipationStatus = Field(..., description="Statut de la participation")
    role: str = Field(default="player", description="Rôle")
    join_order: int = Field(..., description="Ordre d'arrivée")

    # Statistiques
    score: int = Field(default=0, description="Score")
    attempts_made: int = Field(default=0, description="Tentatives effectuées")
    quantum_hints_used: int = Field(default=0, description="Hints quantiques utilisés")
    quantum_score: int = Field(default=0, description="Score quantique")

    # Flags
    is_ready: bool = Field(default=False, description="Prêt")
    is_winner: bool = Field(default=False, description="Gagnant")
    is_eliminated: bool = Field(default=False, description="Éliminé")

    # Timestamps
    joined_at: datetime = Field(..., description="Date d'adhésion")
    finished_at: Optional[datetime] = Field(None, description="Date de fin")


class GameInfo(BaseModel):
    """Informations de base d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de la room")

    # Configuration
    game_type: GameType = Field(..., description="Type de jeu")
    game_mode: GameMode = Field(..., description="Mode de jeu")
    status: GameStatus = Field(..., description="Statut de la partie")
    difficulty: Difficulty = Field(..., description="Difficulté")

    # Paramètres
    combination_length: int = Field(..., description="Longueur de la combinaison")
    available_colors: int = Field(..., description="Couleurs disponibles")
    max_attempts: Optional[int] = Field(None, description="Tentatives maximales")
    time_limit: Optional[int] = Field(None, description="Limite de temps")
    max_players: int = Field(..., description="Joueurs maximum")

    # Configuration avancée
    is_private: bool = Field(..., description="Partie privée")
    allow_spectators: bool = Field(..., description="Spectateurs autorisés")
    enable_chat: bool = Field(..., description="Chat activé")
    quantum_enabled: bool = Field(..., description="Mode quantique")

    # Créateur
    creator_id: UUID = Field(..., description="ID du créateur")
    creator_username: str = Field(..., description="Nom du créateur")

    # Timestamps
    created_at: datetime = Field(..., description="Date de création")
    started_at: Optional[datetime] = Field(None, description="Date de début")
    finished_at: Optional[datetime] = Field(None, description="Date de fin")

    # Statistiques
    current_players: int = Field(default=0, description="Joueurs actuels")


class GameFull(GameInfo):
    """Informations complètes d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    # Participants et tentatives
    participants: List[ParticipantInfo] = Field(default_factory=list, description="Participants")
    attempts: List[AttemptInfo] = Field(default_factory=list, description="Tentatives")

    # Configuration avancée
    settings: Dict[str, Any] = Field(default_factory=dict, description="Paramètres")
    quantum_data: Optional[Dict[str, Any]] = Field(None, description="Données quantiques")

    # Solution (seulement pour le créateur ou partie terminée)
    solution: Optional[List[int]] = Field(None, description="Solution secrète (non exposée)")

class GamePublic(BaseModel):
    """Informations publiques d'une partie (pour les listes)"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de la room")
    game_type: GameType = Field(..., description="Type de jeu")
    game_mode: GameMode = Field(..., description="Mode de jeu")
    status: GameStatus = Field(..., description="Statut")
    difficulty: Difficulty = Field(..., description="Difficulté")

    # Compteurs
    current_players: int = Field(..., description="Joueurs actuels")
    max_players: int = Field(..., description="Joueurs maximum")

    # Configuration visible
    is_private: bool = Field(..., description="Partie privée")
    quantum_enabled: bool = Field(..., description="Mode quantique")

    # Créateur
    creator_username: str = Field(..., description="Nom du créateur")

    # Timing
    created_at: datetime = Field(..., description="Date de création")
    started_at: Optional[datetime] = Field(None, description="Date de début")


# === SCHÉMAS DE RECHERCHE ===

class GameSearch(BaseModel):
    """Critères de recherche de parties"""
    model_config = ConfigDict(from_attributes=True)

    game_type: Optional[GameType] = Field(None, description="Type de jeu")
    game_mode: Optional[GameMode] = Field(None, description="Mode de jeu")
    status: Optional[GameStatus] = Field(None, description="Statut")
    difficulty: Optional[Difficulty] = Field(None, description="Difficulté")
    quantum_enabled: Optional[bool] = Field(None, description="Mode quantique")
    is_private: Optional[bool] = Field(None, description="Parties privées")
    room_code: Optional[str] = Field(None, description="Code de room")


class GameList(BaseModel):
    """Liste de parties avec pagination"""
    model_config = ConfigDict(from_attributes=True)

    games: List[GamePublic] = Field(..., description="Liste des parties")
    total: int = Field(..., description="Total de parties")
    page: int = Field(..., description="Page actuelle")
    per_page: int = Field(..., description="Parties par page")
    pages: int = Field(..., description="Nombre total de pages")


# === SCHÉMAS QUANTIQUES ===

class QuantumHintRequest(BaseModel):
    """Demande d'indice quantique"""
    model_config = ConfigDict(from_attributes=True)

    hint_type: str = Field(..., description="Type d'indice (grover, superposition, entanglement)")
    target_positions: Optional[List[int]] = Field(None, description="Positions ciblées")
    quantum_shots: Optional[int] = Field(1024, ge=100, le=8192, description="Nombre de shots")


class QuantumHintResponse(BaseModel):
    """Réponse d'indice quantique"""
    model_config = ConfigDict(from_attributes=True)

    hint_type: str = Field(..., description="Type d'indice utilisé")
    hint_data: Dict[str, Any] = Field(..., description="Données de l'indice")
    quantum_probability: float = Field(..., description="Probabilité quantique")
    cost: int = Field(..., description="Coût de l'indice")
    success: bool = Field(..., description="Succès de l'opération")


class QuantumGameInfo(BaseModel):
    """Informations quantiques d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    quantum_enabled: bool = Field(..., description="Mode quantique activé")
    quantum_solution_generated: bool = Field(..., description="Solution générée quantiquement")
    quantum_hints_available: bool = Field(..., description="Indices quantiques disponibles")
    quantum_config: Dict[str, Any] = Field(..., description="Configuration quantique")
    quantum_statistics: Optional[Dict[str, Any]] = Field(None, description="Statistiques quantiques")


# === SCHÉMAS DE STATISTIQUES ===

class PlayerGameStats(BaseModel):
    """Statistiques d'un joueur pour une partie"""
    model_config = ConfigDict(from_attributes=True)

    total_attempts: int = Field(..., description="Tentatives totales")
    successful_attempts: int = Field(..., description="Tentatives réussies")
    quantum_hints_used: int = Field(..., description="Indices quantiques utilisés")
    quantum_efficiency: float = Field(..., description="Efficacité quantique")
    average_time_per_attempt: Optional[float] = Field(None, description="Temps moyen par tentative")
    total_score: int = Field(..., description="Score total")
    quantum_score: int = Field(..., description="Score quantique")


class GameStatistics(BaseModel):
    """Statistiques complètes d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    total_attempts: int = Field(..., description="Tentatives totales")
    total_players: int = Field(..., description="Joueurs totaux")
    winners: int = Field(..., description="Nombre de gagnants")

    # Statistiques temporelles
    duration_seconds: Optional[int] = Field(None, description="Durée en secondes")
    average_attempts_per_player: float = Field(..., description="Tentatives moyennes par joueur")

    # Statistiques quantiques
    quantum_attempts: int = Field(default=0, description="Tentatives quantiques")
    quantum_hints_used: int = Field(default=0, description="Indices quantiques utilisés")
    quantum_efficiency_avg: float = Field(default=0.0, description="Efficacité quantique moyenne")

    # Scores
    highest_score: int = Field(..., description="Meilleur score")
    total_score: int = Field(..., description="Score total")
    quantum_score: int = Field(default=0, description="Score quantique total")


# === SCHÉMAS D'EXPORT ===

class SolutionHint(BaseModel):
    """Indice sur la solution"""
    model_config = ConfigDict(from_attributes=True)

    hint_type: str = Field(..., description="Type d'indice")
    message: str = Field(..., description="Message d'indice")
    positions: Optional[List[int]] = Field(None, description="Positions concernées")
    colors: Optional[List[int]] = Field(None, description="Couleurs concernées")
    quantum_generated: bool = Field(default=False, description="Généré quantiquement")


class SolutionReveal(BaseModel):
    """Révélation de la solution"""
    model_config = ConfigDict(from_attributes=True)

    solution: List[int] = Field(..., description="Solution complète")
    revealed_at: datetime = Field(..., description="Date de révélation")
    reason: str = Field(..., description="Raison de la révélation")


class GameExport(BaseModel):
    """Export complet d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_info: GameFull = Field(..., description="Informations de la partie")
    statistics: GameStatistics = Field(..., description="Statistiques")
    solution: List[int] = Field(..., description="Solution")
    export_date: datetime = Field(..., description="Date d'export")


class GameReplay(BaseModel):
    """Données de replay d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    attempts_sequence: List[AttemptInfo] = Field(..., description="Séquence des tentatives")
    solution: List[int] = Field(..., description="Solution")
    quantum_data: Optional[Dict[str, Any]] = Field(None, description="Données quantiques")


# === SCHÉMAS DE VALIDATION ===

class GameValidation(BaseModel):
    """Validation des données de jeu"""
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool = Field(..., description="Données valides")
    errors: List[str] = Field(default_factory=list, description="Erreurs détectées")
    warnings: List[str] = Field(default_factory=list, description="Avertissements")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions")
    quantum_compatible: bool = Field(default=True, description="Compatible avec le mode quantique")


class SolutionValidation(BaseModel):
    """Validation d'une solution"""
    model_config = ConfigDict(from_attributes=True)

    is_valid_solution: bool = Field(..., description="Solution valide")
    combination: List[int] = Field(..., description="Combinaison validée")
    matches_constraints: bool = Field(..., description="Respecte les contraintes")
    difficulty_appropriate: bool = Field(..., description="Appropriée à la difficulté")
    quantum_generated: bool = Field(default=False, description="Générée quantiquement")


# === SCHÉMAS DE RÉPONSE ===

class MessageResponse(BaseModel):
    """Réponse simple avec message"""
    model_config = ConfigDict(from_attributes=True)

    message: str = Field(..., description="Message de réponse")
    success: bool = Field(default=True, description="Succès de l'opération")
    data: Optional[Dict[str, Any]] = Field(None, description="Données supplémentaires")


# === RÉSOLUTION DES RÉFÉRENCES FORWARD ===

# Mise à jour des références forward pour les modèles imbriqués
GameFull.model_rebuild()
ParticipantInfo.model_rebuild()
AttemptInfo.model_rebuild()


# === EXPORTS ===

__all__ = [
    # Création et modification
    "GameCreate", "GameJoin", "GameUpdate", "AttemptCreate", "AttemptResult",

    # Information avec données quantiques
    "GameInfo", "GamePublic", "GameFull", "ParticipantInfo", "AttemptInfo",

    # Recherche
    "GameSearch", "GameList",

    # Statistiques quantiques
    "GameStatistics", "PlayerGameStats",

    # Schémas quantiques spécifiques
    "QuantumGameInfo", "QuantumHintRequest", "QuantumHintResponse",

    # Export
    "GameExport", "GameReplay", "SolutionHint", "SolutionReveal",

    # Validation
    "GameValidation", "SolutionValidation",

    # Réponses
    "MessageResponse","GameCreateResponse"
]