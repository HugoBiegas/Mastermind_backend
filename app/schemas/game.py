"""
Schémas Pydantic pour la gestion des jeux
MODIFIÉ: Ajout du support quantique dans les schémas
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, validator

from app.models.game import GameType, GameMode, GameStatus, Difficulty, ParticipationStatus


# === SCHÉMAS DE BASE AVEC SUPPORT QUANTIQUE ===

class GameCreate(BaseModel):
    """Schéma pour créer une partie avec support quantique"""
    model_config = ConfigDict(from_attributes=True)

    game_type: GameType = Field(default=GameType.CLASSIC, description="Type de jeu")
    game_mode: GameMode = Field(default=GameMode.SINGLE, description="Mode de jeu")
    difficulty: Difficulty = Field(default=Difficulty.MEDIUM, description="Difficulté")

    max_attempts: Optional[int] = Field(default=12, ge=1, le=50, description="Tentatives max")
    time_limit: Optional[int] = Field(default=None, ge=60, le=3600, description="Limite de temps (secondes)")
    max_players: int = Field(default=1, ge=1, le=8, description="Joueurs max")

    is_private: bool = Field(default=False, description="Partie privée")
    password: Optional[str] = Field(default=None, min_length=1, max_length=50, description="Mot de passe")
    room_code: Optional[str] = Field(default=None, min_length=4, max_length=10, description="Code personnalisé")

    allow_spectators: bool = Field(default=True, description="Autoriser les spectateurs")
    enable_chat: bool = Field(default=True, description="Activer le chat")

    # NOUVEAUX CHAMPS QUANTIQUES
    quantum_enabled: bool = Field(default=False, description="Activer les fonctionnalités quantiques")
    quantum_shots: Optional[int] = Field(default=1024, ge=100, le=8192, description="Nombre de mesures quantiques")

    # Paramètres de jeu
    combination_length: int = Field(default=4, ge=3, le=8, description="Longueur de la combinaison")
    available_colors: int = Field(default=6, ge=4, le=10, description="Nombre de couleurs disponibles")

    settings: Optional[Dict[str, Any]] = Field(default=None, description="Paramètres avancés")

    @validator('game_type')
    def validate_quantum_consistency(cls, v, values):
        """Valide la cohérence entre game_type et quantum_enabled"""
        if v == GameType.QUANTUM:
            values['quantum_enabled'] = True
        return v


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
    """Résultat d'une tentative avec informations quantiques"""
    model_config = ConfigDict(from_attributes=True)

    attempt_number: int = Field(..., description="Numéro de la tentative")
    combination: List[int] = Field(..., description="Combinaison proposée")
    exact_matches: int = Field(..., description="Couleurs bien placées")
    position_matches: int = Field(..., description="Couleurs mal placées")
    is_correct: bool = Field(..., description="Solution trouvée")

    # NOUVEAUX CHAMPS QUANTIQUES
    quantum_calculated: bool = Field(default=False, description="Calculé avec algorithmes quantiques")
    quantum_hint_used: bool = Field(default=False, description="Hint quantique utilisé")
    quantum_efficiency: Optional[float] = Field(None, description="Efficacité quantique (0-1)")

    remaining_attempts: Optional[int] = Field(None, description="Tentatives restantes")
    game_finished: bool = Field(default=False, description="Partie terminée")
    score: int = Field(default=0, description="Score classique")
    quantum_score: int = Field(default=0, description="Score quantique")


class GameInfo(BaseModel):
    """Informations basiques d'une partie avec support quantique"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de la room")
    game_type: GameType = Field(..., description="Type de jeu")
    game_mode: GameMode = Field(..., description="Mode de jeu")
    status: GameStatus = Field(..., description="Statut actuel")
    difficulty: Difficulty = Field(..., description="Difficulté")

    # NOUVEAUX CHAMPS QUANTIQUES
    quantum_enabled: bool = Field(default=False, description="Fonctionnalités quantiques activées")
    quantum_solution: bool = Field(default=False, description="Solution générée quantiquement")

    max_players: int = Field(..., description="Joueurs maximum")
    current_players: int = Field(..., description="Joueurs actuels")
    is_private: bool = Field(..., description="Partie privée")

    created_at: datetime = Field(..., description="Date de création")
    started_at: Optional[datetime] = Field(None, description="Date de début")


class ParticipantInfo(BaseModel):
    """Informations sur un participant avec données quantiques"""
    model_config = ConfigDict(from_attributes=True)

    player_id: UUID = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom d'utilisateur")
    status: ParticipationStatus = Field(..., description="Statut de participation")
    score: int = Field(..., description="Score classique")
    quantum_score: int = Field(default=0, description="Score quantique")
    attempts_made: int = Field(..., description="Tentatives effectuées")
    hints_used: int = Field(..., description="Hints utilisés")
    quantum_hints_used: int = Field(default=0, description="Hints quantiques utilisés")
    rank: Optional[int] = Field(None, description="Classement")
    joined_at: datetime = Field(..., description="Date de participation")


class AttemptInfo(BaseModel):
    """Informations sur une tentative avec données quantiques"""
    model_config = ConfigDict(from_attributes=True)

    attempt_number: int = Field(..., description="Numéro de tentative")
    player_id: UUID = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom du joueur")
    combination: List[int] = Field(..., description="Combinaison tentée")
    exact_matches: int = Field(..., description="Bien placés")
    position_matches: int = Field(..., description="Mal placés")
    is_correct: bool = Field(..., description="Solution correcte")
    quantum_calculated: bool = Field(default=False, description="Calculé quantiquement")
    quantum_efficiency: Optional[float] = Field(None, description="Efficacité quantique")
    created_at: datetime = Field(..., description="Date de la tentative")


class GameFull(BaseModel):
    """Détails complets d'une partie avec informations quantiques"""
    model_config = ConfigDict(from_attributes=True)

    # Informations de base
    id: UUID = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de la room")
    game_type: GameType = Field(..., description="Type de jeu")
    game_mode: GameMode = Field(..., description="Mode de jeu")
    status: GameStatus = Field(..., description="Statut")
    difficulty: Difficulty = Field(..., description="Difficulté")

    # Configuration de jeu
    combination_length: int = Field(..., description="Longueur combinaison")
    available_colors: int = Field(..., description="Couleurs disponibles")
    max_attempts: Optional[int] = Field(None, description="Tentatives max")
    time_limit: Optional[int] = Field(None, description="Limite de temps")
    max_players: int = Field(..., description="Joueurs max")

    # NOUVEAUX CHAMPS QUANTIQUES
    quantum_enabled: bool = Field(default=False, description="Mode quantique activé")
    quantum_solution: bool = Field(default=False, description="Solution quantique")
    quantum_settings: Optional[Dict[str, Any]] = Field(None, description="Configuration quantique")
    quantum_backend_available: bool = Field(default=False, description="Backend quantique disponible")

    # Paramètres
    is_private: bool = Field(..., description="Partie privée")
    allow_spectators: bool = Field(..., description="Spectateurs autorisés")
    enable_chat: bool = Field(..., description="Chat activé")
    settings: Optional[Dict[str, Any]] = Field(None, description="Paramètres")

    # Participants et tentatives
    participants: List[ParticipantInfo] = Field(..., description="Liste des participants")
    attempts: List[AttemptInfo] = Field(..., description="Historique des tentatives")

    # Métadonnées
    created_by: UUID = Field(..., description="Créateur")
    created_at: datetime = Field(..., description="Date de création")
    updated_at: datetime = Field(..., description="Dernière mise à jour")
    started_at: Optional[datetime] = Field(None, description="Date de début")
    finished_at: Optional[datetime] = Field(None, description="Date de fin")
    duration: Optional[int] = Field(None, description="Durée en secondes")


class GamePublic(BaseModel):
    """Informations publiques d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de la room")
    game_type: GameType = Field(..., description="Type de jeu")
    game_mode: GameMode = Field(..., description="Mode de jeu")
    status: GameStatus = Field(..., description="Statut")
    difficulty: Difficulty = Field(..., description="Difficulté")
    quantum_enabled: bool = Field(default=False, description="Mode quantique")
    max_players: int = Field(..., description="Joueurs max")
    current_players: int = Field(..., description="Joueurs actuels")
    has_password: bool = Field(..., description="Protégée par mot de passe")
    allow_spectators: bool = Field(..., description="Spectateurs autorisés")
    created_at: datetime = Field(..., description="Date de création")


# === SCHÉMAS QUANTIQUES SPÉCIFIQUES ===

class QuantumGameInfo(BaseModel):
    """Informations quantiques détaillées d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    is_quantum_enabled: bool = Field(..., description="Mode quantique activé")
    quantum_solution: bool = Field(..., description="Solution générée quantiquement")
    quantum_settings: Dict[str, Any] = Field(..., description="Configuration quantique")
    quantum_backend_status: Dict[str, Any] = Field(..., description="État du backend quantique")

    # Statistiques d'utilisation quantique
    total_attempts: int = Field(..., description="Tentatives totales")
    quantum_attempts: int = Field(..., description="Tentatives calculées quantiquement")
    quantum_usage_ratio: float = Field(..., description="Ratio d'utilisation quantique")

    # Informations techniques
    shots_used: int = Field(default=1024, description="Mesures quantiques utilisées")
    qubits_used: int = Field(default=5, description="Qubits utilisés")
    algorithms_used: List[str] = Field(default_factory=list, description="Algorithmes quantiques utilisés")


class QuantumHintRequest(BaseModel):
    """Demande de hint quantique"""
    model_config = ConfigDict(from_attributes=True)

    hint_type: str = Field(..., description="Type de hint")
    cost_accepted: bool = Field(default=True, description="Accepte le coût")
    custom_shots: Optional[int] = Field(None, ge=100, le=8192, description="Mesures personnalisées")

    @validator('hint_type')
    def validate_hint_type(cls, v):
        allowed_hints = ["grover", "superposition", "entanglement", "basic"]
        if v not in allowed_hints:
            raise ValueError(f"Type de hint invalide. Autorisés: {allowed_hints}")
        return v


class QuantumHintResponse(BaseModel):
    """Réponse de hint quantique"""
    model_config = ConfigDict(from_attributes=True)

    message: str = Field(..., description="Message du hint")
    type: str = Field(..., description="Type de hint")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Niveau de confiance")
    algorithm: str = Field(..., description="Algorithme utilisé")
    qubits: int = Field(..., description="Qubits utilisés")
    execution_time: float = Field(..., description="Temps d'exécution")
    cost: int = Field(default=0, description="Coût en points")
    quantum_data: Optional[Dict[str, Any]] = Field(None, description="Données quantiques brutes")


# === SCHÉMAS DE RECHERCHE ET LISTING ===

class GameSearch(BaseModel):
    """Paramètres de recherche de parties avec filtre quantique"""
    model_config = ConfigDict(from_attributes=True)

    game_type: Optional[GameType] = Field(None, description="Type de jeu")
    game_mode: Optional[GameMode] = Field(None, description="Mode de jeu")
    status: Optional[GameStatus] = Field(None, description="Statut")
    difficulty: Optional[Difficulty] = Field(None, description="Difficulté")
    quantum_only: bool = Field(default=False, description="Parties quantiques uniquement")
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
    quantum_games: int = Field(default=0, description="Nombre de parties quantiques")


# === SCHÉMAS DE STATISTIQUES QUANTIQUES ===

class GameStatistics(BaseModel):
    """Statistiques d'une partie avec données quantiques"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    total_attempts: int = Field(..., description="Tentatives totales")
    total_players: int = Field(..., description="Joueurs totaux")
    average_attempts: float = Field(..., description="Moyenne des tentatives")
    success_rate: float = Field(..., description="Taux de réussite")
    average_time: Optional[float] = Field(None, description="Temps moyen")

    # NOUVELLES STATISTIQUES QUANTIQUES
    quantum_attempts: int = Field(default=0, description="Tentatives quantiques")
    quantum_hints_used: int = Field(default=0, description="Hints quantiques utilisés")
    quantum_efficiency: float = Field(default=0.0, description="Efficacité quantique moyenne")
    quantum_usage_rate: float = Field(default=0.0, description="Taux d'utilisation quantique")


class PlayerGameStats(BaseModel):
    """Statistiques d'un joueur avec données quantiques"""
    model_config = ConfigDict(from_attributes=True)

    player_id: UUID = Field(..., description="ID du joueur")
    games_played: int = Field(..., description="Parties jouées")
    games_won: int = Field(..., description="Parties gagnées")
    win_rate: float = Field(..., description="Taux de victoire")
    average_attempts: float = Field(..., description="Tentatives moyennes")
    best_score: int = Field(..., description="Meilleur score")
    total_score: int = Field(..., description="Score total")

    # NOUVELLES STATISTIQUES QUANTIQUES
    quantum_games_played: int = Field(default=0, description="Parties quantiques jouées")
    total_quantum_score: int = Field(default=0, description="Score quantique total")
    quantum_hints_mastery: float = Field(default=0.0, description="Maîtrise des hints quantiques")
    quantum_efficiency_rating: float = Field(default=0.0, description="Note d'efficacité quantique")


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


# === SCHÉMAS D'EXPORT ET DEBUG ===

class SolutionHint(BaseModel):
    """Indice sur la solution"""
    model_config = ConfigDict(from_attributes=True)

    hint_type: str = Field(..., description="Type d'indice")
    message: str = Field(..., description="Message d'indice")
    positions: Optional[List[int]] = Field(None, description="Positions concernées")
    colors: Optional[List[int]] = Field(None, description="Couleurs concernées")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Niveau de confiance")
    quantum_generated: bool = Field(default=False, description="Généré quantiquement")


class SolutionReveal(BaseModel):
    """Révélation de la solution (debug)"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    solution: List[int] = Field(..., description="Solution complète")
    quantum_generated: bool = Field(default=False, description="Générée quantiquement")
    generation_method: Optional[str] = Field(None, description="Méthode de génération")
    revealed_by: UUID = Field(..., description="ID de l'utilisateur qui révèle")
    revealed_at: datetime = Field(..., description="Date de révélation")


class GameExport(BaseModel):
    """Export complet d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_info: GameFull = Field(..., description="Informations complètes")
    quantum_data: Optional[QuantumGameInfo] = Field(None, description="Données quantiques")
    export_format: str = Field(..., description="Format d'export")
    exported_at: datetime = Field(..., description="Date d'export")
    exported_by: UUID = Field(..., description="Exporté par")


class GameReplay(BaseModel):
    """Replay d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    attempts_sequence: List[AttemptInfo] = Field(..., description="Séquence des tentatives")
    final_result: Dict[str, Any] = Field(..., description="Résultat final")
    quantum_insights: Optional[Dict[str, Any]] = Field(None, description="Insights quantiques")

class GameJoin(BaseModel):
    """Schéma pour rejoindre une partie"""
    model_config = ConfigDict(from_attributes=True)

    password: Optional[str] = Field(default=None, description="Mot de passe de la partie")
    player_name: Optional[str] = Field(default=None, max_length=50, description="Nom d'affichage")


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

# === RÉSOLUTION DES RÉFÉRENCES FORWARD ===

# Mise à jour des références forward pour les modèles imbriqués
GameFull.model_rebuild()
ParticipantInfo.model_rebuild()
AttemptInfo.model_rebuild()


# === EXPORTS ===

__all__ = [
    # Création et modification
    "GameCreate", "GameJoin", "GameUpdate",

    # Gameplay avec support quantique
    "AttemptCreate", "AttemptResult", "SolutionHint", "SolutionReveal",

    # Information avec données quantiques
    "GameInfo", "GamePublic", "GameFull", "ParticipantInfo", "AttemptInfo",

    # Recherche
    "GameSearch", "GameList",

    # Statistiques quantiques
    "GameStatistics", "PlayerGameStats",

    # Schémas quantiques spécifiques
    "QuantumGameInfo", "QuantumHintRequest", "QuantumHintResponse",

    # Export
    "GameExport", "GameReplay",

    # Validation
    "GameValidation", "SolutionValidation"
]