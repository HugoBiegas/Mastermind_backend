"""
Modèles de base de données pour la gestion des jeux
MODIFIÉ: Ajout du support pour le mode quantique
CORRECTION: Synchronisation des relations creator_id avec user.py
"""
import secrets
import string
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, DateTime, Integer, String, Index,
    event, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# Import conditionnel pour éviter les imports circulaires
if TYPE_CHECKING:
    from app.models.user import User


# === ÉNUMÉRATIONS ===

class GameType(str, Enum):
    """Types de jeu disponibles"""
    CLASSIC = "classic"
    QUANTUM = "quantum"  # NOUVEAU: Mode quantique
    SPEED = "speed"
    PRECISION = "precision"


class GameMode(str, Enum):
    """Modes de jeu multijoueur"""
    SINGLE = "single"
    MULTIPLAYER = "multiplayer"
    BATTLE_ROYALE = "battle_royale"
    TOURNAMENT = "tournament"


class GameStatus(str, Enum):
    """États d'une partie"""
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
    """États de participation d'un joueur"""
    WAITING = "waiting"
    READY = "ready"
    ACTIVE = "active"
    FINISHED = "finished"
    DISCONNECTED = "disconnected"
    ELIMINATED = "eliminated"


# === FONCTIONS UTILITAIRES ===

def generate_room_code() -> str:
    """Génère un code de room unique"""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))


def generate_solution(length: int = 4, colors: int = 6) -> List[int]:
    """Génère une solution aléatoire classique (fallback)"""
    return [secrets.randbelow(colors) + 1 for _ in range(length)]


def calculate_game_score(attempts: int, time_taken: int, max_attempts: int = 12) -> int:
    """Calcule le score d'une partie"""
    if attempts > max_attempts:
        return 0

    base_score = 1000
    attempt_penalty = (attempts - 1) * 50
    time_penalty = min(time_taken // 10, 200)

    return max(0, base_score - attempt_penalty - time_penalty)


# === MODÈLES SQLALCHEMY ===

class Game(Base):
    """
    Modèle principal d'une partie de jeu
    MODIFIÉ: Ajout du support quantique
    CORRECTION: Synchronisation des relations avec user.py
    """
    __tablename__ = "games"

    # === CLÉS ET IDENTIFICATION ===

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True
    )

    room_code: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        nullable=False,
        index=True
    )

    # === CONFIGURATION DU JEU ===

    game_type: Mapped[GameType] = mapped_column(
        String(20),
        nullable=False,
        default=GameType.CLASSIC,
        index=True
    )

    game_mode: Mapped[GameMode] = mapped_column(
        String(20),
        nullable=False,
        default=GameMode.SINGLE,
        index=True
    )

    status: Mapped[GameStatus] = mapped_column(
        String(20),
        nullable=False,
        default=GameStatus.WAITING,
        index=True
    )

    difficulty: Mapped[Difficulty] = mapped_column(
        String(20),
        nullable=False,
        default=Difficulty.MEDIUM,
        index=True
    )

    # === PARAMÈTRES DE JEU ===

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

    # === DONNÉES DE JEU ===

    solution: Mapped[List[int]] = mapped_column(
        JSONB,
        nullable=False
    )

    # NOUVEAU: Données quantiques
    quantum_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Données quantiques de la partie (circuits, états, résultats)"
    )

    # === CONFIGURATION AVANCÉE ===

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

    # NOUVEAU: Support quantique
    quantum_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Active les fonctionnalités quantiques pour cette partie"
    )

    # === RÉFÉRENCE CRÉATEUR - CORRECTION: Nom cohérent avec user.py ===

    creator_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # === PARAMÈTRES AVANCÉS ===

    settings: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {
            "allow_duplicates": True,
            "allow_blanks": False,
            "quantum_enabled": False,
            "hint_cost": 10,
            "auto_reveal_pegs": True,
            "show_statistics": True
        }
    )

    # === TIMESTAMPS ===

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

    # === RELATIONS SQLALCHEMY - CORRECTION: Ajout de la relation creator ===

    # Relation avec le créateur de la partie
    creator: Mapped["User"] = relationship(
        "User",
        back_populates="created_games",
        foreign_keys=[creator_id],
        lazy="select"
    )

    # Participations à la partie
    participations: Mapped[List["GameParticipation"]] = relationship(
        "GameParticipation",
        back_populates="game",
        cascade="all, delete-orphan",
        lazy="select"
    )

    # Tentatives dans la partie
    attempts: Mapped[List["GameAttempt"]] = relationship(
        "GameAttempt",
        back_populates="game",
        cascade="all, delete-orphan",
        lazy="select"
    )

    # === PROPRIÉTÉS CALCULÉES ===

    @hybrid_property
    def is_quantum_enabled(self) -> bool:
        """Vérifie si le mode quantique est activé pour cette partie"""
        return (
            self.game_type == GameType.QUANTUM or
            self.quantum_enabled or
            (self.settings and self.settings.get("quantum_enabled", False))
        )

    @hybrid_property
    def current_players_count(self) -> int:
        """Nombre de joueurs actuellement actifs"""
        return len([p for p in self.participations if p.status in [
            ParticipationStatus.ACTIVE, ParticipationStatus.WAITING
        ]])

    @hybrid_property
    def is_full(self) -> bool:
        """Vérifie si la partie est pleine"""
        return self.current_players_count >= self.max_players

    @hybrid_property
    def can_start(self) -> bool:
        """Vérifie si la partie peut démarrer"""
        return (
            self.status == GameStatus.WAITING and
            self.current_players_count >= 1 and
            (self.game_mode == GameMode.SINGLE or self.current_players_count >= 2)
        )

    @hybrid_property
    def is_active(self) -> bool:
        """Vérifie si la partie est active"""
        return self.status in [GameStatus.ACTIVE, GameStatus.STARTING]

    @hybrid_property
    def duration(self) -> Optional[int]:
        """Durée de la partie en secondes"""
        if self.started_at and self.finished_at:
            return int((self.finished_at - self.started_at).total_seconds())
        elif self.started_at:
            return int((datetime.now(timezone.utc) - self.started_at).total_seconds())
        return None

    # === MÉTHODES UTILITAIRES ===

    def add_quantum_data(self, data: Dict[str, Any]) -> None:
        """Ajoute des données quantiques à la partie"""
        if self.quantum_data is None:
            self.quantum_data = {}
        self.quantum_data.update(data)

    def enable_quantum_mode(self) -> None:
        """Active le mode quantique pour cette partie"""
        self.quantum_enabled = True
        if self.settings:
            self.settings["quantum_enabled"] = True
        else:
            self.settings = {"quantum_enabled": True}

    def get_quantum_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques quantiques de la partie"""
        if not self.is_quantum_enabled or not self.quantum_data:
            return {}

        return self.quantum_data.get("metrics", {})

    def __repr__(self) -> str:
        quantum_marker = " [Q]" if self.is_quantum_enabled else ""
        return f"<Game(id={self.id}, room_code={self.room_code}, status={self.status}){quantum_marker}>"


class GameParticipation(Base):
    """
    Modèle de participation d'un joueur à une partie
    MODIFIÉ: Ajout des métriques quantiques
    """
    __tablename__ = "game_participations"

    # === CLÉS ===

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

    # === DONNÉES DE PARTICIPATION ===

    status: Mapped[ParticipationStatus] = mapped_column(
        String(20),
        nullable=False,
        default=ParticipationStatus.WAITING
    )

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

    # NOUVEAU: Score quantique spécifique
    quantum_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Score basé sur l'utilisation des fonctionnalités quantiques"
    )

    hints_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    # NOUVEAU: Hints quantiques utilisés
    quantum_hints_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Nombre de hints quantiques utilisés"
    )

    time_taken: Mapped[Optional[int]] = mapped_column(
        Integer,  # en secondes
        nullable=True
    )

    rank: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )

    # === TIMESTAMPS ===

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # === RELATIONS SQLALCHEMY ===

    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="participations",
        lazy="select"
    )

    player: Mapped["User"] = relationship(
        "User",
        back_populates="game_participations",
        lazy="select"
    )

    # === CONTRAINTES ===
    __table_args__ = (
        Index('idx_participation_unique', 'game_id', 'player_id', unique=True),
    )

    # === MÉTHODES UTILITAIRES ===

    def calculate_total_score(self) -> int:
        """Calcule le score total incluant le bonus quantique"""
        base_score = self.score
        quantum_bonus = int(self.quantum_score * 1.5)  # Bonus de 50%
        return base_score + quantum_bonus

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
    MODIFIÉ: Ajout du support quantique pour les calculs d'indices
    """
    __tablename__ = "game_attempts"

    # === CLÉS ===

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

    # === DONNÉES DE TENTATIVE ===

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    combination: Mapped[List[int]] = mapped_column(
        JSONB,
        nullable=False
    )

    # Résultats classiques
    correct_position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    correct_color: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    # NOUVEAU: Résultats calculés quantiquement
    quantum_calculated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Indique si les indices ont été calculés avec des algorithmes quantiques"
    )

    # === MÉTADONNÉES ===

    time_taken: Mapped[Optional[int]] = mapped_column(
        Integer,  # en millisecondes
        nullable=True
    )

    hint_used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    # NOUVEAU: Données quantiques de la tentative
    quantum_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Données quantiques associées à cette tentative"
    )

    # === TIMESTAMP ===

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # === RELATIONS SQLALCHEMY ===

    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="attempts",
        lazy="select"
    )

    player: Mapped["User"] = relationship(
        "User",
        back_populates="game_attempts",
        lazy="select"
    )

    # === CONTRAINTES ===
    __table_args__ = (
        Index('idx_attempt_unique', 'game_id', 'player_id', 'attempt_number', unique=True),
    )

    # === MÉTHODES UTILITAIRES ===

    def add_quantum_data(self, data: Dict[str, Any]) -> None:
        """Ajoute des données quantiques"""
        if self.quantum_data is None:
            self.quantum_data = {}
        self.quantum_data.update(data)

    def set_quantum_calculated(self, calculation_data: Optional[Dict[str, Any]] = None):
        """Marque que les indices ont été calculés quantiquement"""
        self.quantum_calculated = True
        if calculation_data:
            self.add_quantum_data({"calculation": calculation_data})

    def get_quantum_efficiency(self) -> float:
        """Calcule l'efficacité quantique de la tentative"""
        if not self.quantum_calculated:
            return 0.0

        # Plus d'informations quantiques = meilleure efficacité
        if self.quantum_data:
            return min(1.0, len(self.quantum_data) * 0.2)

        return 0.5  # Efficacité de base

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
    if target.game_type == GameType.QUANTUM and not target.quantum_enabled:
        target.quantum_enabled = True

    if target.quantum_enabled and target.settings:
        target.settings["quantum_enabled"] = True


# === EXPORTS ===

__all__ = [
    # Énumérations
    "GameType", "GameMode", "GameStatus", "Difficulty", "ParticipationStatus",

    # Modèles
    "Game", "GameParticipation", "GameAttempt",

    # Fonctions utilitaires
    "generate_room_code", "generate_solution", "calculate_game_score"
]