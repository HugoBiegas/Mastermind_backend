"""
Modèles de jeu pour Quantum Mastermind
SQLAlchemy 2.0.41 avec typing moderne et support quantique
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
    FINISHED = "finished"    # Terminé sa partie


# === FONCTIONS UTILITAIRES ===

def generate_room_code(length: int = 6) -> str:
    """Génère un code de room aléatoire"""
    chars = string.ascii_uppercase + string.digits
    # Éviter les caractères confus
    chars = chars.replace('0', '').replace('O', '').replace('1', '').replace('I', '')
    return ''.join(secrets.choice(chars) for _ in range(length))


def generate_solution(combination_length: int, color_count: int, allow_duplicates: bool = True) -> List[int]:
    """Génère une solution aléatoire"""
    if allow_duplicates:
        return [secrets.randbelow(color_count) + 1 for _ in range(combination_length)]
    else:
        if color_count < combination_length:
            raise ValueError("Pas assez de couleurs pour une combinaison sans doublons")
        colors = list(range(1, color_count + 1))
        return secrets.SystemRandom().sample(colors, combination_length)


def calculate_game_score(
    attempts_used: int,
    max_attempts: int,
    time_taken: int,
    difficulty: Difficulty,
    quantum_bonus: int = 0
) -> int:
    """Calcule le score d'une partie"""
    base_scores = {
        Difficulty.EASY: 100,
        Difficulty.NORMAL: 200,
        Difficulty.HARD: 400,
        Difficulty.EXPERT: 800
    }

    base_score = base_scores.get(difficulty, 200)

    # Bonus basé sur les tentatives restantes
    attempts_bonus = max(0, (max_attempts - attempts_used) * 10)

    # Bonus temporel (bonus si résolu rapidement)
    time_bonus = max(0, (600 - time_taken) // 10)  # 10 min = 600s

    total_score = base_score + attempts_bonus + time_bonus + quantum_bonus
    return max(0, total_score)


# === MODÈLE PRINCIPAL DE PARTIE ===

class Game(Base):
    """
    Modèle principal représentant une partie de Quantum Mastermind
    """
    __tablename__ = "games"

    # === IDENTIFICATION ===

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    room_code: Mapped[str] = mapped_column(
        String(10),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: generate_room_code()
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

    status: Mapped[GameStatus] = mapped_column(
        String(15),
        nullable=False,
        default=GameStatus.WAITING,
        index=True
    )

    difficulty: Mapped[Difficulty] = mapped_column(
        String(10),
        nullable=False,
        default=Difficulty.NORMAL
    )

    # === PARAMÈTRES DE PARTIE ===

    max_players: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1
    )

    max_attempts: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=10
    )

    time_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Limite de temps en secondes"
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

    # === ACCÈS ET SÉCURITÉ ===

    is_private: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    password_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Hash SHA-256 du mot de passe"
    )

    # === SOLUTION ET ÉTAT ===

    solution: Mapped[Optional[str]] = mapped_column(
        Text,
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
        nullable=True
    )

    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # === CONTRAINTES ===

    __table_args__ = (
        # Index composites
        Index("ix_games_status_created", "status", "created_at"),
        Index("ix_games_type_mode", "game_type", "game_mode"),
        Index("ix_games_creator_status", "creator_id", "status"),

        # Contraintes de validation
        CheckConstraint(
            "max_players >= 1 AND max_players <= 8",
            name="ck_max_players_range"
        ),
        CheckConstraint(
            "combination_length >= 3 AND combination_length <= 8",
            name="ck_combination_length_range"
        ),
        CheckConstraint(
            "color_count >= 4 AND color_count <= 12",
            name="ck_color_count_range"
        ),
        CheckConstraint(
            "max_attempts IS NULL OR max_attempts > 0",
            name="ck_max_attempts_positive"
        ),
        CheckConstraint(
            "time_limit IS NULL OR time_limit > 0",
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

    # === PROPRIÉTÉS CALCULÉES ===

    @property
    def is_active(self) -> bool:
        """Vérifie si la partie est active"""
        return self.status == GameStatus.ACTIVE

    @property
    def is_finished(self) -> bool:
        """Vérifie si la partie est terminée"""
        return self.status in [GameStatus.FINISHED, GameStatus.CANCELLED, GameStatus.ABANDONED]

    @property
    def duration(self) -> Optional[int]:
        """Durée de la partie en secondes"""
        if not self.started_at:
            return None
        end_time = self.finished_at or datetime.now(timezone.utc)
        return int((end_time - self.started_at).total_seconds())

    @property
    def is_full(self) -> bool:
        """Vérifie si la partie est pleine"""
        current_players = self.participations.filter(
            GameParticipation.status == ParticipationStatus.ACTIVE
        ).count()
        return current_players >= self.max_players

    @property
    def can_start(self) -> bool:
        """Vérifie si la partie peut démarrer"""
        if self.status != GameStatus.WAITING:
            return False

        active_players = self.participations.filter(
            GameParticipation.status == ParticipationStatus.ACTIVE
        ).count()

        return active_players >= 1  # Au moins 1 joueur

    @property
    def solution_list(self) -> Optional[List[int]]:
        """Retourne la solution sous forme de liste"""
        if not self.solution:
            return None
        try:
            return json.loads(self.solution)
        except (json.JSONDecodeError, TypeError):
            return None

    # === MÉTHODES D'INSTANCE ===

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Récupère un paramètre de jeu"""
        if not self.settings:
            return default
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """Définit un paramètre de jeu"""
        if self.settings is None:
            self.settings = {}
        self.settings[key] = value

    def set_solution(self, solution: List[int]) -> None:
        """Définit la solution de la partie"""
        import hashlib

        self.solution = json.dumps(solution)
        # Hash pour vérification d'intégrité
        solution_str = ''.join(map(str, solution))
        self.solution_hash = hashlib.sha256(solution_str.encode()).hexdigest()

    def verify_solution(self, proposed_solution: List[int]) -> bool:
        """Vérifie une solution proposée"""
        return self.solution_list == proposed_solution

    def start_game(self) -> None:
        """Démarre la partie"""
        if not self.can_start:
            raise ValueError("La partie ne peut pas démarrer")

        self.status = GameStatus.ACTIVE
        self.started_at = datetime.now(timezone.utc)

    def finish_game(self, reason: str = "completed") -> None:
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

    def cancel_game(self, reason: str = "cancelled") -> None:
        """Annule la partie"""
        if self.is_finished:
            raise ValueError("La partie est déjà terminée")

        self.status = GameStatus.CANCELLED
        self.finished_at = datetime.now(timezone.utc)

    def abandon_game(self) -> None:
        """Abandonne la partie (tous les joueurs partis)"""
        self.status = GameStatus.ABANDONED
        self.finished_at = datetime.now(timezone.utc)

    def add_quantum_hint(self) -> None:
        """Incrémente le compteur de hints quantiques"""
        self.quantum_hints_used += 1

    def __repr__(self) -> str:
        return f"<Game(id={self.id}, room_code='{self.room_code}', status='{self.status}')>"


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

    # === MÉTADONNÉES TEMPORELLES ===

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
        Index("ix_participation_unique", "game_id", "player_id", unique=True),

        # Index composites
        Index("ix_participation_game_status", "game_id", "status"),
        Index("ix_participation_player_status", "player_id", "status"),

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

    # === PROPRIÉTÉS CALCULÉES ===

    @property
    def is_active(self) -> bool:
        """Vérifie si la participation est active"""
        return self.status == ParticipationStatus.ACTIVE

    @property
    def duration(self) -> Optional[int]:
        """Durée de participation en secondes"""
        if not self.joined_at:
            return None
        end_time = self.left_at or datetime.now(timezone.utc)
        return int((end_time - self.joined_at).total_seconds())

    # === MÉTHODES D'INSTANCE ===

    def leave_game(self) -> None:
        """Quitte la partie"""
        if self.status == ParticipationStatus.ACTIVE:
            self.status = ParticipationStatus.DISCONNECTED
            self.left_at = datetime.now(timezone.utc)

    def eliminate(self) -> None:
        """Élimine le joueur (battle royale)"""
        self.status = ParticipationStatus.ELIMINATED
        self.finished_at = datetime.now(timezone.utc)

    def finish(self, position: int, won: bool = False) -> None:
        """Termine la participation"""
        self.status = ParticipationStatus.FINISHED
        self.finish_position = position
        self.is_winner = won
        self.finished_at = datetime.now(timezone.utc)

    def add_attempt(self, score: int = 0) -> None:
        """Ajoute une tentative"""
        self.attempts_made += 1
        if score > 0:
            self.score += score

    def use_quantum_hint(self) -> None:
        """Utilise un hint quantique"""
        self.quantum_hints_used += 1

    def __repr__(self) -> str:
        return f"<GameParticipation(game_id={self.game_id}, player_id={self.player_id}, status='{self.status}')>"


# === MODÈLE DE TENTATIVE ===

class GameAttempt(Base):
    """
    Tentative d'un joueur dans une partie
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
        "User",
        back_populates="game_attempts"
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

    is_winning: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    score_gained: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
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

    # === MÉTADONNÉES TEMPORELLES ===

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    time_taken: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Temps pris pour cette tentative en secondes"
    )

    # === CONTRAINTES ===

    __table_args__ = (
        # Index composites
        Index("ix_attempt_game_number", "game_id", "attempt_number"),
        Index("ix_attempt_player_game", "player_id", "game_id"),
        Index("ix_attempt_created", "created_at"),

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
            "score_gained >= 0",
            name="ck_score_gained_positive"
        ),
        CheckConstraint(
            "time_taken IS NULL OR time_taken >= 0",
            name="ck_time_taken_positive"
        ),
    )

    # === PROPRIÉTÉS CALCULÉES ===

    @property
    def combination_list(self) -> List[int]:
        """Retourne la combinaison sous forme de liste"""
        try:
            return json.loads(self.combination)
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def total_pegs(self) -> int:
        """Nombre total de pions (noirs + blancs)"""
        return self.black_pegs + self.white_pegs

    # === MÉTHODES D'INSTANCE ===

    def set_combination(self, combination: List[int]) -> None:
        """Définit la combinaison proposée"""
        self.combination = json.dumps(combination)

    def set_result(self, black_pegs: int, white_pegs: int, is_winning: bool = False) -> None:
        """Définit le résultat de la tentative"""
        self.black_pegs = black_pegs
        self.white_pegs = white_pegs
        self.is_winning = is_winning

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
        target.combination = json.dumps(target.combination)


# === EXPORTS ===

__all__ = [
    # Énumérations
    "GameType", "GameMode", "GameStatus", "Difficulty", "ParticipationStatus",

    # Modèles
    "Game", "GameParticipation", "GameAttempt",

    # Fonctions utilitaires
    "generate_room_code", "generate_solution", "calculate_game_score"
]