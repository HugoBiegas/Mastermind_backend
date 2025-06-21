"""
Schémas Pydantic pour le multijoueur - Version corrigée pour cohérence avec le frontend
Compatible avec les types TypeScript du frontend React.js
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

# =====================================================
# ÉNUMÉRATIONS CORRESPONDANT AU FRONTEND
# =====================================================

class MultiplayerGameType(str, Enum):
    """Types de parties multijoueur correspondant au frontend"""
    MULTI_MASTERMIND = "multi_mastermind"
    BATTLE_ROYALE = "battle_royale"
    TOURNAMENT = "tournament"


class Difficulty(str, Enum):
    """Niveaux de difficulté"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class GameStatus(str, Enum):
    """Statuts d'une partie"""
    WAITING = "waiting"
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class PlayerStatus(str, Enum):
    """Statut des joueurs"""
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"
    ELIMINATED = "eliminated"


class ItemType(str, Enum):
    """Types d'objets"""
    EXTRA_HINT = "extra_hint"
    TIME_BONUS = "time_bonus"
    SKIP_MASTERMIND = "skip_mastermind"
    DOUBLE_SCORE = "double_score"
    FREEZE_TIME = "freeze_time"
    ADD_MASTERMIND = "add_mastermind"


# =====================================================
# SCHÉMAS DE REQUÊTE (CORRESPONDANT AU FRONTEND)
# =====================================================

class MultiplayerGameCreateRequest(BaseModel):
    """Requête de création de partie multijoueur - Structure attendue par le frontend"""
    model_config = ConfigDict(from_attributes=True)

    game_type: MultiplayerGameType = Field(..., description="Type de partie")
    difficulty: Difficulty = Field(..., description="Difficulté")
    total_masterminds: int = Field(3, ge=1, le=12, description="Nombre de masterminds")
    max_players: int = Field(6, ge=2, le=12, description="Nombre max de joueurs")
    is_private: bool = Field(False, description="Partie privée")
    password: Optional[str] = Field(None, description="Mot de passe")
    items_enabled: bool = Field(True, description="Objets activés")
    allow_spectators: bool = Field(True, description="Spectateurs autorisés")
    enable_chat: bool = Field(True, description="Chat activé")
    quantum_enabled: bool = Field(False, description="Mode quantique")


class JoinGameRequest(BaseModel):
    """Requête pour rejoindre une partie"""
    model_config = ConfigDict(from_attributes=True)

    password: Optional[str] = Field(None, description="Mot de passe")
    as_spectator: Optional[bool] = Field(False, description="Rejoindre en tant que spectateur")


class MultiplayerAttemptRequest(BaseModel):
    """Requête de tentative multijoueur"""
    model_config = ConfigDict(from_attributes=True)

    mastermind_number: int = Field(..., description="Numéro du mastermind")
    combination: List[int] = Field(..., description="Combinaison proposée")


class ItemUseRequest(BaseModel):
    """Requête d'utilisation d'objet"""
    model_config = ConfigDict(from_attributes=True)

    item_type: ItemType = Field(..., description="Type d'objet")
    target_players: Optional[List[str]] = Field(None, description="Joueurs ciblés")


# =====================================================
# SCHÉMAS DE RÉPONSE (STRUCTURE ATTENDUE PAR LE FRONTEND)
# =====================================================

class PlayerProgress(BaseModel):
    """Progression d'un joueur - Structure exacte attendue par le frontend"""
    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom d'utilisateur")
    status: PlayerStatus = Field(..., description="Statut du joueur")
    score: int = Field(0, description="Score actuel")
    current_mastermind: int = Field(1, description="Mastermind actuel")
    attempts_count: int = Field(0, description="Nombre de tentatives")
    items: List[Dict[str, Any]] = Field(default_factory=list, description="Objets possédés")
    active_effects: List[Dict[str, Any]] = Field(default_factory=list, description="Effets actifs")
    is_host: bool = Field(False, description="Est l'hôte")
    join_order: int = Field(0, description="Ordre d'arrivée")


class GameMastermind(BaseModel):
    """Mastermind dans une partie"""
    model_config = ConfigDict(from_attributes=True)

    number: int = Field(..., description="Numéro du mastermind")
    combination_length: int = Field(4, description="Longueur de la combinaison")
    available_colors: int = Field(6, description="Nombre de couleurs")
    max_attempts: int = Field(12, description="Tentatives maximum")
    is_current: bool = Field(False, description="Mastermind actuel")
    completed_by: List[str] = Field(default_factory=list, description="Complété par")


class MultiplayerGame(BaseModel):
    """Partie multijoueur - Structure exacte attendue par le frontend"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de la room")
    game_type: MultiplayerGameType = Field(..., description="Type de partie")
    difficulty: Difficulty = Field(..., description="Difficulté")
    status: GameStatus = Field(..., description="Statut de la partie")

    # Configuration
    max_players: int = Field(..., description="Joueurs maximum")
    current_players: int = Field(0, description="Joueurs actuels")
    is_private: bool = Field(False, description="Partie privée")
    items_enabled: bool = Field(True, description="Objets activés")
    quantum_enabled: bool = Field(False, description="Mode quantique")
    allow_spectators: bool = Field(True, description="Spectateurs autorisés")
    enable_chat: bool = Field(True, description="Chat activé")

    # Progression
    current_mastermind: int = Field(1, description="Mastermind actuel")
    total_masterminds: int = Field(3, description="Total de masterminds")
    masterminds: List[GameMastermind] = Field(default_factory=list, description="Liste des masterminds")

    # Participants
    players: List[PlayerProgress] = Field(default_factory=list, description="Liste des joueurs")
    spectators: List[Dict[str, Any]] = Field(default_factory=list, description="Spectateurs")

    # Créateur
    creator: Dict[str, str] = Field(..., description="Créateur de la partie")

    # Timestamps
    created_at: str = Field(..., description="Date de création")
    started_at: Optional[str] = Field(None, description="Date de début")
    finished_at: Optional[str] = Field(None, description="Date de fin")
    estimated_finish: Optional[str] = Field(None, description="Fin estimée")

    # Jeu de base (pour compatibilité avec le frontend)
    base_game: Optional[Dict[str, Any]] = Field(None, description="Jeu de base")


class PublicGameListing(BaseModel):
    """Listing public des parties pour le lobby"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de la room")
    name: Optional[str] = Field(None, description="Nom de la partie")
    game_type: MultiplayerGameType = Field(..., description="Type de partie")
    difficulty: Difficulty = Field(..., description="Difficulté")
    status: GameStatus = Field(..., description="Statut")

    current_players: int = Field(..., description="Joueurs actuels")
    max_players: int = Field(..., description="Joueurs maximum")
    has_password: bool = Field(False, description="Protégée par mot de passe")
    allow_spectators: bool = Field(True, description="Spectateurs autorisés")
    items_enabled: bool = Field(True, description="Objets activés")
    quantum_enabled: bool = Field(False, description="Mode quantique")

    creator_username: str = Field(..., description="Nom du créateur")
    created_at: str = Field(..., description="Date de création")
    estimated_finish: Optional[str] = Field(None, description="Fin estimée")


class MultiplayerAttemptResponse(BaseModel):
    """Réponse à une tentative multijoueur"""
    model_config = ConfigDict(from_attributes=True)

    success: bool = Field(..., description="Tentative réussie")
    correct_positions: int = Field(..., description="Positions correctes")
    correct_colors: int = Field(..., description="Couleurs correctes")
    is_solution: bool = Field(False, description="Solution trouvée")
    score_gained: int = Field(0, description="Score gagné")
    items_obtained: List[Dict[str, Any]] = Field(default_factory=list, description="Objets obtenus")
    mastermind_completed: bool = Field(False, description="Mastermind complété")
    game_finished: bool = Field(False, description="Partie terminée")
    updated_game_state: Optional[MultiplayerGame] = Field(None, description="État de jeu mis à jour")


class ActiveEffect(BaseModel):
    """Effet actif sur un joueur"""
    model_config = ConfigDict(from_attributes=True)

    effect_type: str = Field(..., description="Type d'effet")
    source_player: str = Field(..., description="Joueur source")
    duration: int = Field(..., description="Durée restante")
    intensity: float = Field(1.0, description="Intensité")


class ItemUseResponse(BaseModel):
    """Réponse à l'utilisation d'un objet"""
    model_config = ConfigDict(from_attributes=True)

    success: bool = Field(..., description="Utilisation réussie")
    message: str = Field(..., description="Message de résultat")
    effects_applied: List[ActiveEffect] = Field(default_factory=list, description="Effets appliqués")
    updated_game_state: Optional[MultiplayerGame] = Field(None, description="État de jeu mis à jour")


# =====================================================
# RÉPONSES PAGINATION ET FILTRES
# =====================================================

class MultiplayerGameFilters(BaseModel):
    """Filtres pour la recherche de parties"""
    model_config = ConfigDict(from_attributes=True)

    game_type: Optional[MultiplayerGameType] = None
    difficulty: Optional[Difficulty] = None
    max_players: Optional[int] = Field(None, ge=2, le=12)
    has_password: Optional[bool] = None
    allow_spectators: Optional[bool] = None
    quantum_enabled: Optional[bool] = None
    status: Optional[GameStatus] = None
    search_term: Optional[str] = None
    has_slots: Optional[bool] = None
    sort_by: Optional[str] = Field("created_at", regex="^(created_at|current_players|difficulty)$")
    sort_order: Optional[str] = Field("desc", regex="^(asc|desc)$")


class LobbyListResponse(BaseModel):
    """Réponse pour la liste du lobby"""
    model_config = ConfigDict(from_attributes=True)

    games: List[PublicGameListing] = Field(..., description="Liste des parties")
    total: int = Field(..., description="Total de parties")
    page: int = Field(..., description="Page actuelle")
    limit: int = Field(..., description="Limite par page")
    has_next: bool = Field(False, description="Page suivante disponible")
    has_prev: bool = Field(False, description="Page précédente disponible")


# =====================================================
# ÉVÉNEMENTS WEBSOCKET
# =====================================================

class WebSocketMessage(BaseModel):
    """Message WebSocket standardisé"""
    model_config = ConfigDict(from_attributes=True)

    type: str = Field(..., description="Type d'événement")
    data: Dict[str, Any] = Field(..., description="Données de l'événement")
    timestamp: float = Field(..., description="Timestamp")
    game_id: Optional[str] = Field(None, description="ID de la partie")


class PlayerJoinedEvent(BaseModel):
    """Événement : joueur rejoint"""
    model_config = ConfigDict(from_attributes=True)

    username: str = Field(..., description="Nom d'utilisateur")
    players_count: int = Field(..., description="Nombre de joueurs")
    player_data: PlayerProgress = Field(..., description="Données du joueur")


class PlayerLeftEvent(BaseModel):
    """Événement : joueur quitte"""
    model_config = ConfigDict(from_attributes=True)

    username: str = Field(..., description="Nom d'utilisateur")
    players_count: int = Field(..., description="Nombre de joueurs")
    reason: Optional[str] = Field(None, description="Raison du départ")


class GameStartedEvent(BaseModel):
    """Événement : partie démarrée"""
    model_config = ConfigDict(from_attributes=True)

    game_id: str = Field(..., description="ID de la partie")
    current_mastermind: int = Field(..., description="Mastermind actuel")
    updated_game_state: MultiplayerGame = Field(..., description="État de jeu")


class AttemptMadeEvent(BaseModel):
    """Événement : tentative effectuée"""
    model_config = ConfigDict(from_attributes=True)

    player_id: str = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom d'utilisateur")
    mastermind_number: int = Field(..., description="Numéro du mastermind")
    result: MultiplayerAttemptResponse = Field(..., description="Résultat de la tentative")


class ItemUsedEvent(BaseModel):
    """Événement : objet utilisé"""
    model_config = ConfigDict(from_attributes=True)

    player_id: str = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom d'utilisateur")
    item_type: ItemType = Field(..., description="Type d'objet")
    target_players: Optional[List[str]] = Field(None, description="Joueurs ciblés")
    effects: List[ActiveEffect] = Field(default_factory=list, description="Effets appliqués")


class GameFinishedEvent(BaseModel):
    """Événement : partie terminée"""
    model_config = ConfigDict(from_attributes=True)

    game_id: str = Field(..., description="ID de la partie")
    winner: Optional[str] = Field(None, description="Gagnant")
    final_standings: List[PlayerProgress] = Field(..., description="Classement final")
    game_stats: Dict[str, Any] = Field(..., description="Statistiques de la partie")


# =====================================================
# STRUCTURE DE RÉPONSE API STANDARDISÉE
# =====================================================

class MultiplayerApiResponse(BaseModel):
    """Réponse API standardisée pour le multijoueur"""
    model_config = ConfigDict(from_attributes=True)

    success: bool = Field(..., description="Succès de l'opération")
    data: Any = Field(..., description="Données de réponse")
    message: Optional[str] = Field(None, description="Message informatif")
    error: Optional[str] = Field(None, description="Message d'erreur")
    timestamp: str = Field(..., description="Timestamp de la réponse")