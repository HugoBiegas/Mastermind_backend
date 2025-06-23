"""
Modèles SQLAlchemy pour le système multijoueur
COMPLET: Synchronisation parfaite avec init.sql et schemas Pydantic
Version: 2.0.0 - Tous les modèles multijoueur
"""
import enum
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, DateTime, Float, Integer, String, Text,
    ForeignKey, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.game import Difficulty


# =====================================================
# ENUMS POUR LE MULTIJOUEUR
# =====================================================

class MultiplayerGameType(str, enum.Enum):
    """Types de parties multijoueur"""
    MULTI_MASTERMIND = "multi_mastermind"
    BATTLE_ROYALE = "battle_royale"
    TOURNAMENT = "tournament"


class PlayerStatus(str, enum.Enum):
    """Statuts des joueurs dans une partie multijoueur"""
    WAITING = "waiting"
    READY = "ready"
    PLAYING = "active"
    PAUSED = "paused"
    FINISHED = "finished"
    DISCONNECTED = "disconnected"
    ELIMINATED = "eliminated"


class ItemType(str, enum.Enum):
    """Types d'objets de jeu"""
    EXTRA_HINT = "extra_hint"
    TIME_BONUS = "time_bonus"
    SKIP_MASTERMIND = "skip_mastermind"
    DOUBLE_SCORE = "double_score"
    FREEZE_TIME = "freeze_time"
    ADD_MASTERMIND = "add_mastermind"
    REDUCE_ATTEMPTS = "reduce_attempts"
    SCRAMBLE_COLORS = "scramble_colors"


class ItemRarity(str, enum.Enum):
    """Rareté des objets"""
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


# =====================================================
# MODÈLE PRINCIPAL MULTIJOUEUR
# =====================================================

class MultiplayerGame(Base):
    """
    Partie multijoueur principale
    CORRECTION: Synchronisé exactement avec init.sql
    """
    __tablename__ = "multiplayer_games"

    # === CLÉS PRIMAIRES ===
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    base_game_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("games.id", ondelete="CASCADE"),
        unique=True
    )

    # === CONFIGURATION MULTIJOUEUR ===
    game_type: Mapped[MultiplayerGameType] = mapped_column(
        String(50),
        nullable=False,
        default=MultiplayerGameType.MULTI_MASTERMIND
    )
    total_masterminds: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    current_mastermind: Mapped[int] = mapped_column(Integer, default=1)
    is_final_mastermind: Mapped[bool] = mapped_column(Boolean, default=False)

    # === CONFIGURATION DE DIFFICULTÉ (dupliqué pour performance) ===
    difficulty: Mapped[Difficulty] = mapped_column(String(20), nullable=False)

    # === CONFIGURATION DES OBJETS ===
    items_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    items_per_mastermind: Mapped[int] = mapped_column(Integer, default=1)

    # === MÉTADONNÉES TEMPORELLES (selon init.sql) ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # === RELATIONS ===
    base_game: Mapped["Game"] = relationship("Game", lazy="select")
    player_progresses: Mapped[List["PlayerProgress"]] = relationship(
        "PlayerProgress",
        back_populates="multiplayer_game",
        cascade="all, delete-orphan"
    )
    masterminds: Mapped[List["GameMastermind"]] = relationship(
        "GameMastermind",
        back_populates="multiplayer_game",
        cascade="all, delete-orphan"
    )
    leaderboard: Mapped[List["PlayerLeaderboard"]] = relationship(
        "PlayerLeaderboard",
        back_populates="multiplayer_game",
        cascade="all, delete-orphan"
    )

    # === CONTRAINTES ===
    __table_args__ = (
        CheckConstraint("game_type IN ('multi_mastermind', 'battle_royale', 'tournament')", name="ck_game_type_valid"),
        CheckConstraint("total_masterminds >= 1 AND total_masterminds <= 10", name="ck_total_masterminds_bounds"),
        CheckConstraint("current_mastermind >= 1 AND current_mastermind <= total_masterminds",
                        name="ck_current_mastermind_bounds"),
        CheckConstraint("difficulty IN ('easy', 'medium', 'hard', 'expert', 'quantum')",
                        name="ck_game_difficulty_valid"),
        CheckConstraint("items_per_mastermind >= 0", name="ck_items_per_mastermind_non_negative"),
        UniqueConstraint("base_game_id", name="uq_multiplayer_games_base_game"),
    )

    def __repr__(self) -> str:
        return f"<MultiplayerGame(id={self.id}, type={self.game_type}, masterminds={self.total_masterminds})>"


# =====================================================
# MASTERMINDS INDIVIDUELS
# =====================================================

class GameMastermind(Base):
    """
    Mastermind individuel dans une partie multijoueur
    CORRECTION: Correspond exactement à init.sql
    """
    __tablename__ = "game_masterminds"

    # === CLÉS ===
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    multiplayer_game_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("multiplayer_games.id", ondelete="CASCADE")
    )
    mastermind_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # === CONFIGURATION (selon init.sql) ===
    combination_length: Mapped[int] = mapped_column(Integer, nullable=False)
    available_colors: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)

    # === SOLUTION SECRÈTE (selon init.sql) ===
    solution: Mapped[List[int]] = mapped_column(JSONB, nullable=False)

    # === ÉTAT (selon init.sql) ===
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # === MÉTADONNÉES TEMPORELLES (selon init.sql - SEULEMENT created_at et completed_at) ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # === RELATIONS ===
    multiplayer_game: Mapped["MultiplayerGame"] = relationship("MultiplayerGame", back_populates="masterminds")
    player_attempts: Mapped[List["PlayerMastermindAttempt"]] = relationship(
        "PlayerMastermindAttempt",
        back_populates="mastermind",
        cascade="all, delete-orphan"
    )

    # === CONTRAINTES ===
    __table_args__ = (
        CheckConstraint("mastermind_number >= 1", name="ck_mastermind_number_positive"),
        CheckConstraint("combination_length >= 2 AND combination_length <= 8", name="ck_combination_length_bounds"),
        CheckConstraint("available_colors >= 3 AND available_colors <= 15", name="ck_available_colors_bounds"),
        CheckConstraint("max_attempts > 0", name="ck_max_attempts_positive"),
        UniqueConstraint("multiplayer_game_id", "mastermind_number", name="uq_game_masterminds_game_number"),
        Index("idx_multiplayer_mastermind", "multiplayer_game_id", "mastermind_number"),
    )

    def __repr__(self) -> str:
        return f"<GameMastermind(id={self.id}, number={self.mastermind_number}, active={self.is_active})>"


# =====================================================
# PROGRESSION DES JOUEURS
# =====================================================

class PlayerProgress(Base):
    """Progression d'un joueur dans une partie multijoueur"""
    __tablename__ = "player_progress"

    # === CLÉS ===
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    multiplayer_game_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("multiplayer_games.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE")
    )

    # === STATUT DU JOUEUR ===
    status: Mapped[PlayerStatus] = mapped_column(String(30), default=PlayerStatus.WAITING)

    # === PROGRESSION ===
    current_mastermind: Mapped[int] = mapped_column(Integer, default=1)
    completed_masterminds: Mapped[int] = mapped_column(Integer, default=0)

    # === SCORES ===
    total_score: Mapped[int] = mapped_column(Integer, default=0)

    # === TEMPS TOTAL ===
    total_time: Mapped[float] = mapped_column(Float, default=0.0)

    # === ÉTAT DE FIN ===
    is_finished: Mapped[bool] = mapped_column(Boolean, default=False)
    finish_position: Mapped[Optional[int]] = mapped_column(Integer)
    finish_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # === OBJETS COLLECTÉS (JSONB selon init.sql) ===
    collected_items: Mapped[List[str]] = mapped_column(JSONB, default=list)
    used_items: Mapped[List[str]] = mapped_column(JSONB, default=list)

    # === MÉTADONNÉES TEMPORELLES ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # === RELATIONS ===
    multiplayer_game: Mapped["MultiplayerGame"] = relationship("MultiplayerGame", back_populates="player_progresses")
    user: Mapped["User"] = relationship("User", lazy="select")

    # === CONTRAINTES ===
    __table_args__ = (
        CheckConstraint(
            "status IN ('waiting', 'ready', 'playing', 'paused', 'finished', 'disconnected', 'eliminated')",
            name="ck_progress_status_valid"
        ),
        CheckConstraint("current_mastermind >= 1", name="ck_progress_current_mastermind_positive"),
        CheckConstraint("completed_masterminds >= 0", name="ck_progress_completed_masterminds_positive"),
        CheckConstraint("total_score >= 0", name="ck_progress_total_score_positive"),
        CheckConstraint("total_time >= 0", name="ck_progress_total_time_positive"),
        CheckConstraint("finish_position IS NULL OR finish_position >= 1", name="ck_progress_finish_position_valid"),
        UniqueConstraint("multiplayer_game_id", "user_id", name="uq_player_progress_game_user"),
        Index("idx_player_progress_game", "multiplayer_game_id"),
        Index("idx_player_progress_user", "user_id"),
        Index("idx_player_progress_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<PlayerProgress(user_id={self.user_id}, status={self.status}, score={self.total_score})>"


# =====================================================
# TENTATIVES PAR MASTERMIND
# =====================================================

class PlayerMastermindAttempt(Base):
    """Tentative d'un joueur sur un mastermind spécifique"""
    __tablename__ = "player_mastermind_attempts"

    # === CLÉS ===
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    mastermind_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("game_masterminds.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE")
    )

    # === DONNÉES DE TENTATIVE ===
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    combination: Mapped[List[int]] = mapped_column(JSONB, nullable=False)

    # === RÉSULTATS ===
    exact_matches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    position_matches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_winning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # === SCORING ===
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    time_taken: Mapped[Optional[int]] = mapped_column(Integer)  # en millisecondes

    # === DONNÉES QUANTIQUES ===
    quantum_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    hint_type: Mapped[Optional[str]] = mapped_column(String(50))

    # === MÉTADONNÉES ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # === RELATIONS ===
    mastermind: Mapped["GameMastermind"] = relationship("GameMastermind", back_populates="player_attempts")
    user: Mapped["User"] = relationship("User", lazy="select")

    # === CONTRAINTES ===
    __table_args__ = (
        CheckConstraint("attempt_number > 0", name="ck_attempts_number_positive"),
        CheckConstraint("exact_matches >= 0", name="ck_attempts_exact_matches_positive"),
        CheckConstraint("position_matches >= 0", name="ck_attempts_position_matches_positive"),
        CheckConstraint("score >= 0", name="ck_attempts_score_positive"),
        CheckConstraint("time_taken IS NULL OR time_taken > 0", name="ck_attempts_time_taken_positive_or_null"),
        CheckConstraint(
            "hint_type IS NULL OR hint_type IN ('grover', 'superposition', 'entanglement', 'interference')",
            name="ck_attempts_hint_type_valid"
        ),
        UniqueConstraint("mastermind_id", "user_id", "attempt_number", name="uq_player_mastermind_attempts"),
        Index("idx_player_attempts_mastermind", "mastermind_id"),
        Index("idx_player_attempts_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<PlayerMastermindAttempt(user_id={self.user_id}, attempt={self.attempt_number}, winning={self.is_winning})>"


# =====================================================
# CLASSEMENTS
# =====================================================

class PlayerLeaderboard(Base):
    """Classement final d'une partie multijoueur"""
    __tablename__ = "player_leaderboard"

    # === CLÉS ===
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    multiplayer_game_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("multiplayer_games.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE")
    )

    # === CLASSEMENT ===
    final_position: Mapped[int] = mapped_column(Integer, nullable=False)
    final_score: Mapped[int] = mapped_column(Integer, nullable=False)
    total_time: Mapped[float] = mapped_column(Float, nullable=False)

    # === STATISTIQUES DÉTAILLÉES ===
    masterminds_completed: Mapped[int] = mapped_column(Integer, default=0)
    total_attempts: Mapped[int] = mapped_column(Integer, default=0)
    perfect_solutions: Mapped[int] = mapped_column(Integer, default=0)
    quantum_hints_used: Mapped[int] = mapped_column(Integer, default=0)
    items_used: Mapped[int] = mapped_column(Integer, default=0)

    # === MÉTADONNÉES ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # === RELATIONS ===
    multiplayer_game: Mapped["MultiplayerGame"] = relationship("MultiplayerGame", back_populates="leaderboard")
    user: Mapped["User"] = relationship("User", lazy="select")

    # === CONTRAINTES ===
    __table_args__ = (
        CheckConstraint("final_position >= 1", name="ck_leaderboard_final_position_positive"),
        CheckConstraint("final_score >= 0", name="ck_leaderboard_final_score_positive"),
        CheckConstraint("total_time >= 0", name="ck_leaderboard_total_time_positive"),
        CheckConstraint("masterminds_completed >= 0", name="ck_leaderboard_masterminds_completed_positive"),
        CheckConstraint("total_attempts >= 0", name="ck_leaderboard_total_attempts_positive"),
        CheckConstraint("perfect_solutions >= 0", name="ck_leaderboard_perfect_solutions_positive"),
        CheckConstraint("quantum_hints_used >= 0", name="ck_leaderboard_quantum_hints_used_positive"),
        CheckConstraint("items_used >= 0", name="ck_leaderboard_items_used_positive"),

        UniqueConstraint("multiplayer_game_id", "user_id", name="uq_player_leaderboard_game_user"),
        Index("idx_leaderboard_game", "multiplayer_game_id"),
        Index("idx_leaderboard_position", "final_position"),
    )

    def __repr__(self) -> str:
        return f"<PlayerLeaderboard(user_id={self.user_id}, position={self.final_position}, score={self.final_score})>"


# =====================================================
# OBJETS DE JEU
# =====================================================

class GameItem(Base):
    """Objets collectibles et utilisables dans les parties"""
    __tablename__ = "game_items"

    # === CLÉS ===
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # === INFORMATIONS DE BASE ===
    item_type: Mapped[ItemType] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rarity: Mapped[ItemRarity] = mapped_column(String(20), nullable=False)

    # === PROPRIÉTÉS ===
    is_offensive: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    effect_value: Mapped[Optional[int]] = mapped_column(Integer)

    # === MÉTADONNÉES ===
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # === CONTRAINTES ===
    __table_args__ = (
        CheckConstraint(
            "item_type IN ('extra_hint', 'time_bonus', 'skip_mastermind', 'double_score', 'freeze_time', 'add_mastermind', 'reduce_attempts', 'scramble_colors')",
            name="ck_game_items_item_type_valid"
        ),
        CheckConstraint(
            "rarity IN ('common', 'rare', 'epic', 'legendary')",
            name="ck_game_items_rarity_valid"
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds > 0",
            name="ck_game_items_duration_positive_or_null"
        ),
        Index("idx_game_items_type", "item_type"),
        Index("idx_game_items_rarity", "rarity"),
    )

    def __repr__(self) -> str:
        return f"<GameItem(type={self.item_type}, name={self.name}, rarity={self.rarity})>"


# =====================================================
# SESSIONS WEBSOCKET
# =====================================================

class WebSocketSession(Base):
    """Sessions WebSocket actives"""
    __tablename__ = "websocket_sessions"

    # === CLÉS ===
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # === IDENTIFICATION ===
    session_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    connection_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # === RELATIONS ===
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL")
    )
    game_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("games.id", ondelete="SET NULL")
    )

    # === ÉTAT DE LA CONNEXION ===
    status: Mapped[str] = mapped_column(String(20), default="connected")
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))  # IPv6 compatible
    user_agent: Mapped[Optional[str]] = mapped_column(Text)

    # === MÉTADONNÉES TEMPORELLES ===
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    disconnected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # === STATISTIQUES ===
    messages_sent: Mapped[int] = mapped_column(Integer, default=0)
    messages_received: Mapped[int] = mapped_column(Integer, default=0)

    # === DONNÉES DE SESSION ===
    session_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)

    # === RELATIONS ===
    user: Mapped[Optional["User"]] = relationship("User", lazy="select")
    game: Mapped[Optional["Game"]] = relationship("Game", lazy="select")

    # === CONTRAINTES ===
    __table_args__ = (
        CheckConstraint(
            "status IN ('connected', 'disconnected', 'error', 'timeout')",
            name="ck_websocket_status_valid"
        ),
        CheckConstraint(
            "messages_sent >= 0 AND messages_received >= 0",
            name="ck_websocket_messages_non_negative"
        ),
        Index("idx_websocket_user", "user_id"),
        Index("idx_websocket_game", "game_id"),
        Index("idx_websocket_status", "status"),
    )
    def __repr__(self) -> str:
        return f"<WebSocketSession(id={self.session_id}, user_id={self.user_id}, status={self.status})>"


# =====================================================
# FONCTIONS UTILITAIRES POUR LES MODÈLES
# =====================================================

def get_active_multiplayer_games_count() -> int:
    """Retourne le nombre de parties multijoueur actives"""
    # Cette fonction sera implémentée avec une session de base de données
    pass


def get_player_multiplayer_stats(user_id: UUID) -> Dict[str, Any]:
    """Retourne les statistiques multijoueur d'un joueur"""
    # Cette fonction sera implémentée avec une session de base de données
    pass


def cleanup_expired_websocket_sessions(timeout_minutes: int = 30) -> int:
    """Nettoie les sessions WebSocket expirées"""
    # Cette fonction sera implémentée avec une session de base de données
    pass


# =====================================================
# EXPORTS
# =====================================================

__all__ = [
    # Enums
    "MultiplayerGameType",
    "PlayerStatus",
    "ItemType",
    "ItemRarity",

    # Modèles principaux
    "MultiplayerGame",
    "GameMastermind",
    "PlayerProgress",
    "PlayerMastermindAttempt",
    "PlayerLeaderboard",
    "GameItem",
    "WebSocketSession",

    # Fonctions utilitaires
    "get_active_multiplayer_games_count",
    "get_player_multiplayer_stats",
    "cleanup_expired_websocket_sessions"
]