"""
Modèle utilisateur pour Quantum Mastermind
SQLAlchemy 2.0.41 avec typing moderne et async support
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

    # Rang dérivé du score et des performances
    rank: Mapped[str] = mapped_column(
        String(20),
        default="Bronze",
        nullable=False,
        index=True
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

    # === MÉTADONNÉES DE SÉCURITÉ ===

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
        INET,
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

    # Tentatives dans les jeux
    game_attempts: Mapped[List["GameAttempt"]] = relationship(
        "GameAttempt",
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    # === CONTRAINTES ===

    __table_args__ = (
        # Index composites pour les requêtes fréquentes
        Index("ix_users_active_verified", "is_active", "is_verified"),
        Index("ix_users_created_score", "created_at", "total_score"),
        Index("ix_users_last_login", "last_login"),
        Index("ix_users_rank_score", "rank", "total_score"),

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

    # === PROPRIÉTÉS CALCULÉES ===

    @property
    def win_rate(self) -> float:
        """Taux de victoire en pourcentage"""
        if self.total_games == 0:
            return 0.0
        return (self.games_won / self.total_games) * 100

    @property
    def is_locked(self) -> bool:
        """Vérifie si le compte est verrouillé"""
        if not self.locked_until:
            return False
        return datetime.now(timezone.utc) < self.locked_until

    @property
    def is_online(self) -> bool:
        """Vérifie si l'utilisateur est considéré comme en ligne"""
        if not self.last_login:
            return False
        # Considéré en ligne si dernière connexion < 15 minutes
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        return self.last_login > cutoff

    @property
    def level(self) -> int:
        """Calcule le niveau basé sur les points quantiques"""
        if self.quantum_points < 100:
            return 1
        return min(100, int(self.quantum_points / 100) + 1)

    @property
    def display_name(self) -> str:
        """Nom d'affichage (nom complet ou username)"""
        return self.full_name or self.username

    # === MÉTHODES D'INSTANCE ===

    def update_score(self, points: int) -> None:
        """
        Met à jour le score total et le meilleur score

        Args:
            points: Points à ajouter
        """
        self.total_score = max(0, self.total_score + points)
        if points > self.best_score:
            self.best_score = points

    def update_rank(self) -> None:
        """Met à jour le rang basé sur le score total"""
        if self.total_score < 100:
            self.rank = "Bronze"
        elif self.total_score < 500:
            self.rank = "Silver"
        elif self.total_score < 1000:
            self.rank = "Gold"
        elif self.total_score < 2500:
            self.rank = "Platinum"
        elif self.total_score < 5000:
            self.rank = "Diamond"
        else:
            self.rank = "Master"

    def record_game_result(self, won: bool, score: int = 0) -> None:
        """
        Enregistre le résultat d'une partie

        Args:
            won: True si le joueur a gagné
            score: Score obtenu dans la partie
        """
        self.total_games += 1
        if won:
            self.games_won += 1

        if score > 0:
            self.update_score(score)

        self.update_rank()
        self.updated_at = datetime.now(timezone.utc)

    def add_quantum_points(self, points: int) -> None:
        """
        Ajoute des points quantiques

        Args:
            points: Points quantiques à ajouter
        """
        self.quantum_points = max(0, self.quantum_points + points)
        self.updated_at = datetime.now(timezone.utc)

    def reset_login_attempts(self) -> None:
        """Remet à zéro les tentatives de connexion"""
        self.login_attempts = 0
        self.locked_until = None

    def lock_account(self, duration_minutes: int = 15) -> None:
        """
        Verrouille le compte pour une durée donnée

        Args:
            duration_minutes: Durée de verrouillage en minutes
        """
        self.locked_until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)

    def update_preferences(self, new_preferences: dict) -> None:
        """
        Met à jour les préférences utilisateur

        Args:
            new_preferences: Nouvelles préférences
        """
        if self.preferences is None:
            self.preferences = {}

        self.preferences.update(new_preferences)
        self.updated_at = datetime.now(timezone.utc)

    def update_settings(self, new_settings: dict) -> None:
        """
        Met à jour les paramètres utilisateur

        Args:
            new_settings: Nouveaux paramètres
        """
        if self.settings is None:
            self.settings = {
                "theme": "dark",
                "language": "fr",
                "notifications": {},
                "privacy": {}
            }

        # Fusion récursive des paramètres
        for key, value in new_settings.items():
            if isinstance(value, dict) and key in self.settings:
                self.settings[key].update(value)
            else:
                self.settings[key] = value

        self.updated_at = datetime.now(timezone.utc)

    def verify_email(self) -> None:
        """Marque l'email comme vérifié"""
        self.is_verified = True
        self.email_verified_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def deactivate(self, reason: Optional[str] = None) -> None:
        """
        Désactive le compte utilisateur

        Args:
            reason: Raison de la désactivation
        """
        self.is_active = False
        if reason and self.settings:
            self.settings['deactivation_reason'] = reason
        self.updated_at = datetime.now(timezone.utc)

    def activate(self) -> None:
        """Réactive le compte utilisateur"""
        self.is_active = True
        self.reset_login_attempts()
        if self.settings and 'deactivation_reason' in self.settings:
            del self.settings['deactivation_reason']
        self.updated_at = datetime.now(timezone.utc)

    # === MÉTHODES DE VALIDATION ===

    def can_play(self) -> bool:
        """Vérifie si l'utilisateur peut jouer"""
        return self.is_active and not self.is_locked

    def can_create_game(self) -> bool:
        """Vérifie si l'utilisateur peut créer une partie"""
        return self.can_play() and self.is_verified

    def can_use_quantum_features(self) -> bool:
        """Vérifie si l'utilisateur peut utiliser les fonctionnalités quantiques"""
        return self.can_play() and self.level >= 3  # Niveau minimum requis

    # === REPRÉSENTATION STRING ===

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', rank='{self.rank}')>"

    def __str__(self) -> str:
        return self.display_name

    def increment_login_attempts(self):
        pass

    def update_last_login(self, ip: str | None) -> None:
        """
        Met à jour la date et l'adresse IP de dernière connexion.

        Args:
            ip (str | None): Adresse IP au format string (IPv4 ou IPv6)
        """
        self.last_login = datetime.now(timezone.utc)
        if ip:
            try:
                self.last_ip_address = str(ip_address(ip))
            except AddressValueError:
                self.last_ip_address = None



# === ÉVÉNEMENTS SQLAlchemy ===

from sqlalchemy import event

@event.listens_for(User, 'before_insert')
def user_before_insert(mapper, connection, target):
    """Traitement avant insertion d'un utilisateur"""
    # Normalisation des données
    if target.username:
        target.username = target.username.lower().strip()
    if target.email:
        target.email = target.email.lower().strip()

    # Initialisation des valeurs par défaut
    if target.preferences is None:
        target.preferences = {}
    if target.settings is None:
        target.settings = {
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


@event.listens_for(User, 'before_update')
def user_before_update(mapper, connection, target):
    """Traitement avant mise à jour d'un utilisateur"""
    # Mise à jour automatique du timestamp
    target.updated_at = datetime.now(timezone.utc)

    # Mise à jour du rang si le score a changé
    if target.total_score != getattr(target, '_sa_instance_state').committed_state.get('total_score', 0):
        target.update_rank()