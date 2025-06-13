"""
Modèles pour les parties de Quantum Mastermind
Game, GamePlayer, GameAttempt avec logique quantique
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID
from enum import Enum

from sqlalchemy import (
    Boolean, Float, Integer, String, DateTime, Interval,
    CheckConstraint, Index, ForeignKey, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TimestampedModel


# === ÉNUMÉRATIONS ===
class GameType(str, Enum):
    CLASSIC = "classic"
    QUANTUM = "quantum"
    HYBRID = "hybrid"
    TOURNAMENT = "tournament"


class GameMode(str, Enum):
    SOLO = "solo"
    MULTIPLAYER = "multiplayer"
    RANKED = "ranked"
    TRAINING = "training"


class GameStatus(str, Enum):
    WAITING = "waiting"
    ACTIVE = "active"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"


class PlayerStatus(str, Enum):
    JOINED = "joined"
    READY = "ready"
    PLAYING = "playing"
    FINISHED = "finished"
    DISCONNECTED = "disconnected"


class Difficulty(str, Enum):
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"
    EXPERT = "expert"


# === MODÈLE GAME ===
class Game(TimestampedModel):
    """
    Modèle principal pour une partie de Quantum Mastermind
    """
    __tablename__ = "games"

    # === IDENTIFICATION ===
    room_id: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Code de room pour rejoindre la partie"
    )

    created_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Créateur de la partie"
    )

    # === CONFIGURATION DU JEU ===
    game_type: Mapped[GameType] = mapped_column(
        SQLEnum(GameType),
        default=GameType.CLASSIC,
        nullable=False,
        comment="Type de jeu"
    )

    game_mode: Mapped[GameMode] = mapped_column(
        SQLEnum(GameMode),
        default=GameMode.SOLO,
        nullable=False,
        comment="Mode de jeu"
    )

    difficulty: Mapped[Difficulty] = mapped_column(
        SQLEnum(Difficulty),
        default=Difficulty.NORMAL,
        nullable=False,
        comment="Niveau de difficulté"
    )

    # === ÉTAT ET RÈGLES ===
    status: Mapped[GameStatus] = mapped_column(
        SQLEnum(GameStatus),
        default=GameStatus.WAITING,
        nullable=False,
        index=True,
        comment="État actuel de la partie"
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=10,
        nullable=False,
        comment="Nombre maximum de tentatives"
    )

    time_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Limite de temps en secondes"
    )

    max_players: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Nombre maximum de joueurs"
    )

    # === SOLUTIONS ===
    quantum_solution: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Solution quantique générée"
    )

    classical_solution: Mapped[Optional[List[str]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Solution classique (couleurs)"
    )

    solution_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Hash SHA-256 de la solution pour vérification"
    )

    quantum_seed: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        comment="Seed pour la génération quantique reproductible"
    )

    # === RÉSULTATS ===
    winner_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Gagnant de la partie"
    )

    total_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Nombre total de tentatives dans la partie"
    )

    game_duration: Mapped[Optional[timedelta]] = mapped_column(
        Interval,
        nullable=True,
        comment="Durée totale de la partie"
    )

    # === MÉTADONNÉES ===
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Moment du début de partie"
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Moment de fin de partie"
    )

    settings: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        default=dict,
        nullable=True,
        comment="Paramètres spécifiques à la partie"
    )

    # === RELATIONS ===
    players: Mapped[List["GamePlayer"]] = relationship(
        "GamePlayer",
        back_populates="game",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    attempts: Mapped[List["GameAttempt"]] = relationship(
        "GameAttempt",
        back_populates="game",
        cascade="all, delete-orphan"
    )

    # === CONTRAINTES ===
    __table_args__ = (
        CheckConstraint('max_attempts > 0 AND max_attempts <= 20', name='check_max_attempts_range'),
        CheckConstraint('time_limit > 0 OR time_limit IS NULL', name='check_time_limit_positive'),
        CheckConstraint('max_players > 0 AND max_players <= 8', name='check_max_players_range'),
        CheckConstraint('total_attempts >= 0', name='check_total_attempts_positive'),
        Index('idx_games_room_id', 'room_id'),
        Index('idx_games_status_type', 'status', 'game_type'),
        Index('idx_games_created_by', 'created_by'),
        Index('idx_games_finished_at', 'finished_at'),
    )

    # === PROPRIÉTÉS CALCULÉES ===
    @property
    def is_active(self) -> bool:
        """Vérifie si la partie est active"""
        return self.status in [GameStatus.WAITING, GameStatus.ACTIVE, GameStatus.PAUSED]

    @property
    def is_full(self) -> bool:
        """Vérifie si la partie est pleine"""
        return len(self.players) >= self.max_players

    @property
    def current_player_count(self) -> int:
        """Nombre actuel de joueurs"""
        return len([p for p in self.players if p.status != PlayerStatus.DISCONNECTED])

    @property
    def is_quantum_enabled(self) -> bool:
        """Vérifie si les fonctionnalités quantiques sont activées"""
        return self.game_type in [GameType.QUANTUM, GameType.HYBRID]

    @property
    def progress_percentage(self) -> float:
        """Pourcentage de progression de la partie"""
        if self.status == GameStatus.FINISHED:
            return 100.0
        if self.max_attempts == 0:
            return 0.0
        return min(100.0, (self.total_attempts / self.max_attempts) * 100)

    # === MÉTHODES DE GESTION D'ÉTAT ===
    def start_game(self) -> None:
        """Démarre la partie"""
        if self.status == GameStatus.WAITING:
            self.status = GameStatus.ACTIVE
            self.started_at = datetime.utcnow()

    def finish_game(self, winner_id: Optional[UUID] = None) -> None:
        """Termine la partie"""
        self.status = GameStatus.FINISHED
        self.finished_at = datetime.utcnow()
        self.winner_id = winner_id

        if self.started_at:
            self.game_duration = self.finished_at - self.started_at

    def pause_game(self) -> None:
        """Met en pause la partie"""
        if self.status == GameStatus.ACTIVE:
            self.status = GameStatus.PAUSED

    def resume_game(self) -> None:
        """Reprend la partie"""
        if self.status == GameStatus.PAUSED:
            self.status = GameStatus.ACTIVE

    def cancel_game(self) -> None:
        """Annule la partie"""
        self.status = GameStatus.CANCELLED
        self.finished_at = datetime.utcnow()

    # === MÉTHODES DE SOLUTION ===
    def set_classical_solution(self, colors: List[str]) -> None:
        """Définit la solution classique"""
        import hashlib
        self.classical_solution = colors
        solution_str = ''.join(colors)
        self.solution_hash = hashlib.sha256(solution_str.encode()).hexdigest()

    def verify_solution(self, guess: List[str]) -> bool:
        """Vérifie si une tentative correspond à la solution"""
        return guess == self.classical_solution

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Récupère un paramètre de la partie"""
        if not self.settings:
            return default
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """Définit un paramètre de la partie"""
        if not self.settings:
            self.settings = {}
        self.settings[key] = value


# === MODÈLE GAME PLAYER ===
class GamePlayer(TimestampedModel):
    """
    Modèle pour un joueur dans une partie
    """
    __tablename__ = "game_players"

    # === RÉFÉRENCES ===
    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        comment="Référence vers la partie"
    )

    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Référence vers l'utilisateur (si connecté)"
    )

    # === INFORMATIONS JOUEUR ===
    player_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Nom d'affichage du joueur"
    )

    status: Mapped[PlayerStatus] = mapped_column(
        SQLEnum(PlayerStatus),
        default=PlayerStatus.JOINED,
        nullable=False,
        comment="État du joueur"
    )

    is_host: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Joueur hôte de la partie"
    )

    join_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Ordre d'arrivée dans la partie"
    )

    # === PERFORMANCE ===
    score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Score du joueur"
    )

    attempts_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Nombre de tentatives du joueur"
    )

    best_attempt: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Numéro de la meilleure tentative"
    )

    time_taken: Mapped[Optional[timedelta]] = mapped_column(
        Interval,
        nullable=True,
        comment="Temps pris par le joueur"
    )

    # === RÉSULTAT ===
    has_won: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="A gagné la partie"
    )

    final_rank: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Classement final"
    )

    completion_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Taux de completion (0.0 à 1.0)"
    )

    # === QUANTUM SPÉCIFIQUE ===
    quantum_measurements_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Nombre de mesures quantiques utilisées"
    )

    grover_hints_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Nombre d'indices Grover utilisés"
    )

    entanglement_exploits: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Nombre d'exploitations d'intrication"
    )

    quantum_advantage_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Score d'avantage quantique"
    )

    # === TIMESTAMPS SPÉCIFIQUES ===
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        comment="Moment de rejoindre la partie"
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Moment de fin pour ce joueur"
    )

    # === RELATIONS ===
    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="players"
    )

    attempts: Mapped[List["GameAttempt"]] = relationship(
        "GameAttempt",
        back_populates="player",
        cascade="all, delete-orphan"
    )

    # === CONTRAINTES ===
    __table_args__ = (
        UniqueConstraint('game_id', 'user_id', name='uq_game_user'),
        UniqueConstraint('game_id', 'join_order', name='uq_game_join_order'),
        CheckConstraint('score >= 0', name='check_score_positive'),
        CheckConstraint('attempts_count >= 0', name='check_attempts_positive'),
        CheckConstraint('completion_rate >= 0.0 AND completion_rate <= 1.0', name='check_completion_rate'),
        CheckConstraint('quantum_measurements_used >= 0', name='check_quantum_measurements_positive'),
        CheckConstraint('grover_hints_used >= 0', name='check_grover_hints_positive'),
        CheckConstraint('entanglement_exploits >= 0', name='check_entanglement_positive'),
        Index('idx_game_players_game_user', 'game_id', 'user_id'),
        Index('idx_game_players_status', 'status'),
    )

    # === MÉTHODES ===
    def finish(self, won: bool = False, rank: Optional[int] = None) -> None:
        """Termine la participation du joueur"""
        self.status = PlayerStatus.FINISHED
        self.finished_at = datetime.utcnow()
        self.has_won = won
        self.final_rank = rank

        if self.joined_at:
            self.time_taken = self.finished_at - self.joined_at

    def disconnect(self) -> None:
        """Marque le joueur comme déconnecté"""
        self.status = PlayerStatus.DISCONNECTED

    def reconnect(self) -> None:
        """Reconnecte le joueur"""
        if self.status == PlayerStatus.DISCONNECTED:
            self.status = PlayerStatus.PLAYING

    def add_quantum_score(self, measurement_bonus: int = 0, grover_bonus: int = 0, entanglement_bonus: int = 0) -> None:
        """Ajoute des points quantiques"""
        self.quantum_measurements_used += 1 if measurement_bonus > 0 else 0
        self.grover_hints_used += 1 if grover_bonus > 0 else 0
        self.entanglement_exploits += 1 if entanglement_bonus > 0 else 0
        self.quantum_advantage_score += measurement_bonus + grover_bonus + entanglement_bonus


# === MODÈLE GAME ATTEMPT ===
class GameAttempt(TimestampedModel):
    """
    Modèle pour une tentative dans une partie
    """
    __tablename__ = "game_attempts"

    # === RÉFÉRENCES ===
    game_id: Mapped[UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        comment="Référence vers la partie"
    )

    player_id: Mapped[UUID] = mapped_column(
        ForeignKey("game_players.id", ondelete="CASCADE"),
        nullable=False,
        comment="Référence vers le joueur"
    )

    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Référence vers l'utilisateur"
    )

    # === DÉTAILS DE LA TENTATIVE ===
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Numéro de la tentative"
    )

    guess: Mapped[List[str]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Tentative du joueur (couleurs)"
    )

    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Tentative valide"
    )

    # === RÉSULTATS ===
    result: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Résultat de la tentative (pions noirs/blancs)"
    )

    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Tentative correcte (solution trouvée)"
    )

    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Score de confiance (0.0 à 1.0)"
    )

    # === QUANTUM SPÉCIFIQUE ===
    quantum_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Résultat quantique de la mesure"
    )

    measurement_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Mesure quantique utilisée"
    )

    measured_position: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Position mesurée (0-3)"
    )

    quantum_state_before: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="État quantique avant mesure"
    )

    quantum_state_after: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="État quantique après mesure"
    )

    # === PERFORMANCE ===
    time_taken: Mapped[timedelta] = mapped_column(
        Interval,
        nullable=False,
        comment="Temps pris pour cette tentative"
    )

    think_time: Mapped[Optional[timedelta]] = mapped_column(
        Interval,
        nullable=True,
        comment="Temps de réflexion"
    )

    response_time: Mapped[Optional[timedelta]] = mapped_column(
        Interval,
        nullable=True,
        comment="Temps de réponse de l'interface"
    )

    # === MÉTADONNÉES ===
    client_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        default=dict,
        nullable=True,
        comment="Informations client (IP, User-Agent, etc.)"
    )

    # === RELATIONS ===
    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="attempts"
    )

    player: Mapped["GamePlayer"] = relationship(
        "GamePlayer",
        back_populates="attempts"
    )

    # === CONTRAINTES ===
    __table_args__ = (
        UniqueConstraint('game_id', 'player_id', 'attempt_number', name='uq_game_player_attempt'),
        CheckConstraint('attempt_number > 0', name='check_attempt_number_positive'),
        CheckConstraint('confidence_score >= 0.0 AND confidence_score <= 1.0 OR confidence_score IS NULL',
                        name='check_confidence_range'),
        CheckConstraint('measured_position >= 0 AND measured_position <= 3 OR measured_position IS NULL',
                        name='check_measured_position_range'),
        Index('idx_game_attempts_game_player', 'game_id', 'player_id'),
        Index('idx_game_attempts_correct', 'is_correct'),
        Index('idx_game_attempts_quantum', 'measurement_used'),
    )

    # === MÉTHODES ===
    def calculate_score(self) -> int:
        """Calcule le score pour cette tentative"""
        base_score = 0

        if self.is_correct:
            base_score = 100
        else:
            # Score basé sur les pions noirs/blancs
            blacks = self.result.get('blacks', 0)
            whites = self.result.get('whites', 0)
            base_score = blacks * 10 + whites * 5

        # Bonus quantique
        quantum_bonus = 0
        if self.measurement_used:
            quantum_bonus += 10

        if self.quantum_result:
            quantum_bonus += self.quantum_result.get('bonus_points', 0)

        return base_score + quantum_bonus

    def get_feedback(self) -> Dict[str, Any]:
        """Retourne le feedback pour l'interface"""
        return {
            'attempt_number': self.attempt_number,
            'guess': self.guess,
            'result': self.result,
            'is_correct': self.is_correct,
            'score': self.calculate_score(),
            'quantum_used': self.measurement_used,
            'time_taken': self.time_taken.total_seconds() if self.time_taken else 0
        }