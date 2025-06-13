"""
Schémas Pydantic pour les jeux
Validation et sérialisation des données de parties
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator

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
        regex=r'^[A-Z0-9]+$',
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

    @validator('max_players')
    def validate_max_players_for_mode(cls, v, values):
        """Valide le nombre de joueurs selon le mode"""
        game_mode = values.get('game_mode')
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
        description="Code de la room"
    )
    password: Optional[str] = Field(
        None,
        description="Mot de passe si requis"
    )
    player_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Nom d'affichage personnalisé"
    )


# === SCHÉMAS DE RÉPONSE ===
class GameInfo(BaseModel):
    """Informations d'une partie"""
    id: UUID
    room_id: str
    game_type: GameType
    game_mode: GameMode
    difficulty: Difficulty
    status: GameStatus
    max_attempts: int
    time_limit: Optional[int]
    max_players: int
    current_players: int
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    game_duration: Optional[timedelta]
    is_full: bool
    is_quantum_enabled: bool
    created_by: Optional[UUID]
    winner_id: Optional[UUID]

    class Config:
        from_attributes = True


class GamePublic(BaseModel):
    """Informations publiques d'une partie"""
    id: UUID
    room_id: str
    game_type: GameType
    game_mode: GameMode
    difficulty: Difficulty
    status: GameStatus
    max_players: int
    current_players: int
    created_at: datetime
    is_full: bool
    has_password: bool

    class Config:
        from_attributes = True


class GameFull(GameInfo):
    """Partie complète avec tous les détails"""
    quantum_solution: Optional[Dict[str, Any]]
    classical_solution: Optional[List[str]]
    total_attempts: int
    settings: Optional[Dict[str, Any]]
    players: List["GamePlayerInfo"]

    class Config:
        from_attributes = True


class GameList(BaseModel):
    """Liste de parties"""
    games: List[GamePublic]
    total: int
    page: int
    page_size: int
    active_games: int
    waiting_games: int

    class Config:
        from_attributes = True


# === SCHÉMAS PLAYER ===
class PlayerBase(BaseModel):
    """Schéma de base pour un joueur"""
    player_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nom d'affichage"
    )


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

    class Config:
        from_attributes = True


class GamePlayerUpdate(BaseModel):
    """Mise à jour d'un joueur"""
    status: Optional[PlayerStatus] = None
    player_name: Optional[str] = Field(None, min_length=1, max_length=100)


# === SCHÉMAS ATTEMPT ===
class AttemptBase(BaseModel):
    """Schéma de base pour une tentative"""
    guess: List[str] = Field(
        ...,
        min_items=4,
        max_items=4,
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

    @validator('guess')
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

    class Config:
        from_attributes = True


class AttemptHistory(BaseModel):
    """Historique des tentatives"""
    attempts: List[AttemptResult]
    total_attempts: int
    best_score: int
    average_time: float

    class Config:
        from_attributes = True


# === SCHÉMAS DE RECHERCHE ===
class GameSearch(BaseModel):
    """Critères de recherche de parties"""
    game_type: Optional[GameType] = None
    game_mode: Optional[GameMode] = None
    status: Optional[GameStatus] = None
    difficulty: Optional[Difficulty] = None
    has_slots: Optional[bool] = None  # Parties avec places libres
    created_by: Optional[UUID] = None
    sort_by: Optional[str] = Field(
        "created_at",
        regex=r'^(created_at|players_count|status)$'
    )
    sort_order: Optional[str] = Field(
        "desc",
        regex=r'^(asc|desc)$'
    )
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


# === SCHÉMAS DE STATISTIQUES ===
class GameStats(BaseModel):
    """Statistiques d'une partie"""
    game_id: UUID
    total_attempts: int
    average_attempts: float
    fastest_solve: Optional[timedelta]
    slowest_solve: Optional[timedelta]
    quantum_measurements_total: int
    players_finished: int
    completion_rate: float

    class Config:
        from_attributes = True


class PlayerGameStats(BaseModel):
    """Statistiques d'un joueur pour une partie"""
    player_id: UUID
    game_id: UUID
    attempts_made: int
    best_result: Dict[str, Any]
    time_progression: List[float]  # Temps par tentative
    quantum_usage: Dict[str, int]
    efficiency_score: float

    class Config:
        from_attributes = True


# === SCHÉMAS D'ÉVÉNEMENTS ===
class GameEvent(BaseModel):
    """Événement de jeu"""
    event_type: str
    game_id: UUID
    player_id: Optional[UUID] = None
    data: Dict[str, Any]
    timestamp: datetime

    class Config:
        from_attributes = True


class GameMessage(BaseModel):
    """Message dans une partie"""
    type: str
    from_player: Optional[str] = None
    content: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


# === SCHÉMAS DE SOLUTION ===
class SolutionReveal(BaseModel):
    """Révélation de la solution"""
    game_id: UUID
    classical_solution: List[str]
    quantum_solution: Optional[Dict[str, Any]]
    generation_method: str
    difficulty_level: float

    class Config:
        from_attributes = True


class SolutionHint(BaseModel):
    """Indice pour la solution"""
    hint_type: str  # 'color_presence', 'position_hint', 'quantum_measurement'
    position: Optional[int] = None
    color: Optional[str] = None
    confidence: float
    cost: int  # Points déduits

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


class GameModeration(BaseModel):
    """Actions de modération"""
    action: str = Field(
        ...,
        regex=r'^(pause|resume|terminate|kick_player|ban_player)$'
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
        regex=r'^(cheating|griefing|inappropriate_behavior|bug|other)$'
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Description du problème"
    )
    evidence: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


class TournamentRegistration(BaseModel):
    """Inscription à un tournoi"""
    tournament_id: UUID
    team_name: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# === FORWARD REFERENCES ===
GameFull.model_rebuild()