"""
Modèles de jeu pour Quantum Mastermind
SQLAlchemy 2.0.41 avec typing moderne et support quantique
"""
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy import (
    Boolean, DateTime, String, Text, Integer, Float,
    func, Index, CheckConstraint, ForeignKey, JSON
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Import conditionnel pour éviter les imports circulaires
if TYPE_CHECKING:
    from app.models.user import User


# === ÉNUMÉRATIONS ===

class GameType(str, Enum):
    """Types de jeu disponibles"""
    CLASSIC = "classic"        # Mastermind classique
    QUANTUM = "quantum"        # Avec fonctionnalités quantiques
    HYBRID = "hybrid"          # Mix classique/quantique
    TOURNAMENT = "tournament"  # Mode tournoi


class GameMode(str, Enum):
    """Modes de jeu"""
    SOLO = "solo"             # Jeu solo
    MULTIPLAYER = "multiplayer"  # Multijoueur coopératif
    VERSUS = "versus"         # Joueur contre joueur
    BATTLE_ROYALE = "battle_royale"  # Élimination progressive
    RANKED = "ranked"         # Partie classée
    TRAINING = "training"     # Mode entraînement


class GameStatus(str, Enum):
    """États d'une partie"""
    WAITING = "waiting"       # En attente de joueurs
    STARTING = "starting"     # Démarrage en cours
    ACTIVE = "active"         # Partie en cours
    PAUSED = "paused"         # En pause
    FINISHED = "finished"     # Terminée
    CANCELLED = "cancelled"   # Annulée
    ABANDONED = "abandoned"   # Abandonnée


class Difficulty(str, Enum):
    """Niveaux de difficulté"""
    EASY = "easy"            # Facile (4 couleurs, 3 positions)
    NORMAL = "normal"        # Normal (6 couleurs, 4 positions)
    HARD = "hard"           # Difficile (8 couleurs, 5 positions)
    EXPERT = "expert"       # Expert (10 couleurs, 6 positions)


class ParticipationStatus(str, Enum):
    """Statut de participation"""
    ACTIVE = "active"        # Participe activement
    SPECTATOR = "spectator"  # Spectateur
    ELIMINATED = "eliminated"  # Éliminé (battle royale)
    DISCONNECTED = "disconnected"  # Déconnecté
    FINISHED = "finished"    # A terminé sa partie


# === MODÈLE PRINCIPAL DE JEU ===

class Game(Base):
    """
    Modèle principal d'une partie de Quantum Mastermind
    """
    __tablename__ = "games"

    # === IDENTIFICATION ===

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True
    )

    room_code: Mapped[Optional[str]] = mapped_column(
        String(10),
        unique=True,
        index=True,
        nullable=True,
        comment="Code de room personnalisé"
    )

    # === CONFIGURATION DE JEU ===

    game_type: Mapped[GameType] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )

    game_mode: Mapped[GameMode] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )

    difficulty: Mapped[Difficulty] = mapped_column(
        String(10),
        nullable=False,
        default=Difficulty.NORMAL
    )

    status: Mapped[GameStatus] = mapped_column(
        String(15),
        nullable=False,
        default=GameStatus.WAITING,
        index=True
    )

    # === PARAMÈTRES ===

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=12
    )

    combination_length: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=4
    )

    color_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=6
    )

    time_limit_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Limite de temps par tentative en secondes"
    )

    max_players: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1
    )

    # === SÉCURITÉ ET ACCÈS ===

    is_private: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Hash du mot de passe pour rejoindre"
    )

    # === SOLUTION ET ÉTAT ===

    classical_solution: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Solution classique (JSON array)"
    )

    quantum_solution: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="État quantique de la solution"
    )

    solution_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Hash de vérification de la solution"
    )

    # === MÉTADONNÉES DE JEU ===

    current_turn: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    total_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    quantum_hints_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    # === PARAMÈTRES AVANCÉS ===

    settings: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=lambda: {
            "allow_duplicates": True,
            "allow_blanks": False,
            "quantum_enabled": True,
            "hint_cost": 10,
            "auto_reveal_pegs": True,
            "show_statistics": True
        }
    )

    # === RELATIONS ===

    # Créateur de la partie
    creator_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    creator: Mapped["User"] = relationship(
        "User",
        back_populates="created_games",
        foreign_keys=[creator_id]
    )

    # Participations
    participations: Mapped[List["GameParticipation"]] = relationship(
        "GameParticipation",
        back_populates="game",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    # Tentatives
    attempts: Mapped[List["GameAttempt"]] = relationship(
        "GameAttempt",
        back_populates="game",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    # === MÉTADONNÉES TEMPORELLES ===

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
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

    # === CONTRAINTES ===

    __table_args__ = (
        # Index composites
        Index("ix_games_status_type", "status", "game_type"),
        Index("ix_games_created_status", "created_at", "status"),
        Index("ix_games_creator_status", "creator_id", "status"),

        # Contraintes de validation
        CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 50",
            name="ck_max_attempts_valid"
        ),
        CheckConstraint(
            "combination_length > 0 AND combination_length <= 10",
            name="ck_combination_length_valid"
        ),
        CheckConstraint(
            "color_count >= combination_length",
            name="ck_color_count_sufficient"
        ),
        CheckConstraint(
            "max_players > 0 AND max_players <= 8",
            name="ck_max_players_valid"
        ),
        CheckConstraint(
            "time_limit_seconds IS NULL OR time_limit_seconds > 0",
            name="ck_time_limit_positive"
        ),
        CheckConstraint(
            "current_turn >= 0",
            name="ck_current_turn_positive"
        ),
        CheckConstraint(
            "total_attempts >= 0",
            name="ck_total_attempts_positive"
        ),
    )

    # === MÉTHODES ===

    def __repr__(self) -> str:
        return f"<Game(id={self.id}, type={self.game_type}, status={self.status})>"

    @property
    def is_active(self) -> bool:
        """Vérifie si la partie est active"""
        return self.status == GameStatus.ACTIVE

    @property
    def is_finished(self) -> bool:
        """Vérifie si la partie est terminée"""
        return self.status in [GameStatus.FINISHED, GameStatus.CANCELLED, GameStatus.ABANDONED]

    @property
    def can_join(self) -> bool:
        """Vérifie si on peut rejoindre la partie"""
        return self.status == GameStatus.WAITING and not self.is_full

    @property
    def is_full(self) -> bool:
        """Vérifie si la partie est complète"""
        active_count = self.participations.filter_by(status=ParticipationStatus.ACTIVE).count()
        return active_count >= self.max_players

    @property
    def duration_minutes(self) -> Optional[float]:
        """Calcule la durée de la partie en minutes"""
        if not self.started_at:
            return None

        end_time = self.finished_at or datetime.now(timezone.utc)
        duration = end_time - self.started_at
        return duration.total_seconds() / 60

    @property
    def active_player_count(self) -> int:
        """Nombre de joueurs actifs"""
        return self.participations.filter_by(status=ParticipationStatus.ACTIVE).count()

    @property
    def difficulty_config(self) -> dict:
        """Configuration basée sur la difficulté"""
        configs = {
            Difficulty.EASY: {"colors": 4, "length": 3, "attempts": 15},
            Difficulty.NORMAL: {"colors": 6, "length": 4, "attempts": 12},
            Difficulty.HARD: {"colors": 8, "length": 5, "attempts": 10},
            Difficulty.EXPERT: {"colors": 10, "length": 6, "attempts": 8}
        }
        return configs.get(self.difficulty, configs[Difficulty.NORMAL])

    def get_setting(self, key: str, default=None):
        """Récupère un paramètre de jeu"""
        if not self.settings:
            return default
        return self.settings.get(key, default)

    def set_setting(self, key: str, value) -> None:
        """Définit un paramètre de jeu"""
        if not self.settings:
            self.settings = {}
        self.settings[key] = value

    def start_game(self) -> None:
        """Démarre la partie"""
        if self.status != GameStatus.WAITING:
            raise ValueError("La partie ne peut pas être démarrée")

        self.status = GameStatus.ACTIVE
        self.started_at = datetime.now(timezone.utc)

    def finish_game(self) -> None:
        """Termine la partie"""
        if not self.is_active:
            raise ValueError("La partie n'est pas active")

        self.status = GameStatus.FINISHED
        self.finished_at = datetime.now(timezone.utc)

    def pause_game(self) -> None:
        """Met en pause la partie"""
        if not self.is_active:
            raise ValueError("La partie n'est pas active")

        self.status = GameStatus.PAUSED

    def resume_game(self) -> None:
        """Reprend la partie"""
        if self.status != GameStatus.PAUSED:
            raise ValueError("La partie n'est pas en pause")

        self.status = GameStatus.ACTIVE


# === MODÈLE DE PARTICIPATION ===

class GameParticipation(Base):
    """
    Participation d'un utilisateur à une partie
    """
    __tablename__ = "game_participations"

    # === IDENTIFICATION ===

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    # === RELATIONS ===

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

    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="participations"
    )

    player: Mapped["User"] = relationship(
        "User",
        back_populates="game_participations"
    )

    # === STATUT ET PARAMÈTRES ===

    status: Mapped[ParticipationStatus] = mapped_column(
        String(15),
        nullable=False,
        default=ParticipationStatus.ACTIVE
    )

    player_name: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Nom d'affichage dans cette partie"
    )

    # === STATISTIQUES ===

    attempts_made: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    quantum_hints_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    is_winner: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    finish_position: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Position de fin (1er, 2ème, etc.)"
    )

    # === MÉTADONNÉES ===

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    left_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # === CONTRAINTES ===

    __table_args__ = (
        # Contrainte d'unicité
        Index("ix_unique_game_player", "game_id", "player_id", unique=True),

        # Index pour les requêtes
        Index("ix_participation_status", "status"),
        Index("ix_participation_score", "score"),

        # Contraintes de validation
        CheckConstraint(
            "attempts_made >= 0",
            name="ck_attempts_made_positive"
        ),
        CheckConstraint(
            "score >= 0",
            name="ck_score_positive"
        ),
        CheckConstraint(
            "quantum_hints_used >= 0",
            name="ck_quantum_hints_positive"
        ),
        CheckConstraint(
            "finish_position IS NULL OR finish_position > 0",
            name="ck_finish_position_positive"
        ),
    )

    def __repr__(self) -> str:
        return f"<GameParticipation(game_id={self.game_id}, player_id={self.player_id}, status={self.status})>"


# === MODÈLE DE TENTATIVE ===

class GameAttempt(Base):
    """
    Tentative de solution dans une partie
    """
    __tablename__ = "game_attempts"

    # === IDENTIFICATION ===

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    # === RELATIONS ===

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

    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="attempts"
    )

    player: Mapped["User"] = relationship(
        "User"
    )

    # === DONNÉES DE TENTATIVE ===

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    combination: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Combinaison proposée (JSON array)"
    )

    # === RÉSULTAT ===

    black_pegs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Pions noirs (bonne couleur, bonne position)"
    )

    white_pegs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Pions blancs (bonne couleur, mauvaise position)"
    )

    is_solution: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    # === MÉTADONNÉES QUANTIQUES ===

    used_quantum_hint: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    quantum_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Données quantiques de la tentative"
    )

    # === TIMING ===

    time_taken_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Temps pris pour cette tentative"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    # === CONTRAINTES ===

    __table_args__ = (
        # Index composites
        Index("ix_attempts_game_player", "game_id", "player_id"),
        Index("ix_attempts_game_number", "game_id", "attempt_number"),

        # Contrainte d'unicité
        Index("ix_unique_game_player_attempt", "game_id", "player_id", "attempt_number", unique=True),

        # Contraintes de validation
        CheckConstraint(
            "attempt_number > 0",
            name="ck_attempt_number_positive"
        ),
        CheckConstraint(
            "black_pegs >= 0",
            name="ck_black_pegs_positive"
        ),
        CheckConstraint(
            "white_pegs >= 0",
            name="ck_white_pegs_positive"
        ),
        CheckConstraint(
            "time_taken_seconds IS NULL OR time_taken_seconds >= 0",
            name="ck_time_taken_positive"
        ),
    )

    def __repr__(self) -> str:
        return f"<GameAttempt(game_id={self.game_id}, attempt={self.attempt_number}, result={self.black_pegs}B{self.white_pegs}W)>"

    @property
    def result_string(self) -> str:
        """Retourne le résultat sous forme de chaîne"""
        return f"{self.black_pegs}B{self.white_pegs}W"

    @property
    def is_perfect(self) -> bool:
        """Vérifie si c'est une solution parfaite"""
        return self.is_solution and self.black_pegs > 0 and self.white_pegs == 0


# === FONCTIONS UTILITAIRES ===

def generate_room_code() -> str:
    """Génère un code de room unique"""
    import random
    import string

    # Code de 6 caractères alphanumériques
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def calculate_game_score(
    attempts: int,
    max_attempts: int,
    time_taken: Optional[float] = None,
    quantum_used: bool = False,
    difficulty: Difficulty = Difficulty.NORMAL
) -> int:
    """
    Calcule le score d'une partie

    Args:
        attempts: Nombre de tentatives utilisées
        max_attempts: Nombre maximum de tentatives
        time_taken: Temps pris en secondes
        quantum_used: Si des fonctionnalités quantiques ont été utilisées
        difficulty: Niveau de difficulté

    Returns:
        Score calculé
    """
    base_score = 1000

    # Multiplicateur de difficulté
    difficulty_multipliers = {
        Difficulty.EASY: 0.5,
        Difficulty.NORMAL: 1.0,
        Difficulty.HARD: 1.5,
        Difficulty.EXPERT: 2.0
    }

    multiplier = difficulty_multipliers.get(difficulty, 1.0)

    # Pénalité pour les tentatives
    attempt_penalty = (attempts - 1) * 50

    # Bonus pour la rapidité (si temps disponible)
    time_bonus = 0
    if time_taken and time_taken < 300:  # Moins de 5 minutes
        time_bonus = max(0, (300 - time_taken) * 2)

    # Bonus quantique
    quantum_bonus = 200 if quantum_used else 0

    # Calcul final
    final_score = max(0, int((base_score - attempt_penalty + time_bonus + quantum_bonus) * multiplier))

    return final_score