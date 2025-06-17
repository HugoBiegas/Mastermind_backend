"""
Modèles de base de données pour la gestion des jeux
MODIFIÉ: Ajout du support pour le mode quantique
"""
import secrets
import string
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from app.models.user import User

from sqlalchemy import (
    Boolean, DateTime, Integer, String, Index,
    event
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


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
    MULTI_SYNC = "multi_sync"
    BATTLE_ROYALE = "battle_royale"
    COOPERATIVE = "cooperative"


class GameStatus(str, Enum):
    """États d'une partie"""
    WAITING = "waiting"
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    ABANDONED = "abandoned"


class Difficulty(str, Enum):
    """Niveaux de difficulté"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class ParticipationStatus(str, Enum):
    """États de participation d'un joueur"""
    ACTIVE = "active"
    WAITING = "waiting"
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

    # === SOLUTION ET CONFIGURATION PRIVÉE ===

    solution: Mapped[List[int]] = mapped_column(
        JSONB,
        nullable=False
    )

    # NOUVEAU: Marqueur pour indiquer si la solution a été générée quantiquement
    quantum_solution: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True si la solution a été générée avec des algorithmes quantiques"
    )

    is_private: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )

    # === MÉTADONNÉES ET CONFIGURATION ===

    settings: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict
    )

    # NOUVEAU: Paramètres quantiques spécifiques
    quantum_settings: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Paramètres spécifiques au mode quantique (shots, qubits, etc.)"
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

    # === RÉFÉRENCE CRÉATEUR ===

    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True
    )

    # === TIMESTAMPS ===

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # === RELATIONS ===

    participations: Mapped[List["GameParticipation"]] = relationship(
        "GameParticipation",
        back_populates="game",
        cascade="all, delete-orphan",
        lazy="select"
    )

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
    def duration(self) -> Optional[int]:
        """Durée de la partie en secondes"""
        if self.started_at and self.finished_at:
            return int((self.finished_at - self.started_at).total_seconds())
        elif self.started_at:
            return int((datetime.now(timezone.utc) - self.started_at).total_seconds())
        return None

    # === MÉTHODES UTILITAIRES ===

    def get_quantum_config(self) -> Dict[str, Any]:
        """Retourne la configuration quantique de la partie"""
        default_config = {
            "shots": 1024,
            "max_qubits": 5,
            "use_quantum_solution": self.game_type == GameType.QUANTUM,
            "use_quantum_hints": self.game_type == GameType.QUANTUM,
            "quantum_hint_cost": 50
        }

        if self.quantum_settings:
            default_config.update(self.quantum_settings)

        return default_config

    def set_quantum_solution_generated(self, quantum_data: Optional[Dict[str, Any]] = None):
        """Marque que la solution a été générée quantiquement"""
        self.quantum_solution = True
        if quantum_data:
            if not self.quantum_settings:
                self.quantum_settings = {}
            self.quantum_settings["solution_generation"] = quantum_data

    def add_quantum_metadata(self, metadata: Dict[str, Any]) -> None:
        """Ajoute des métadonnées quantiques"""
        if not self.quantum_settings:
            self.quantum_settings = {}

        if "metadata" not in self.quantum_settings:
            self.quantum_settings["metadata"] = {}

        self.quantum_settings["metadata"].update(metadata)

    def __repr__(self) -> str:
        quantum_marker = " [Q]" if self.is_quantum_enabled else ""
        return f"<Game(id={self.id}, type={self.game_type}, status={self.status}{quantum_marker})>"


class GameParticipation(Base):
    """Participation d'un utilisateur à une partie"""
    __tablename__ = "game_participations"

    # === CLÉS ===

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    game_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True
    )

    player_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
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

    def calculate_quantum_bonus(self) -> int:
        """Calcule le bonus de score quantique"""
        base_bonus = self.quantum_hints_used * 10

        # Bonus si la partie était entièrement quantique
        if self.game and self.game.is_quantum_enabled:
            base_bonus *= 2

        return base_bonus

    def add_quantum_hint_usage(self, hint_type: str, cost: int = 0):
        """Enregistre l'utilisation d'un hint quantique"""
        self.quantum_hints_used += 1
        self.quantum_score += max(0, cost // 2)  # Bonus partiel du coût

    def __repr__(self) -> str:
        return f"<GameParticipation(id={self.id}, game_id={self.game_id}, player_id={self.player_id})>"


class GameAttempt(Base):
    """Tentative de solution dans une partie"""
    __tablename__ = "game_attempts"

    # === CLÉS ===

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    game_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True
    )

    player_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
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

    # === RÉSULTATS ===

    exact_matches: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Couleurs bien placées"
    )

    position_matches: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Couleurs mal placées"
    )

    # NOUVEAU: Indique si les indices ont été calculés quantiquement
    quantum_calculated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True si les indices ont été calculés avec des algorithmes quantiques"
    )

    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
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
        return f"<GameAttempt(id={self.id}, game_id={self.game_id}, attempt_number={self.attempt_number}{quantum_marker})>"


# === ÉVÉNEMENTS SQLAlchemy ===

@event.listens_for(Game, 'before_insert')
def game_before_insert(mapper, connection, target):
    """Traitement avant insertion d'une partie"""
    if not target.room_code:
        target.room_code = generate_room_code()

    if target.settings is None:
        target.settings = {
            "allow_duplicates": True,
            "allow_blanks": False,
            "hint_cost": 10,
            "auto_reveal_pegs": True,
            "show_statistics": True
        }

    # NOUVEAU: Configuration quantique par défaut
    if target.game_type == GameType.QUANTUM and not target.quantum_settings:
        target.quantum_settings = {
            "shots": 1024,
            "max_qubits": 5,
            "use_quantum_solution": True,
            "use_quantum_hints": True,
            "quantum_hint_cost": 50
        }

    # La solution sera générée par le service (quantique ou classique)
    if not target.solution:
        target.solution = generate_solution(
            target.combination_length,
            target.available_colors
        )


@event.listens_for(Game, 'before_update')
def game_before_update(mapper, connection, target):
    """Traitement avant mise à jour d'une partie"""
    target.updated_at = datetime.now(timezone.utc)


@event.listens_for(GameParticipation, 'after_insert')
def participation_after_insert(mapper, connection, target):
    """Traitement après insertion d'une participation"""
    # Logique pour vérifier si la partie peut démarrer automatiquement
    pass


@event.listens_for(GameAttempt, 'before_insert')
def attempt_before_insert(mapper, connection, target):
    """Traitement avant insertion d'une tentative"""
    if isinstance(target.combination, list):
        # Ne rien faire car JSONB gère automatiquement les listes
        pass


# === EXPORTS ===

__all__ = [
    # Énumérations
    "GameType", "GameMode", "GameStatus", "Difficulty", "ParticipationStatus",

    # Modèles
    "Game", "GameParticipation", "GameAttempt",

    # Fonctions utilitaires
    "generate_room_code", "generate_solution", "calculate_game_score"
]