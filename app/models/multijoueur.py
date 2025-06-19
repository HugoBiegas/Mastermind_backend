"""
Modèles étendus pour le mode multijoueur de Quantum Mastermind
Objets bonus/malus, parties multi-masterminds, classements
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, DateTime, Integer, String, Text, ForeignKey,
    CheckConstraint, Index, event, Float
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.game import GameStatus, Difficulty

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.game import Game


# === ÉNUMÉRATIONS POUR LE MULTIJOUEUR ===

class MultiplayerGameType(str, Enum):
    """Types de parties multijoueur"""
    MULTI_MASTERMIND = "multi_mastermind"  # Plusieurs masterminds par partie
    BATTLE_ROYALE = "battle_royale"  # Élimination progressive
    TOURNAMENT = "tournament"  # Tournoi


class ItemType(str, Enum):
    """Types d'objets bonus/malus"""
    # Bonus pour soi
    EXTRA_HINT = "extra_hint"  # Indice supplémentaire
    TIME_BONUS = "time_bonus"  # Temps bonus
    SKIP_MASTERMIND = "skip_mastermind"  # Passer un mastermind
    DOUBLE_SCORE = "double_score"  # Score x2 pour le prochain mastermind

    # Malus pour les adversaires
    FREEZE_TIME = "freeze_time"  # Geler le temps des adversaires
    ADD_MASTERMIND = "add_mastermind"  # Ajouter un mastermind à tous
    REDUCE_ATTEMPTS = "reduce_attempts"  # Réduire les tentatives
    SCRAMBLE_COLORS = "scramble_colors"  # Mélanger l'affichage des couleurs


class ItemRarity(str, Enum):
    """Rareté des objets"""
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


class PlayerStatus(str, Enum):
    """Statut des joueurs dans une partie multijoueur"""
    WAITING = "waiting"
    PLAYING = "playing"
    MASTERMIND_COMPLETE = "mastermind_complete"
    FINISHED = "finished"
    ELIMINATED = "eliminated"


# === MODÈLES PRINCIPAUX ===

class MultiplayerGame(Base):
    """Partie multijoueur avec plusieurs masterminds"""
    __tablename__ = "multiplayer_games"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    base_game_id: Mapped[UUID] = mapped_column(ForeignKey("games.id"), unique=True)

    # Configuration multijoueur
    game_type: Mapped[MultiplayerGameType] = mapped_column(String(50), nullable=False)
    total_masterminds: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    difficulty: Mapped[Difficulty] = mapped_column(String(20), nullable=False)

    # Progression
    current_mastermind: Mapped[int] = mapped_column(Integer, default=1)
    is_final_mastermind: Mapped[bool] = mapped_column(Boolean, default=False)

    # Objets et bonus
    items_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    items_per_mastermind: Mapped[int] = mapped_column(Integer, default=1)

    # Métadonnées
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relations
    base_game: Mapped["Game"] = relationship("Game", back_populates="multiplayer_game")
    player_progresses: Mapped[List["PlayerProgress"]] = relationship("PlayerProgress",
                                                                     back_populates="multiplayer_game")
    masterminds: Mapped[List["GameMastermind"]] = relationship("GameMastermind", back_populates="multiplayer_game")
    leaderboard: Mapped[List["PlayerLeaderboard"]] = relationship("PlayerLeaderboard",
                                                                  back_populates="multiplayer_game")


class GameMastermind(Base):
    """Mastermind individuel dans une partie multijoueur"""
    __tablename__ = "game_masterminds"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    multiplayer_game_id: Mapped[UUID] = mapped_column(ForeignKey("multiplayer_games.id"))
    mastermind_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Solution pour ce mastermind
    solution: Mapped[List[int]] = mapped_column(JSONB, nullable=False)
    combination_length: Mapped[int] = mapped_column(Integer, nullable=False)
    available_colors: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)

    # État
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relations
    multiplayer_game: Mapped["MultiplayerGame"] = relationship("MultiplayerGame", back_populates="masterminds")
    player_attempts: Mapped[List["PlayerMastermindAttempt"]] = relationship("PlayerMastermindAttempt",
                                                                            back_populates="mastermind")

    __table_args__ = (
        Index("idx_multiplayer_mastermind", "multiplayer_game_id", "mastermind_number"),
    )


class PlayerProgress(Base):
    """Progression d'un joueur dans une partie multijoueur"""
    __tablename__ = "player_progress"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    multiplayer_game_id: Mapped[UUID] = mapped_column(ForeignKey("multiplayer_games.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    # Progression
    current_mastermind: Mapped[int] = mapped_column(Integer, default=1)
    completed_masterminds: Mapped[int] = mapped_column(Integer, default=0)
    total_score: Mapped[int] = mapped_column(Integer, default=0)
    total_time: Mapped[float] = mapped_column(Float, default=0.0)

    # État
    status: Mapped[PlayerStatus] = mapped_column(String(30), default=PlayerStatus.WAITING)
    is_finished: Mapped[bool] = mapped_column(Boolean, default=False)
    finish_position: Mapped[Optional[int]] = mapped_column(Integer)
    finish_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Objets collectés
    collected_items: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list)
    used_items: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list)

    # Relations
    multiplayer_game: Mapped["MultiplayerGame"] = relationship("MultiplayerGame", back_populates="player_progresses")
    user: Mapped["User"] = relationship("User")
    mastermind_attempts: Mapped[List["PlayerMastermindAttempt"]] = relationship("PlayerMastermindAttempt",
                                                                                back_populates="player_progress")

    __table_args__ = (
        Index("idx_player_progress", "multiplayer_game_id", "user_id"),
    )


class PlayerMastermindAttempt(Base):
    """Tentative d'un joueur sur un mastermind spécifique"""
    __tablename__ = "player_mastermind_attempts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    player_progress_id: Mapped[UUID] = mapped_column(ForeignKey("player_progress.id"))
    mastermind_id: Mapped[UUID] = mapped_column(ForeignKey("game_masterminds.id"))

    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    combination: Mapped[List[int]] = mapped_column(JSONB, nullable=False)
    exact_matches: Mapped[int] = mapped_column(Integer, nullable=False)
    position_matches: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)

    # Temps et score
    attempt_score: Mapped[int] = mapped_column(Integer, default=0)
    time_taken: Mapped[float] = mapped_column(Float)

    # Quantique
    quantum_calculated: Mapped[bool] = mapped_column(Boolean, default=False)
    quantum_probabilities: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relations
    player_progress: Mapped["PlayerProgress"] = relationship("PlayerProgress", back_populates="mastermind_attempts")
    mastermind: Mapped["GameMastermind"] = relationship("GameMastermind", back_populates="player_attempts")


class GameItem(Base):
    """Objet/pouvoir disponible dans le jeu"""
    __tablename__ = "game_items"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    item_type: Mapped[ItemType] = mapped_column(String(30), nullable=False)
    rarity: Mapped[ItemRarity] = mapped_column(String(20), nullable=False)

    # Configuration
    is_self_target: Mapped[bool] = mapped_column(Boolean,
                                                 default=True)  # True = bonus pour soi, False = malus pour adversaires
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)  # Pour effets temporaires
    effect_value: Mapped[Optional[float]] = mapped_column(Float)  # Valeur numérique de l'effet

    # Métadonnées
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PlayerLeaderboard(Base):
    """Classement final d'une partie multijoueur"""
    __tablename__ = "player_leaderboard"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    multiplayer_game_id: Mapped[UUID] = mapped_column(ForeignKey("multiplayer_games.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    # Classement
    final_position: Mapped[int] = mapped_column(Integer, nullable=False)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False)
    masterminds_completed: Mapped[int] = mapped_column(Integer, nullable=False)
    total_time: Mapped[float] = mapped_column(Float, nullable=False)
    total_attempts: Mapped[int] = mapped_column(Integer, nullable=False)

    # Statistiques détaillées
    items_collected: Mapped[int] = mapped_column(Integer, default=0)
    items_used: Mapped[int] = mapped_column(Integer, default=0)
    best_mastermind_time: Mapped[Optional[float]] = mapped_column(Float)
    worst_mastermind_time: Mapped[Optional[float]] = mapped_column(Float)

    # Relations
    multiplayer_game: Mapped["MultiplayerGame"] = relationship("MultiplayerGame", back_populates="leaderboard")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("idx_leaderboard_position", "multiplayer_game_id", "final_position"),
    )


# === FONCTIONS UTILITAIRES ===

def generate_items_for_mastermind(rarity_weights: Dict[ItemRarity, float] = None) -> List[Dict[str, Any]]:
    """Génère des objets aléatoirement pour un mastermind complété"""
    import random

    if rarity_weights is None:
        rarity_weights = {
            ItemRarity.COMMON: 0.5,
            ItemRarity.RARE: 0.3,
            ItemRarity.EPIC: 0.15,
            ItemRarity.LEGENDARY: 0.05
        }

    # Définition des objets disponibles
    available_items = {
        ItemType.EXTRA_HINT: {"rarity": ItemRarity.COMMON, "name": "Indice Quantique",
                              "description": "Révèle une couleur correcte"},
        ItemType.TIME_BONUS: {"rarity": ItemRarity.COMMON, "name": "Accélération Temporelle",
                              "description": "+30 secondes de temps"},
        ItemType.DOUBLE_SCORE: {"rarity": ItemRarity.RARE, "name": "Boost Quantique",
                                "description": "Score x2 pour le prochain mastermind"},
        ItemType.SKIP_MASTERMIND: {"rarity": ItemRarity.LEGENDARY, "name": "Saut Dimensionnel",
                                   "description": "Complète automatiquement un mastermind"},
        ItemType.FREEZE_TIME: {"rarity": ItemRarity.EPIC, "name": "Gel Temporel",
                               "description": "Gèle le temps des adversaires pendant 30s"},
        ItemType.ADD_MASTERMIND: {"rarity": ItemRarity.RARE, "name": "Complexification",
                                  "description": "Ajoute un mastermind à tous les adversaires"},
        ItemType.REDUCE_ATTEMPTS: {"rarity": ItemRarity.EPIC, "name": "Sabotage",
                                   "description": "Réduit les tentatives des adversaires de 2"},
        ItemType.SCRAMBLE_COLORS: {"rarity": ItemRarity.RARE, "name": "Distorsion",
                                   "description": "Mélange l'affichage des couleurs des adversaires pendant 60s"}
    }

    # Sélection aléatoire basée sur la rareté
    rarity = random.choices(list(rarity_weights.keys()), weights=list(rarity_weights.values()))[0]
    suitable_items = [item_type for item_type, config in available_items.items() if config["rarity"] == rarity]

    if not suitable_items:
        suitable_items = [ItemType.EXTRA_HINT]  # Fallback

    selected_item = random.choice(suitable_items)
    item_config = available_items[selected_item]

    return [{
        "type": selected_item.value,
        "name": item_config["name"],
        "description": item_config["description"],
        "rarity": rarity.value,
        "obtained_at": datetime.now(timezone.utc).isoformat()
    }]


def calculate_multiplayer_score(
        mastermind_number: int,
        attempts_used: int,
        max_attempts: int,
        time_taken: float,
        is_correct: bool,
        items_used: int = 0
) -> int:
    """Calcule le score pour un mastermind en mode multijoueur"""
    if not is_correct:
        return 0

    # Score de base basé sur les tentatives
    base_score = max(0, (max_attempts - attempts_used + 1) * 100)

    # Bonus de temps (plus on est rapide, plus on gagne)
    time_bonus = max(0, int(300 - time_taken))  # 5 minutes max bonus

    # Multiplicateur selon le numéro du mastermind (plus difficile = plus de points)
    difficulty_multiplier = 1 + (mastermind_number - 1) * 0.2

    # Malus pour utilisation d'objets (encourage le skill)
    item_penalty = items_used * 50

    total_score = int((base_score + time_bonus) * difficulty_multiplier - item_penalty)
    return max(0, total_score)