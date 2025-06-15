"""
Modèles de jeu pour Quantum Mastermind
SQLAlchemy 2.0.41 avec typing moderne et support quantique
CORRECTION: Alignement avec le schéma PostgreSQL init.sql
"""
import json
import secrets
import string
from datetime import datetime, timezone, timedelta
from typing import List, Optional, TYPE_CHECKING, Any, Dict
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy import (
    Boolean, DateTime, String, Text, Integer, Float,
    func, Index, CheckConstraint, ForeignKey, JSON, event
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Import conditionnel pour éviter les imports circulaires
if TYPE_CHECKING:
    from app.models.user import User


# === ÉNUMÉRATIONS SYNCHRONISÉES AVEC LA BDD ===

class GameType(str, Enum):
    """Types de jeu disponibles - SYNC avec init.sql"""
    CLASSIC = "classic"        # Mastermind classique
    QUANTUM = "quantum"        # Avec fonctionnalités quantiques
    SPEED = "speed"           # Mode rapidité
    PRECISION = "precision"    # Mode précision


class GameMode(str, Enum):
    """Modes de jeu - SYNC avec init.sql"""
    SINGLE = "single"             # Jeu solo
    MULTIPLAYER = "multiplayer"   # Multijoueur coopératif
    BATTLE_ROYALE = "battle_royale"  # Élimination progressive
    TOURNAMENT = "tournament"     # Mode tournoi


class GameStatus(str, Enum):
    """États d'une partie - SYNC avec init.sql"""
    WAITING = "waiting"       # En attente de joueurs
    STARTING = "starting"     # Démarrage en cours
    ACTIVE = "active"         # Partie en cours
    PAUSED = "paused"         # En pause
    FINISHED = "finished"     # Terminée
    CANCELLED = "cancelled"   # Annulée
    ABORTED = "aborted"       # Abandonnée


class Difficulty(str, Enum):
    """Niveaux de difficulté - SYNC avec init.sql"""
    EASY = "easy"            # Facile
    MEDIUM = "medium"        # Moyen
    HARD = "hard"           # Difficile
    EXPERT = "expert"       # Expert
    QUANTUM = "quantum"     # Quantique


class ParticipationStatus(str, Enum):
    """Statut de participation - SYNC avec init.sql"""
    WAITING = "waiting"      # En attente
    READY = "ready"         # Prêt
    ACTIVE = "active"       # Participe activement
    FINISHED = "finished"   # Terminé
    ELIMINATED = "eliminated"  # Éliminé
    DISCONNECTED = "disconnected"  # Déconnecté


# === FONCTIONS UTILITAIRES ===

def generate_room_code() -> str:
    """Génère un code de room unique"""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))


def generate_solution(length: int = 4, colors: int = 6) -> List[int]:
    """Génère une solution aléatoire"""
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
    CORRECTION: Synchronisé avec init.sql
    """
    __tablename__ = "games"

    # === CLÉS ET IDENTIFICATION ===

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True
    )

    # CORRECTION: room_code (pas room_id)
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

    # === SOLUTION ET CONFIGURATION ===

    solution: Mapped[List[int]] = mapped_column(
        JSONB,
        nullable=False
    )

    # === FLAGS DE CONFIGURATION ===

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

    # === RELATIONS ===

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
            "quantum_enabled": True,
            "hint_cost": 10,
            "auto_reveal_pegs": True,
            "show_statistics": True
        }
    )

    quantum_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True
    )

    # === MÉTADONNÉES TEMPORELLES ===

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )

    # === RELATIONS SQLALCHEMY ===

    creator: Mapped["User"] = relationship(
        "User",
        back_populates="created_games",
        lazy="select"
    )

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

    @property
    def current_players_count(self) -> int:
        """Nombre de joueurs actuels"""
        if not self.participations:
            return 0
        return len([p for p in self.participations if p.status != ParticipationStatus.DISCONNECTED])

    @property
    def is_full(self) -> bool:
        """Vérifie si la partie est complète"""
        return self.current_players_count >= self.max_players

    @property
    def is_active(self) -> bool:
        """Vérifie si la partie est active"""
        return self.status == GameStatus.ACTIVE

    @property
    def is_finished(self) -> bool:
        """Vérifie si la partie est terminée"""
        return self.status in [GameStatus.FINISHED, GameStatus.CANCELLED, GameStatus.ABORTED]

    @property
    def duration_seconds(self) -> Optional[int]:
        """Durée de la partie en secondes"""
        if not self.started_at:
            return None
        end_time = self.finished_at or datetime.now(timezone.utc)
        return int((end_time - self.started_at).total_seconds())

    # === MÉTHODES UTILITAIRES ===

    def can_join(self, user_id: UUID) -> bool:
        """Vérifie si un utilisateur peut rejoindre la partie"""
        if self.is_full or self.is_finished:
            return False

        # Vérifier si l'utilisateur n'est pas déjà dans la partie
        if self.participations:
            existing = [p for p in self.participations if p.player_id == user_id]
            if existing:
                return False

        return True

    def get_participation(self, user_id: UUID) -> Optional["GameParticipation"]:
        """Récupère la participation d'un utilisateur"""
        if not self.participations:
            return None
        for participation in self.participations:
            if participation.player_id == user_id:
                return participation
        return None

    def add_quantum_data(self, data: Dict[str, Any]) -> None:
        """Ajoute des données quantiques"""
        if self.quantum_data is None:
            self.quantum_data = {}
        self.quantum_data.update(data)

    def __repr__(self) -> str:
        return f"<Game(id={self.id}, room_code={self.room_code}, status={self.status})>"


class GameParticipation(Base):
    """
    Modèle de participation à une partie
    CORRECTION: Synchronisé avec init.sql
    """
    __tablename__ = "game_participations"

    # === CLÉS ===

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    # === RELATIONS - CORRECTION: player_id (pas user_id) ===

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

    # === STATUT ===

    status: Mapped[ParticipationStatus] = mapped_column(
        String(20),
        nullable=False,
        default=ParticipationStatus.WAITING,
        index=True
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="player"
    )

    # === ORDRE ET POSITION ===

    join_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    finish_position: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )

    # === SCORING ET STATISTIQUES ===

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

    time_taken: Mapped[Optional[int]] = mapped_column(
        Integer,  # en secondes
        nullable=True
    )

    # === FLAGS ===

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

    # === MÉTADONNÉES TEMPORELLES ===
    # CORRECTION: Synchronisé avec init.sql - pas de created_at/updated_at

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

    # === CONTRAINTE D'UNICITÉ ===
    __table_args__ = (
        Index('idx_participation_unique', 'game_id', 'player_id', unique=True),
    )

    def __repr__(self) -> str:
        return f"<GameParticipation(game_id={self.game_id}, player_id={self.player_id}, status={self.status})>"


class GameAttempt(Base):
    """
    Modèle d'une tentative de jeu
    CORRECTION: Synchronisé avec init.sql
    """
    __tablename__ = "game_attempts"

    # === CLÉS ===

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    # === RELATIONS - CORRECTION: player_id (pas user_id) ===

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

    # === DÉTAILS DE LA TENTATIVE ===

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )

    combination: Mapped[List[int]] = mapped_column(
        JSONB,
        nullable=False
    )

    # === RÉSULTATS ===

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
        default=False,
        index=True
    )

    # === SCORING ET TEMPS ===

    attempt_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    time_taken: Mapped[Optional[int]] = mapped_column(
        Integer,  # temps pour cette tentative en ms
        nullable=True
    )

    # === DONNÉES QUANTIQUES ===

    quantum_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True
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

    # === MÉTADONNÉES ===

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
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

    def __repr__(self) -> str:
        return f"<GameAttempt(id={self.id}, game_id={self.game_id}, attempt_number={self.attempt_number})>"


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
            "quantum_enabled": True,
            "hint_cost": 10,
            "auto_reveal_pegs": True,
            "show_statistics": True
        }

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