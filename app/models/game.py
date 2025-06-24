"""
Modèles de jeu pour Quantum Mastermind
SQLAlchemy 2.0.41 avec typing moderne et support quantique
CORRECTION: Synchronisé exactement avec init.sql (SANS quantum_score)
"""
import random
import string
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, DateTime, Integer, String, Text, ForeignKey,
    CheckConstraint, Index, event
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Import conditionnel pour éviter les imports circulaires
if TYPE_CHECKING:
    from app.models.user import User

# === ÉNUMÉRATIONS CORRIGÉES ===

class GameType(str, Enum):
    """Types de jeu disponibles"""
    CLASSIC = "classic"
    QUANTUM = "quantum"
    SPEED = "speed"
    PRECISION = "precision"


class GameMode(str, Enum):
    """Modes de jeu disponibles"""
    SINGLE = "single"
    MULTIPLAYER = "multiplayer"
    BATTLE_ROYALE = "battle_royale"
    TOURNAMENT = "tournament"


class GameStatus(str, Enum):
    """Statuts d'une partie"""
    WAITING = "waiting"
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    ABORTED = "aborted"


class Difficulty(str, Enum):
    """Niveaux de difficulté"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"
    QUANTUM = "quantum"


class ParticipationStatus(str, Enum):
    """Statuts de participation"""
    WAITING = "waiting"
    READY = "ready"
    ACTIVE = "active"
    FINISHED = "finished"
    ELIMINATED = "eliminated"
    DISCONNECTED = "disconnected"


# === FONCTIONS UTILITAIRES ===

def generate_room_code() -> str:
    """Génère un code de room unique"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def generate_solution(length: int, colors: int) -> List[int]:
    """Génère une solution aléatoire"""
    return [random.randint(1, colors) for _ in range(length)]


def calculate_game_score(attempts: int, max_attempts: int, time_taken: int = 0) -> int:
    """Calcule le score d'une partie"""
    base_score = max(0, (max_attempts - attempts + 1) * 100)
    time_bonus = max(0, 1000 - time_taken // 1000)
    return base_score + time_bonus


# === MODÈLES ===

class Game(Base):
    """
    Modèle d'une partie de Quantum Mastermind
    CORRECTION: Synchronisé exactement avec init.sql
    """
    __tablename__ = "games"

    # === CLÉS ===
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    room_code: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
        index=True
    )

    # === CONFIGURATION DU JEU (selon init.sql) ===
    game_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="classic"
    )

    game_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="single"
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="waiting",
        index=True
    )

    difficulty: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium"
    )

    # === PARAMÈTRES DE JEU (selon init.sql) ===
    combination_length: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=4
    )

    available_colors: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=6
    )

    max_attempts: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=12
    )

    time_limit: Mapped[Optional[int]] = mapped_column(
        Integer,  # en secondes
        nullable=True
    )

    max_players: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1
    )

    # === SOLUTION SECRÈTE (selon init.sql) ===
    solution: Mapped[List[int]] = mapped_column(
        JSONB,
        nullable=False
    )

    # === CONFIGURATION AVANCÉE (selon init.sql) ===
    is_private: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    allow_spectators: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    enable_chat: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    quantum_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    # === RÉFÉRENCE CRÉATEUR (selon init.sql) ===
    creator_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # === PARAMÈTRES AVANCÉS (selon init.sql) ===
    settings: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None
    )

    quantum_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=None
    )

    # === TIMESTAMPS (selon init.sql) ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # === RELATIONS SQLALCHEMY ===
    creator: Mapped["User"] = relationship(
        "User",
        back_populates="created_games",
        foreign_keys=[creator_id],
        lazy="noload"
    )

    participations: Mapped[List["GameParticipation"]] = relationship(
        "GameParticipation",
        back_populates="game",
        cascade="all, delete-orphan",
        lazy="noload"
    )

    attempts: Mapped[List["GameAttempt"]] = relationship(
        "GameAttempt",
        back_populates="game",
        cascade="all, delete-orphan",
        lazy="noload"
    )

    # === PROPRIÉTÉS CALCULÉES ===
    @hybrid_property
    def is_quantum_enabled(self) -> bool:
        """Vérifie si le mode quantique est activé"""
        return (
            self.game_type == GameType.QUANTUM.value or
            self.quantum_enabled or
            (self.settings and self.settings.get("quantum_enabled", False))
        )

    def get_current_player_count(self) -> int:
        """Retourne le nombre de joueurs actuels"""
        return len([p for p in self.participations if p.status != ParticipationStatus.DISCONNECTED.value])

    def is_full(self) -> bool:
        """Vérifie si la partie est pleine"""
        return self.get_current_player_count() >= self.max_players

    def can_start(self) -> bool:
        """Vérifie si la partie peut démarrer"""
        return (
            self.status == GameStatus.WAITING.value and
            self.get_current_player_count() >= 1
        )

    def get_quantum_config(self) -> Dict[str, Any]:
        """Retourne la configuration quantique"""
        base_config = {
            "shots": 1024,
            "max_qubits": 5,
            "use_quantum_solution": False,
            "use_quantum_hints": False
        }

        if self.quantum_data and "settings" in self.quantum_data:
            base_config.update(self.quantum_data["settings"])

        return base_config

    def set_quantum_solution_generated(self, generation_data: Dict[str, Any]):
        """Marque qu'une solution quantique a été générée"""
        if self.quantum_data is None:
            self.quantum_data = {}
        self.quantum_data["solution_generation"] = generation_data

    def __repr__(self) -> str:
        quantum_marker = " [Q]" if self.is_quantum_enabled else ""
        return f"<Game(id={self.id}, code={self.room_code}, status={self.status}){quantum_marker}>"


class GameParticipation(Base):
    """
    Modèle de participation d'un joueur à une partie
    CORRECTION: Synchronisé exactement avec init.sql (SANS quantum_score)
    """
    __tablename__ = "game_participations"

    # === CLÉS (selon init.sql) ===
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    game_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    player_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # === STATUT ET RÔLE (selon init.sql) ===
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="waiting"
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="player"
    )

    # === ORDRE ET POSITION (selon init.sql) ===
    join_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    finish_position: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )

    # === SCORING ET STATISTIQUES (selon init.sql) ===
    score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    attempts_made: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    quantum_hints_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    # REMARQUE: quantum_score N'EXISTE PAS dans init.sql, donc supprimé

    time_taken: Mapped[Optional[int]] = mapped_column(
        Integer,  # en secondes selon init.sql
        nullable=True
    )

    # === FLAGS (selon init.sql) ===
    is_ready: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    is_winner: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    is_eliminated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    # === TIMESTAMPS (selon init.sql) ===
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    left_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # === RELATIONS SQLALCHEMY ===
    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="participations",
        lazy="noload"
    )

    player: Mapped["User"] = relationship(
        "User",
        back_populates="game_participations",
        lazy="noload"
    )

    # === CONTRAINTES ===
    __table_args__ = (
        Index('idx_participation_unique', 'game_id', 'player_id', unique=True),
    )

    # === MÉTHODES UTILITAIRES ===
    def calculate_total_score(self) -> int:
        """Calcule le score total (pour l'instant, juste score normal)"""
        return self.score  # quantum_score supprimé

    def get_quantum_efficiency(self) -> float:
        """Calcule l'efficacité quantique du joueur"""
        if self.attempts_made == 0:
            return 0.0
        return self.quantum_hints_used / self.attempts_made

    def __repr__(self) -> str:
        return f"<GameParticipation(game_id={self.game_id}, player_id={self.player_id}, status={self.status})>"


class GameAttempt(Base):
    """
    Modèle d'une tentative dans une partie
    CORRECTION: Synchronisé exactement avec init.sql
    """
    __tablename__ = "game_attempts"

    # === CLÉS (selon init.sql) ===
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    game_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    player_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    mastermind_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=1,
        comment="Numéro du mastermind pour le multijoueur (1 si solo)"
    )

    mastermind_total: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=1,
        comment="Nombre total de masterminds dans la partie (1 si solo)"
    )

    # === DONNÉES DE TENTATIVE (selon init.sql) ===
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    combination: Mapped[List[int]] = mapped_column(
        JSONB,
        nullable=False
    )

    # === RÉSULTATS (selon init.sql) ===
    correct_positions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    correct_colors: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    # === SCORING (selon init.sql) ===
    attempt_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    time_taken: Mapped[Optional[int]] = mapped_column(
        Integer,  # en millisecondes selon init.sql
        nullable=True
    )

    # === DONNÉES QUANTIQUES (selon init.sql) ===
    quantum_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Données quantiques détaillées (probabilités, etc.)"
    )

    used_quantum_hint: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    hint_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )

    # === TIMESTAMPS (selon init.sql) ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # === RELATIONS SQLALCHEMY ===
    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="attempts",
        lazy="noload"
    )

    player: Mapped["User"] = relationship(
        "User",
        back_populates="game_attempts",
        lazy="noload"
    )

    # === CONTRAINTES ===
    __table_args__ = (
        Index('idx_attempt_unique', 'game_id', 'player_id', 'attempt_number', unique=True),
    )

    # === PROPRIÉTÉS CALCULÉES ===
    @property
    def exact_matches(self) -> int:
        """Alias pour correct_positions (compatibilité)"""
        return self.correct_positions

    @exact_matches.setter
    def exact_matches(self, value: int):
        """Setter pour exact_matches"""
        self.correct_positions = value

    @property
    def position_matches(self) -> int:
        """Alias pour correct_colors (compatibilité)"""
        return self.correct_colors

    @position_matches.setter
    def position_matches(self, value: int):
        """Setter pour position_matches"""
        self.correct_colors = value

    @property
    def quantum_calculated(self) -> bool:
        """Indique si calculé quantiquement"""
        return self.quantum_data is not None and "calculation" in self.quantum_data

    # === MÉTHODES UTILITAIRES ===
    def add_quantum_data(self, data: Dict[str, Any]) -> None:
        """Ajoute des données quantiques"""
        if self.quantum_data is None:
            self.quantum_data = {}
        self.quantum_data.update(data)

    def set_quantum_calculated(self, calculation_data: Optional[Dict[str, Any]] = None):
        """Marque que les indices ont été calculés quantiquement"""
        if self.quantum_data is None:
            self.quantum_data = {}
        self.quantum_data["quantum_calculated"] = True
        if calculation_data:
            self.quantum_data["calculation"] = calculation_data

    def get_quantum_efficiency(self) -> float:
        """Calcule l'efficacité quantique de la tentative"""
        if not self.quantum_calculated:
            return 0.0

        if self.quantum_data:
            return min(1.0, len(self.quantum_data) * 0.2)

        return 0.5

    def __repr__(self) -> str:
        quantum_marker = " [Q]" if self.quantum_calculated else ""
        return f"<GameAttempt(game_id={self.game_id}, player_id={self.player_id}, attempt={self.attempt_number}){quantum_marker}>"


# === ÉVÉNEMENTS SQLALCHEMY ===

@event.listens_for(Game, 'before_insert')
def generate_room_code_on_insert(mapper, connection, target):
    """Génère automatiquement un code de room unique"""
    if not target.room_code:
        target.room_code = generate_room_code()


@event.listens_for(Game, 'before_insert')
def set_quantum_defaults(mapper, connection, target):
    """Configure les paramètres quantiques par défaut"""
    if target.game_type == GameType.QUANTUM.value and not target.quantum_enabled:
        target.quantum_enabled = True

    if target.quantum_enabled and target.settings:
        target.settings["quantum_enabled"] = True


# === EXPORTS ===

__all__ = [

    "GameType", "GameMode", "GameStatus", "Difficulty", "ParticipationStatus",

    "Game", "GameParticipation", "GameAttempt",

    "generate_room_code", "generate_solution", "calculate_game_score"

]