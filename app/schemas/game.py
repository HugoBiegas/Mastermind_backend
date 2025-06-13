"""
Schémas Pydantic pour les jeux
Validation et sérialisation des données de parties
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.game import GameType, GameMode, GameStatus, PlayerStatus, Difficulty


# === SCHÉMAS DE BASE ===
class GameBase(BaseModel):
    """Schéma de base pour les jeux"""
    game_type: GameType = Field(
        GameType.CLASSIC,
        description="Type de jeu"
    )
    game_mode: GameMode = Field(
        GameMode.SOLO,
        description="Mode de jeu"
    )
    difficulty: Difficulty = Field(
        Difficulty.NORMAL,
        description="Niveau de difficulté"
    )
    max_attempts: int = Field(
        10,
        ge=1,
        le=20,
        description="Nombre maximum de tentatives"
    )
    time_limit: Optional[int] = Field(
        None,
        gt=0,
        le=3600,
        description="Limite de temps en secondes"
    )
    max_players: int = Field(
        1,
        ge=1,
        le=8,
        description="Nombre maximum de joueurs"
    )


class GameCreate(GameBase):
    """Schéma pour la création d'une partie"""
    room_code: Optional[str] = Field(
        None,
        min_length=4,
        max_length=20,
        pattern=r'^[A-Z0-9]+$',
        description="Code de room personnalisé"
    )
    is_private: bool = Field(
        False,
        description="Partie privée"
    )
    password: Optional[str] = Field(
        None,
        min_length=4,
        max_length=50,
        description="Mot de passe pour rejoindre"
    )
    settings: Optional[Dict[str, Any]] = Field(
        {},
        description="Paramètres personnalisés"
    )

    @field_validator('max_players')
    @classmethod
    def validate_max_players_for_mode(cls, v, info):
        """Valide le nombre de joueurs selon le mode"""
        data = info.data
        game_mode = data.get('game_mode')
        if game_mode == GameMode.SOLO and v != 1:
            raise ValueError("Mode solo: 1 joueur maximum")
        elif game_mode == GameMode.MULTIPLAYER and v < 2:
            raise ValueError("Mode multijoueur: minimum 2 joueurs")
        return v


class GameUpdate(BaseModel):
    """Schéma pour la mise à jour d'une partie"""
    status: Optional[GameStatus] = None
    max_attempts: Optional[int] = Field(None, ge=1, le=20)
    time_limit: Optional[int] = Field(None, gt=0, le=3600)
    settings: Optional[Dict[str, Any]] = None


class GameJoin(BaseModel):
    """Schéma pour rejoindre une partie"""
    room_code: str = Field(
        ...,
        min_length=4,
        max_length=20,
        pattern=r'^[A-Z0-9]+$',
        description="Code de la room"
    )
    password: Optional[str] = Field(
        None,
        description="Mot de passe si requis"
    )
    player_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Nom du joueur personnalisé"
    )


class GameLeave(BaseModel):
    """Schéma pour quitter une partie"""
    reason: Optional[str] = Field(
        None,
        max_length=200,
        description="Raison de départ"
    )


# === SCHÉMAS COMPLETS ===
class GameInfo(BaseModel):
    """Informations complètes d'une partie"""
    id: UUID
    room_id: str
    created_by: Optional[UUID]
    game_type: GameType
    game_mode: GameMode
    difficulty: Difficulty
    status: GameStatus
    max_attempts: int
    time_limit: Optional[int]
    max_players: int
    current_players_count: int
    is_private: bool
    has_password: bool
    settings: Dict[str, Any]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    estimated_duration: Optional[int]

    model_config = {"from_attributes": True}

    @property
    def is_full(self) -> bool:
        """Vérifie si la partie est complète"""
        return self.current_players_count >= self.max_players

    @property
    def can_join(self) -> bool:
        """Vérifie si on peut rejoindre la partie"""
        return (
            self.status == GameStatus.WAITING_PLAYERS and
            not self.is_full
        )

    @property
    def duration(self) -> Optional[timedelta]:
        """Calcule la durée de la partie"""
        if self.started_at and self.finished_at:
            return self.finished_at - self.started_at
        elif self.started_at:
            return datetime.utcnow() - self.started_at
        return None


class GameFull(GameInfo):
    """Partie complète avec joueurs et données détaillées"""
    players: List["GamePlayerInfo"] = []
    attempts_history: List["AttemptResult"] = []
    current_combination: Optional[List[str]] = None  # Visible pour le créateur
    quantum_state: Optional[Dict[str, Any]] = None
    leaderboard: List[Dict[str, Any]] = []
    chat_messages: List[Dict[str, Any]] = []

    model_config = {"from_attributes": True}

    @property
    def host(self) -> Optional["GamePlayerInfo"]:
        """Retourne le joueur host"""
        return next((p for p in self.players if p.is_host), None)

    @property
    def active_players(self) -> List["GamePlayerInfo"]:
        """Retourne les joueurs actifs"""
        return [p for p in self.players if p.status == PlayerStatus.ACTIVE]

    @property
    def winner(self) -> Optional["GamePlayerInfo"]:
        """Retourne le gagnant s'il y en a un"""
        return next((p for p in self.players if p.has_won), None)


class GameSummary(BaseModel):
    """Résumé d'une partie terminée"""
    game_id: UUID
    room_id: str
    game_type: GameType
    game_mode: GameMode
    difficulty: Difficulty
    duration: timedelta
    total_attempts: int
    players_count: int
    winner: Optional[str]
    final_scores: Dict[str, int]
    quantum_advantage_used: bool
    completion_rate: float
    average_score: float
    best_time: Optional[float]

    model_config = {"from_attributes": True}


class GamePlayerInfo(BaseModel):
    """Informations d'un joueur dans une partie"""
    id: UUID
    user_id: Optional[UUID]
    player_name: str
    status: PlayerStatus
    is_host: bool
    join_order: int
    score: int
    attempts_count: int
    has_won: bool
    final_rank: Optional[int]
    completion_rate: float
    quantum_measurements_used: int
    grover_hints_used: int
    entanglement_exploits: int
    quantum_advantage_score: float
    joined_at: datetime
    finished_at: Optional[datetime]
    time_taken: Optional[timedelta]

    model_config = {"from_attributes": True}


class GamePlayerUpdate(BaseModel):
    """Mise à jour d'un joueur"""
    status: Optional[PlayerStatus] = None
    player_name: Optional[str] = Field(None, min_length=1, max_length=100)


# === SCHÉMAS ATTEMPT ===
class AttemptBase(BaseModel):
    """Schéma de base pour une tentative"""
    guess: List[str] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Tentative (4 couleurs)"
    )
    use_quantum_measurement: bool = Field(
        False,
        description="Utiliser une mesure quantique"
    )
    measured_position: Optional[int] = Field(
        None,
        ge=0,
        le=3,
        description="Position à mesurer (0-3)"
    )

    @field_validator('guess')
    @classmethod
    def validate_colors(cls, v):
        """Valide les couleurs de la tentative"""
        valid_colors = {
            'red', 'blue', 'green', 'yellow',
            'orange', 'purple', 'black', 'white'
        }
        for color in v:
            if color not in valid_colors:
                raise ValueError(f"Couleur invalide: {color}")
        return v


class AttemptCreate(AttemptBase):
    """Création d'une tentative"""
    pass


class AttemptResult(BaseModel):
    """Résultat d'une tentative"""
    id: UUID
    attempt_number: int
    guess: List[str]
    result: Dict[str, Any]  # {blacks: int, whites: int, ...}
    is_correct: bool
    score: int
    time_taken: timedelta
    measurement_used: bool
    quantum_result: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class AttemptHistory(BaseModel):
    """Historique des tentatives"""
    attempts: List[AttemptResult]
    total_attempts: int
    best_score: int
    average_time: float
    quantum_measurements_count: int
    success_rate: float


# === SCHÉMAS DE HINTS ===
class HintRequest(BaseModel):
    """Demande d'indice"""
    hint_type: str = Field(
        ...,
        pattern=r'^(color_presence|position_hint|quantum_measurement|grover_search)$',
        description="Type d'indice demandé"
    )
    position: Optional[int] = Field(
        None,
        ge=0,
        le=3,
        description="Position spécifique (si applicable)"
    )
    quantum_parameters: Optional[Dict[str, Any]] = Field(
        None,
        description="Paramètres quantiques spéciaux"
    )


class HintResult(BaseModel):
    """Résultat d'un indice"""
    hint_type: str  # 'color_presence', 'position_hint', 'quantum_measurement'
    position: Optional[int] = None
    color: Optional[str] = None
    confidence: float
    cost: int  # Points déduits
    quantum_advantage: bool = False
    additional_info: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


# === SCHÉMAS D'ADMINISTRATION ===
class GameAdmin(BaseModel):
    """Vue admin d'une partie"""
    id: UUID
    room_id: str
    created_by: Optional[UUID]
    game_type: GameType
    status: GameStatus
    players_count: int
    total_attempts: int
    created_at: datetime
    finished_at: Optional[datetime]
    has_issues: bool
    moderator_notes: Optional[str]

    model_config = {"from_attributes": True}


class GameModeration(BaseModel):
    """Actions de modération"""
    action: str = Field(
        ...,
        pattern=r'^(pause|resume|terminate|kick_player|ban_player)$'
    )
    target_player_id: Optional[UUID] = None
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Raison de l'action"
    )
    duration: Optional[int] = Field(
        None,
        gt=0,
        description="Durée en minutes (pour les bannissements)"
    )


# === SCHÉMAS DE RAPPORT ===
class GameReport(BaseModel):
    """Rapport d'une partie"""
    game_id: UUID
    reporter_id: UUID
    report_type: str = Field(
        ...,
        pattern=r'^(cheating|griefing|inappropriate_behavior|bug|other)$'
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Description du problème"
    )
    evidence: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


# === SCHÉMAS DE TOURNOI ===
class TournamentInfo(BaseModel):
    """Informations de tournoi"""
    id: UUID
    name: str
    description: str
    start_date: datetime
    end_date: datetime
    max_participants: int
    current_participants: int
    entry_fee: int
    prize_pool: int
    rules: Dict[str, Any]
    status: str

    model_config = {"from_attributes": True}


class TournamentRegistration(BaseModel):
    """Inscription à un tournoi"""
    tournament_id: UUID
    team_name: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


# === SCHÉMAS DE CLASSEMENT ===
class Leaderboard(BaseModel):
    """Classement général"""
    period: str = Field(
        ...,
        pattern=r'^(daily|weekly|monthly|all_time)$',
        description="Période du classement"
    )
    game_type: Optional[GameType] = None
    entries: List["LeaderboardEntry"]
    last_updated: datetime


class LeaderboardEntry(BaseModel):
    """Entrée du classement"""
    rank: int
    user_id: UUID
    username: str
    score: int
    games_played: int
    win_rate: float
    average_time: float
    quantum_score: int
    trend: str  # "up", "down", "stable", "new"

    model_config = {"from_attributes": True}


# === SCHÉMAS DE STATISTIQUES ===
class GameStatistics(BaseModel):
    """Statistiques générales des parties"""
    total_games: int
    active_games: int
    games_today: int
    games_this_week: int
    average_game_duration: float
    most_popular_mode: GameType
    quantum_usage_rate: float
    player_satisfaction_score: float
    completion_rate: float


class PlayerGameStats(BaseModel):
    """Statistiques d'un joueur pour les jeux"""
    user_id: UUID
    total_games: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    average_score: int
    best_score: int
    total_time_played: timedelta
    average_game_time: timedelta
    best_time: Optional[timedelta]
    favorite_difficulty: Difficulty
    quantum_mastery_level: str
    achievements_count: int
    current_streak: int
    best_streak: int

    model_config = {"from_attributes": True}


# === SCHÉMAS DE RECHERCHE ET FILTRES ===
class GameSearchFilters(BaseModel):
    """Filtres de recherche de parties"""
    game_type: Optional[GameType] = None
    game_mode: Optional[GameMode] = None
    difficulty: Optional[Difficulty] = None
    status: Optional[GameStatus] = None
    has_password: Optional[bool] = None
    min_players: Optional[int] = Field(None, ge=1)
    max_players: Optional[int] = Field(None, le=8)
    created_since: Optional[datetime] = None
    room_code: Optional[str] = None


class GameSearchResult(BaseModel):
    """Résultat de recherche de parties"""
    games: List[GameInfo]
    total_count: int
    page: int
    page_size: int
    has_next: bool
    filters_applied: GameSearchFilters


# === SCHÉMAS DE CONFIGURATION ===
class GameConfiguration(BaseModel):
    """Configuration avancée d'une partie"""
    allow_hints: bool = True
    hint_cost_multiplier: float = Field(1.0, ge=0.1, le=5.0)
    time_pressure_mode: bool = False
    quantum_features_enabled: bool = True
    spectators_allowed: bool = False
    chat_enabled: bool = True
    auto_start_when_full: bool = True
    eliminate_on_timeout: bool = False
    scoring_system: str = Field(
        "standard",
        pattern=r'^(standard|time_based|quantum_enhanced|competitive)$'
    )
    custom_rules: Optional[Dict[str, Any]] = None


# === SCHÉMAS DE NOTIFICATIONS ===
class GameNotification(BaseModel):
    """Notification de jeu"""
    type: str = Field(
        ...,
        pattern=r'^(game_started|player_joined|player_left|game_finished|hint_available|your_turn)$'
    )
    game_id: UUID
    message: str
    data: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# === FORWARD REFERENCES ===
GameFull.model_rebuild()
Leaderboard.model_rebuild()