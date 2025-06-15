"""
Modèle utilisateur pour Quantum Mastermind
SQLAlchemy 2.0.41 avec typing moderne et async support
"""
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, DateTime, String, Text, Integer,
    func, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

# Import conditionnel pour éviter les imports circulaires
if TYPE_CHECKING:
    from app.models.game import Game, GameParticipation
    from app.models.audit import AuditLog


class User(Base):
    """
    Modèle utilisateur principal avec support SQLAlchemy 2.0
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

    email: Mapped[str] = mapped_column(
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

    # Utilisation de JSONB pour PostgreSQL, JSON pour autres DB
    preferences: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=lambda: {}
    )

    settings: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default=lambda: {
            "theme": "dark",
            "language": "fr",
            "notifications": {
                "email": True,
                "push": True,
                "game_invites": True,
                "tournaments": True
            },
            "privacy": {
                "show_stats": True,
                "show_online_status": True
            }
        }
    )

    # === STATISTIQUES DE JEU ===

    total_games: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    games_won: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    total_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    best_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    quantum_points: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Points gagnés en utilisant les fonctionnalités quantiques"
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

    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )

    email_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # === MÉTADONNÉES DE CONNEXION ===

    login_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    last_ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # Support IPv6
        nullable=True
    )

    # === RELATIONS ===

    # Jeux créés par l'utilisateur
    created_games: Mapped[List["Game"]] = relationship(
        "Game",
        back_populates="creator",
        foreign_keys="Game.creator_id",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    # Participations aux jeux
    game_participations: Mapped[List["GameParticipation"]] = relationship(
        "GameParticipation",
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    # Logs d'audit
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    # === CONTRAINTES ===

    __table_args__ = (
        # Index composites pour les requêtes fréquentes
        Index("ix_users_active_verified", "is_active", "is_verified"),
        Index("ix_users_created_score", "created_at", "total_score"),
        Index("ix_users_last_login", "last_login"),

        # Contraintes de validation
        CheckConstraint(
            "char_length(username) >= 3",
            name="ck_username_min_length"
        ),
        CheckConstraint(
            "char_length(email) >= 5",
            name="ck_email_min_length"
        ),
        CheckConstraint(
            "total_games >= 0",
            name="ck_total_games_positive"
        ),
        CheckConstraint(
            "games_won >= 0",
            name="ck_games_won_positive"
        ),
        CheckConstraint(
            "games_won <= total_games",
            name="ck_games_won_lte_total"
        ),
        CheckConstraint(
            "total_score >= 0",
            name="ck_total_score_positive"
        ),
        CheckConstraint(
            "best_score >= 0",
            name="ck_best_score_positive"
        ),
        CheckConstraint(
            "quantum_points >= 0",
            name="ck_quantum_points_positive"
        ),
        CheckConstraint(
            "login_attempts >= 0",
            name="ck_login_attempts_positive"
        ),
    )

    # === MÉTHODES ===

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"

    def __str__(self) -> str:
        return self.username

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
    def is_locked(self) -> bool:
        """Vérifie si le compte est verrouillé"""
        if not self.locked_until:
            return False
        return datetime.now(timezone.utc) < self.locked_until

    @property
    def display_name(self) -> str:
        """Retourne le nom d'affichage préféré"""
        return self.full_name or self.username

    @property
    def rank(self) -> str:
        """Calcule le rang basé sur les points quantiques"""
        if self.quantum_points < 100:
            return "Novice"
        elif self.quantum_points < 500:
            return "Apprenti"
        elif self.quantum_points < 1000:
            return "Quantique"
        elif self.quantum_points < 2500:
            return "Expert"
        elif self.quantum_points < 5000:
            return "Maître"
        else:
            return "Grand Maître"

    def update_stats(self, game_won: bool, score: int, quantum_used: bool) -> None:
        """
        Met à jour les statistiques après une partie

        Args:
            game_won: True si la partie a été gagnée
            score: Score obtenu
            quantum_used: True si des fonctionnalités quantiques ont été utilisées
        """
        self.total_games += 1
        if game_won:
            self.games_won += 1

        self.total_score += score
        if score > self.best_score:
            self.best_score = score

        if quantum_used:
            # Bonus pour l'utilisation de fonctionnalités quantiques
            quantum_bonus = score // 10
            self.quantum_points += quantum_bonus

    def reset_login_attempts(self) -> None:
        """Remet à zéro les tentatives de connexion"""
        self.login_attempts = 0
        self.locked_until = None

    def increment_login_attempts(self) -> None:
        """Incrémente les tentatives de connexion et verrouille si nécessaire"""
        self.login_attempts += 1

        # Verrouillage après 5 tentatives
        if self.login_attempts >= 5:
            from datetime import timedelta
            self.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)

    def update_last_login(self, ip_address: Optional[str] = None) -> None:
        """Met à jour la dernière connexion"""
        self.last_login = datetime.now(timezone.utc)
        if ip_address:
            self.last_ip_address = ip_address
        self.reset_login_attempts()

    def verify_email(self) -> None:
        """Marque l'email comme vérifié"""
        self.is_verified = True
        self.email_verified_at = datetime.now(timezone.utc)

    def get_preference(self, key: str, default=None):
        """Récupère une préférence utilisateur"""
        if not self.preferences:
            return default
        return self.preferences.get(key, default)

    def set_preference(self, key: str, value) -> None:
        """Définit une préférence utilisateur"""
        if not self.preferences:
            self.preferences = {}
        self.preferences[key] = value

    def get_setting(self, key: str, default=None):
        """Récupère un paramètre utilisateur avec support de clés imbriquées"""
        if not self.settings:
            return default

        # Support des clés imbriquées comme "notifications.email"
        keys = key.split('.')
        current = self.settings

        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default

        return current

    def set_setting(self, key: str, value) -> None:
        """Définit un paramètre utilisateur avec support de clés imbriquées"""
        if not self.settings:
            self.settings = {}

        # Support des clés imbriquées
        keys = key.split('.')
        current = self.settings

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """
        Convertit l'utilisateur en dictionnaire

        Args:
            include_sensitive: Inclure les données sensibles

        Returns:
            Dictionnaire représentant l'utilisateur
        """
        data = {
            "id": str(self.id),
            "username": self.username,
            "email": self.email if include_sensitive else self.email[:3] + "***",
            "full_name": self.full_name,
            "avatar_url": self.avatar_url,
            "bio": self.bio,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "is_superuser": self.is_superuser if include_sensitive else None,
            "total_games": self.total_games,
            "games_won": self.games_won,
            "win_rate": self.win_rate,
            "total_score": self.total_score,
            "best_score": self.best_score,
            "average_score": self.average_score,
            "quantum_points": self.quantum_points,
            "rank": self.rank,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "settings": self.settings,
            "preferences": self.preferences
        }

        # Supprimer les valeurs None si pas sensible
        if not include_sensitive:
            data = {k: v for k, v in data.items() if v is not None}

        return data

    @classmethod
    def create_user(
        cls,
        username: str,
        email: str,
        hashed_password: str,
        full_name: Optional[str] = None,
        is_verified: bool = False
    ) -> "User":
        """
        Factory method pour créer un utilisateur

        Args:
            username: Nom d'utilisateur
            email: Adresse email
            hashed_password: Mot de passe hashé
            full_name: Nom complet (optionnel)
            is_verified: Email vérifié (défaut: False)

        Returns:
            Instance User créée
        """
        return cls(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            is_verified=is_verified
        )