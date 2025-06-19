"""
Schémas Pydantic pour les fonctionnalités multijoueur
Validation des données, sérialisation, documentation API
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator, ConfigDict

from app.models.game import Difficulty, GameMode, GameStatus
from app.models.multijoueur import MultiplayerGameType, ItemType, PlayerStatus


# =====================================================
# SCHÉMAS DE BASE
# =====================================================

class ItemBase(BaseModel):
    """Schéma de base pour un objet"""
    type: str
    name: str
    description: str
    rarity: str
    obtained_at: datetime


class PlayerItemResponse(ItemBase):
    """Réponse pour un objet de joueur"""
    used_at: Optional[datetime] = None
    is_used: bool = False


class GameMastermindResponse(BaseModel):
    """Réponse pour un mastermind de partie"""
    id: UUID
    mastermind_number: int
    combination_length: int
    available_colors: int
    max_attempts: int
    is_active: bool
    is_completed: bool
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =====================================================
# CRÉATION ET GESTION DES PARTIES
# =====================================================

class MultiplayerGameCreate(BaseModel):
    """Schéma pour créer une partie multijoueur"""
    game_mode: GameMode = Field(GameMode.MULTIPLAYER, description="Mode de jeu (toujours multiplayer)")
    difficulty: Difficulty = Field(..., description="Difficulté de la partie")
    total_masterminds: int = Field(..., ge=3, le=12, description="Nombre total de masterminds")
    max_players: int = Field(..., ge=2, le=12, description="Nombre maximum de joueurs")
    is_private: bool = Field(False, description="Partie privée")
    password: Optional[str] = Field(None, max_length=50, description="Mot de passe si privée")
    items_enabled: bool = Field(True, description="Système d'objets activé")
    allow_spectators: bool = Field(False, description="Autoriser les spectateurs")
    enable_chat: bool = Field(True, description="Chat activé")

    @validator('total_masterminds')
    def validate_total_masterminds(cls, v):
        if v not in [3, 6, 9, 12]:
            raise ValueError('Le nombre de masterminds doit être 3, 6, 9 ou 12')
        return v

    @validator('password')
    def validate_password(cls, v, values):
        if values.get('is_private') and not v:
            raise ValueError('Un mot de passe est requis pour les parties privées')
        if not values.get('is_private') and v:
            raise ValueError('Mot de passe non autorisé pour les parties publiques')
        return v


class MultiplayerGameResponse(BaseModel):
    """Réponse complète pour une partie multijoueur"""
    id: UUID
    base_game_id: UUID
    room_code: str
    game_type: MultiplayerGameType
    total_masterminds: int
    difficulty: Difficulty
    current_mastermind: int
    is_final_mastermind: bool
    items_enabled: bool
    items_per_mastermind: int
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    # Informations de la partie de base
    status: GameStatus
    max_players: int
    current_players: int
    creator_username: str
    is_private: bool

    # Progression des joueurs
    player_progresses: List['PlayerProgressResponse'] = []
    masterminds: List[GameMastermindResponse] = []
    leaderboard: List['LeaderboardResponse'] = []

    model_config = ConfigDict(from_attributes=True)


class PublicGameListing(BaseModel):
    """Schéma pour lister les parties publiques"""
    id: UUID
    room_code: str
    creator_username: str
    difficulty: Difficulty
    total_masterminds: int
    current_players: int
    max_players: int
    status: GameStatus
    created_at: datetime
    avg_player_level: Optional[float] = None
    items_enabled: bool = True

    model_config = ConfigDict(from_attributes=True)


class JoinGameRequest(BaseModel):
    """Requête pour rejoindre une partie"""
    password: Optional[str] = Field(None, max_length=50, description="Mot de passe si partie privée")


class JoinGameResponse(BaseModel):
    """Réponse pour rejoindre une partie"""
    success: bool
    game: MultiplayerGameResponse
    message: str


# =====================================================
# GAMEPLAY
# =====================================================

class MultiplayerAttemptRequest(BaseModel):
    """Requête pour faire une tentative"""
    mastermind_number: int = Field(..., ge=1, description="Numéro du mastermind")
    combination: List[int] = Field(..., min_items=3, max_items=8, description="Combinaison proposée")

    @validator('combination')
    def validate_combination(cls, v):
        if not v:
            raise ValueError('La combinaison ne peut pas être vide')
        if any(color < 0 or color > 7 for color in v):
            raise ValueError('Les couleurs doivent être entre 0 et 7')
        return v


class AttemptResultResponse(BaseModel):
    """Réponse pour le résultat d'une tentative"""
    id: UUID
    attempt_number: int
    combination: List[int]
    exact_matches: int
    position_matches: int
    is_correct: bool
    attempt_score: int
    time_taken: float
    quantum_calculated: bool = False
    quantum_probabilities: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MultiplayerAttemptResponse(BaseModel):
    """Réponse complète pour une tentative multijoueur"""
    attempt: AttemptResultResponse
    mastermind_completed: bool
    items_obtained: List[PlayerItemResponse] = []
    score: int
    next_mastermind: Optional[GameMastermindResponse] = None
    game_finished: bool = False
    final_position: Optional[int] = None


# =====================================================
# SYSTÈME D'OBJETS
# =====================================================

class ItemUseRequest(BaseModel):
    """Requête pour utiliser un objet"""
    item_type: ItemType = Field(..., description="Type d'objet à utiliser")
    target_players: Optional[List[UUID]] = Field(None, description="Joueurs cibles pour les malus")

    @validator('target_players')
    def validate_target_players(cls, v, values):
        item_type = values.get('item_type')
        if not item_type:
            return v

        # Vérifier si l'objet nécessite des cibles
        malus_items = [ItemType.FREEZE_TIME, ItemType.ADD_MASTERMIND,
                       ItemType.REDUCE_ATTEMPTS, ItemType.SCRAMBLE_COLORS]

        if item_type in malus_items and not v:
            raise ValueError('Des joueurs cibles sont requis pour cet objet')

        return v


class ItemUseResponse(BaseModel):
    """Réponse pour l'utilisation d'un objet"""
    success: bool
    message: str
    effect_applied: bool
    remaining_items: List[PlayerItemResponse]
    affected_players: List[UUID] = []
    effect_duration: Optional[int] = None


class AvailableItemResponse(BaseModel):
    """Réponse pour un objet disponible"""
    name: str
    description: str
    rarity: str
    is_self_target: bool
    effect_value: Optional[int] = None
    duration_seconds: Optional[int] = None


# =====================================================
# PROGRESSION ET CLASSEMENTS
# =====================================================

class PlayerProgressResponse(BaseModel):
    """Réponse pour la progression d'un joueur"""
    id: UUID
    user_id: UUID
    username: str
    current_mastermind: int
    completed_masterminds: int
    total_score: int
    total_time: float
    status: PlayerStatus
    is_finished: bool
    finish_position: Optional[int] = None
    finish_time: Optional[datetime] = None
    collected_items: List[PlayerItemResponse] = []
    used_items: List[PlayerItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class LeaderboardResponse(BaseModel):
    """Réponse pour une entrée du classement"""
    id: UUID
    user_id: UUID
    username: str
    final_position: int
    total_score: int
    masterminds_completed: int
    total_time: float
    total_attempts: int
    items_collected: int
    items_used: int
    best_mastermind_time: Optional[float] = None
    worst_mastermind_time: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


# =====================================================
# STATISTIQUES
# =====================================================

class PlayerStatsResponse(BaseModel):
    """Statistiques d'un joueur"""
    games_played: int
    games_won: int
    win_rate: float
    average_score: float
    total_masterminds_completed: int
    favorite_difficulty: str
    most_used_items: List[Dict[str, Any]] = []
    best_time: Optional[float] = None
    rank: int


class TopPlayerResponse(BaseModel):
    """Réponse pour un top joueur"""
    user_id: UUID
    username: str
    games_won: int
    average_score: float


class GlobalStatsResponse(BaseModel):
    """Statistiques globales du multijoueur"""
    total_multiplayer_games: int
    total_players: int
    average_game_duration: float
    most_popular_difficulty: str
    most_used_items: List[Dict[str, Any]] = []
    top_players: List[TopPlayerResponse] = []


# =====================================================
# WEBSOCKET EVENTS
# =====================================================

class WebSocketEventBase(BaseModel):
    """Schéma de base pour les événements WebSocket"""
    type: str
    data: Dict[str, Any]
    timestamp: float
    game_id: Optional[UUID] = None


class PlayerJoinedEvent(WebSocketEventBase):
    """Événement : joueur rejoint"""
    type: str = "PLAYER_JOINED"


class PlayerLeftEvent(WebSocketEventBase):
    """Événement : joueur quitte"""
    type: str = "PLAYER_LEFT"


class PlayerMastermindCompleteEvent(WebSocketEventBase):
    """Événement : mastermind complété"""
    type: str = "PLAYER_MASTERMIND_COMPLETE"


class ItemUsedEvent(WebSocketEventBase):
    """Événement : objet utilisé"""
    type: str = "ITEM_USED"


class EffectAppliedEvent(WebSocketEventBase):
    """Événement : effet appliqué"""
    type: str = "EFFECT_APPLIED"


class PlayerStatusChangedEvent(WebSocketEventBase):
    """Événement : statut joueur changé"""
    type: str = "PLAYER_STATUS_CHANGED"


class GameStateUpdateEvent(WebSocketEventBase):
    """Événement : mise à jour état de jeu"""
    type: str = "GAME_STATE_UPDATE"


class GameFinishedEvent(WebSocketEventBase):
    """Événement : partie terminée"""
    type: str = "GAME_FINISHED"


class AttemptMadeEvent(WebSocketEventBase):
    """Événement : tentative effectuée"""
    type: str = "ATTEMPT_MADE"


# =====================================================
# FILTRES ET PAGINATION
# =====================================================

class MultiplayerGameFilters(BaseModel):
    """Filtres pour la recherche de parties"""
    difficulty: Optional[Difficulty] = None
    max_players: Optional[int] = Field(None, ge=2, le=12)
    has_slots: Optional[bool] = None
    sort_by: Optional[str] = Field("created_at", regex="^(created_at|current_players|difficulty)$")
    sort_order: Optional[str] = Field("desc", regex="^(asc|desc)$")


# =====================================================
# MISE À JOUR DES RÉFÉRENCES CIRCULAIRES
# =====================================================

# Mise à jour des références pour éviter les imports circulaires
MultiplayerGameResponse.model_rebuild()
PlayerProgressResponse.model_rebuild()
LeaderboardResponse.model_rebuild()