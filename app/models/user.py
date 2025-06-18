"""
Modèle utilisateur pour Quantum Mastermind
SQLAlchemy 2.0.41 avec typing moderne et async support
CORRECTION: Relations synchronisées avec game.py
"""
from datetime import datetime, timezone, timedelta
from ipaddress import ip_address, AddressValueError
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import EmailStr
from sqlalchemy import (
    Boolean, DateTime, String, Text, Integer,
    Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Import conditionnel pour éviter les imports circulaires
if TYPE_CHECKING:
    from app.models.game import Game, GameParticipation, GameAttempt

class User(Base):
    """
    Modèle utilisateur principal avec support SQLAlchemy 2.0
    CORRECTION: Relations synchronisées avec les modèles de jeu
    """
    __tablename__ = "users"

    # === COLONNES PRINCIPALES ===

    # Clé primaire UUID
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True
    )

    # Informations d'identification
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )

    email: Mapped[EmailStr] = mapped_column(
        String(254),
        unique=True,
        index=True,
        nullable=False
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    # === INFORMATIONS PERSONNELLES ===

    full_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )

    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # === STATUT ET PERMISSIONS ===

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )

    # === PARAMÈTRES ET PRÉFÉRENCES ===

    preferences: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {
            "language": "fr",
            "theme": "dark",
            "notifications": {
                "email": True,
                "push": True,
                "game_invitations": True,
                "game_results": True
            },
            "game_settings": {
                "auto_join": False,
                "show_hints": True,
                "sound_enabled": True
            }
        }
    )

    settings: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {
            "privacy": {
                "profile_visible": True,
                "stats_visible": True,
                "online_status_visible": True
            },
            "gameplay": {
                "auto_ready": False,
                "timeout_warnings": True
            }
        }
    )

    # === STATISTIQUES DE JEU ===

    total_games: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    games_won: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    total_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    best_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )

    quantum_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    rank: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='Bronze',
        index=True
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

    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )

    # === SÉCURITÉ ET AUDIT ===

    email_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    login_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    last_ip_address: Mapped[Optional[str]] = mapped_column(
        INET,
        nullable=True
    )

    # === RELATIONS SQLALCHEMY ===
    # CORRECTION: Relations synchronisées avec les modèles de jeu

    # Parties créées par l'utilisateur
    created_games: Mapped[List["Game"]] = relationship(
        "Game",
        back_populates="creator",
        foreign_keys="Game.creator_id",
        cascade="all, delete-orphan",
        lazy="noload"
    )

    # Participations aux parties (CORRECTION: utilise player_id)
    game_participations: Mapped[List["GameParticipation"]] = relationship(
        "GameParticipation",
        back_populates="player",
        foreign_keys="GameParticipation.player_id",
        cascade="all, delete-orphan",
        lazy="noload"
    )

    # Tentatives dans les parties (CORRECTION: utilise player_id)
    game_attempts: Mapped[List["GameAttempt"]] = relationship(
        "GameAttempt",
        back_populates="player",
        foreign_keys="GameAttempt.player_id",
        cascade="all, delete-orphan",
        lazy="noload"
    )

    # === PROPRIÉTÉS CALCULÉES ===

    @property
    def win_rate(self) -> float:
        """Calcule le taux de victoire"""
        if self.total_games == 0:
            return 0.0
        return round((self.games_won / self.total_games) * 100, 2)

    @property
    def average_score(self) -> float:
        """Calcule le score moyen"""
        if self.total_games == 0:
            return 0.0
        return round(self.total_score / self.total_games, 2)

    @property
    def is_beginner(self) -> bool:
        """Vérifie si l'utilisateur est débutant"""
        return self.total_games < 10

    @property
    def is_expert(self) -> bool:
        """Vérifie si l'utilisateur est expert"""
        return self.rank in ['Diamond', 'Master', 'Grandmaster'] and self.total_games >= 100

    @property
    def is_online(self) -> bool:
        """Vérifie si l'utilisateur est en ligne (dernière connexion < 15 min)"""
        if not self.last_login:
            return False
        return (datetime.now(timezone.utc) - self.last_login) < timedelta(minutes=15)

    @property
    def account_age_days(self) -> int:
        """Âge du compte en jours"""
        return (datetime.now(timezone.utc) - self.created_at).days

    @property
    def is_locked(self) -> bool:
        """Vérifie si le compte est verrouillé"""
        if not self.locked_until:
            return False
        return datetime.now(timezone.utc) < self.locked_until

    @property
    def games_lost(self) -> int:
        """Nombre de parties perdues"""
        return max(0, self.total_games - self.games_won)

    # === MÉTHODES UTILITAIRES ===

    def update_last_login(self, ip_addr: Optional[str] = None) -> None:
        """Met à jour la dernière connexion"""
        self.last_login = datetime.now(timezone.utc)
        self.login_attempts = 0  # Reset après connexion réussie

        if ip_addr:
            try:
                # Validation de l'adresse IP
                validated_ip = ip_address(ip_addr)
                self.last_ip_address = str(validated_ip)
            except (AddressValueError, ValueError):
                # IP invalide, on l'ignore
                pass

    def increment_login_attempts(self) -> None:
        """Incrémente le compteur de tentatives de connexion"""
        self.login_attempts += 1

        # Verrouillage automatique après 5 tentatives
        if self.login_attempts >= 5:
            self.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)

    def unlock_account(self) -> None:
        """Déverrouille le compte"""
        self.locked_until = None
        self.login_attempts = 0

    def update_game_stats(self, won: bool, score: int) -> None:
        """Met à jour les statistiques de jeu"""
        self.total_games += 1
        self.total_score += score

        if won:
            self.games_won += 1

        # Mise à jour du meilleur score
        if self.best_score is None or score > self.best_score:
            self.best_score = score

        # Mise à jour automatique du rang
        self._update_rank()

    def add_quantum_points(self, points: int) -> None:
        """Ajoute des points quantiques"""
        self.quantum_points += points
        self._update_rank()

    def _update_rank(self) -> None:
        """Met à jour le rang basé sur les statistiques"""
        # Logique de calcul du rang basée sur les points et performances
        total_points = self.total_score + (self.quantum_points * 2)

        if total_points < 1000:
            self.rank = 'Bronze'
        elif total_points < 5000:
            self.rank = 'Silver'
        elif total_points < 15000:
            self.rank = 'Gold'
        elif total_points < 35000:
            self.rank = 'Platinum'
        elif total_points < 75000:
            self.rank = 'Diamond'
        elif total_points < 150000:
            self.rank = 'Master'
        else:
            self.rank = 'Grandmaster'

    def update_preferences(self, new_preferences: dict) -> None:
        """Met à jour les préférences utilisateur"""
        if self.preferences is None:
            self.preferences = {}

        # Merge profond des préférences
        def deep_merge(base: dict, update: dict) -> dict:
            for key, value in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value
            return base

        deep_merge(self.preferences, new_preferences)

    def get_preference(self, key: str, default=None):
        """Récupère une préférence spécifique"""
        if not self.preferences:
            return default

        # Support de la notation pointée (ex: "game_settings.sound_enabled")
        keys = key.split('.')
        value = self.preferences

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def can_play_game(self) -> bool:
        """Vérifie si l'utilisateur peut jouer"""
        return self.is_active and self.is_verified and not self.is_locked

    def get_current_games_count(self) -> int:
        """Retourne le nombre de parties actives"""
        if not self.game_participations:
            return 0

        active_statuses = ['waiting', 'ready', 'active']
        return len([
            p for p in self.game_participations
            if p.status in active_statuses
        ])

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', rank='{self.rank}')>"


# === CONTRAINTES DE TABLE ===

# Contraintes de validation
User.__table_args__ = (
    CheckConstraint('total_games >= 0', name='ck_users_total_games'),
    CheckConstraint('games_won >= 0 AND games_won <= total_games', name='ck_users_games_won'),
    CheckConstraint('total_score >= 0', name='ck_users_total_score'),
    CheckConstraint('quantum_points >= 0', name='ck_users_quantum_points'),
    CheckConstraint('login_attempts >= 0', name='ck_users_login_attempts'),
    CheckConstraint(
        "rank IN ('Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond', 'Master', 'Grandmaster')",
        name='ck_users_rank'
    ),

    # Index composites pour les performances
    Index('idx_users_active_verified', 'is_active', 'is_verified'),
    Index('idx_users_rank_score', 'rank', 'total_score'),
    Index('idx_users_created_stats', 'created_at', 'total_games'),
)


# === EXPORTS ===

__all__ = [
    "User"
]