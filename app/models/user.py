"""
Modèle User pour Quantum Mastermind
Gestion complète des utilisateurs avec statistiques et sécurité
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import Boolean, Float, Integer, String, DateTime, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import TimestampedModel


class User(TimestampedModel):
    """
    Modèle utilisateur avec statistiques de jeu et sécurité renforcée
    """
    __tablename__ = "users"

    # === INFORMATIONS DE BASE ===
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Nom d'utilisateur unique"
    )

    email: Mapped[str] = mapped_column(
        String(254),
        unique=True,
        nullable=False,
        index=True,
        comment="Adresse email unique"
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hash du mot de passe (bcrypt)"
    )

    # === ÉTAT DU COMPTE ===
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Compte actif"
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Email vérifié"
    )

    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Administrateur"
    )

    # === STATISTIQUES DE JEU ===
    total_games: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Nombre total de parties jouées"
    )

    wins: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Nombre de victoires"
    )

    best_time: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Meilleur temps en secondes"
    )

    average_time: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Temps moyen en secondes"
    )

    quantum_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Score quantique accumulé"
    )

    # === CONNEXIONS ET ACTIVITÉ ===
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Dernière connexion"
    )

    login_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Nombre de connexions"
    )

    last_ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
        comment="Dernière adresse IP"
    )

    # === PRÉFÉRENCES UTILISATEUR ===
    preferences: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="Préférences utilisateur JSON"
    )

    # === SÉCURITÉ ===
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Tentatives de connexion échouées"
    )

    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Verrouillage temporaire jusqu'à"
    )

    password_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Dernière modification du mot de passe"
    )

    # === TOKENS DE SÉCURITÉ ===
    email_verification_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Token de vérification email"
    )

    password_reset_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Token de réinitialisation mot de passe"
    )

    password_reset_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Expiration du token de reset"
    )

    # === RELATIONS ===
    # Les relations seront définies dans les autres modèles pour éviter les imports circulaires

    # === CONTRAINTES ===
    __table_args__ = (
        CheckConstraint('total_games >= 0', name='check_total_games_positive'),
        CheckConstraint('wins >= 0', name='check_wins_positive'),
        CheckConstraint('wins <= total_games', name='check_wins_not_greater_than_total'),
        CheckConstraint('best_time > 0 OR best_time IS NULL', name='check_best_time_positive'),
        CheckConstraint('average_time > 0 OR average_time IS NULL', name='check_average_time_positive'),
        CheckConstraint('quantum_score >= 0', name='check_quantum_score_positive'),
        CheckConstraint('login_count >= 0', name='check_login_count_positive'),
        CheckConstraint('failed_login_attempts >= 0', name='check_failed_attempts_positive'),
        Index('idx_users_username_active', 'username', 'is_active'),
        Index('idx_users_email_active', 'email', 'is_active'),
        Index('idx_users_quantum_score', 'quantum_score', postgresql_using='btree'),
        Index('idx_users_last_login', 'last_login', postgresql_using='btree'),
    )

    # === MÉTHODES DE PROPRIÉTÉS CALCULÉES ===
    @property
    def win_rate(self) -> float:
        """Calcule le taux de victoire"""
        if self.total_games == 0:
            return 0.0
        return (self.wins / self.total_games) * 100

    @property
    def full_name(self) -> str:
        """Nom complet pour affichage"""
        return self.username  # Pas de prénom/nom dans ce modèle simple

    @property
    def is_locked(self) -> bool:
        """Vérifie si le compte est verrouillé"""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until

    @property
    def is_email_verified(self) -> bool:
        """Vérifie si l'email est vérifié"""
        return self.is_verified

    @property
    def games_this_month(self) -> int:
        """Nombre de parties ce mois (à calculer avec une requête)"""
        # Cette propriété nécessite une requête à la base,
        # elle sera calculée dans le service
        return 0

    # === MÉTHODES DE SÉCURITÉ ===
    def increment_failed_login(self) -> None:
        """Incrémente les tentatives de connexion échouées"""
        self.failed_login_attempts += 1

        # Verrouillage temporaire après 5 tentatives
        if self.failed_login_attempts >= 5:
            self.locked_until = datetime.utcnow() + timedelta(minutes=15)

    def reset_failed_login(self) -> None:
        """Remet à zéro les tentatives échouées"""
        self.failed_login_attempts = 0
        self.locked_until = None

    def record_login(self, ip_address: str) -> None:
        """Enregistre une connexion réussie"""
        self.last_login = datetime.utcnow()
        self.login_count += 1
        self.last_ip_address = ip_address
        self.reset_failed_login()

    def lock_account(self, duration_minutes: int = 60) -> None:
        """Verrouille le compte temporairement"""
        from datetime import timedelta
        self.locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)

    def unlock_account(self) -> None:
        """Déverrouille le compte"""
        self.locked_until = None
        self.failed_login_attempts = 0

    # === MÉTHODES DE GESTION DES PRÉFÉRENCES ===
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Récupère une préférence utilisateur"""
        if not self.preferences:
            return default
        return self.preferences.get(key, default)

    def set_preference(self, key: str, value: Any) -> None:
        """Définit une préférence utilisateur"""
        if not self.preferences:
            self.preferences = {}
        self.preferences[key] = value

    def remove_preference(self, key: str) -> None:
        """Supprime une préférence"""
        if self.preferences and key in self.preferences:
            del self.preferences[key]

    # === MÉTHODES DE STATISTIQUES ===
    def update_game_stats(
            self,
            won: bool,
            game_time: float,
            quantum_points: int = 0
    ) -> None:
        """Met à jour les statistiques après une partie"""
        self.total_games += 1

        if won:
            self.wins += 1

        # Mise à jour du meilleur temps
        if self.best_time is None or game_time < self.best_time:
            self.best_time = game_time

        # Mise à jour du temps moyen
        if self.average_time is None:
            self.average_time = game_time
        else:
            # Moyenne pondérée
            total_time = self.average_time * (self.total_games - 1) + game_time
            self.average_time = total_time / self.total_games

        # Mise à jour du score quantique
        self.quantum_score += quantum_points

    def reset_stats(self) -> None:
        """Remet à zéro les statistiques (admin uniquement)"""
        self.total_games = 0
        self.wins = 0
        self.best_time = None
        self.average_time = None
        self.quantum_score = 0

    # === MÉTHODES DE VALIDATION ===
    def validate(self) -> Dict[str, List[str]]:
        """Valide les données du modèle"""
        errors = {}

        # Validation username
        if not self.username or len(self.username) < 3:
            errors.setdefault('username', []).append('Minimum 3 caractères requis')

        if len(self.username) > 50:
            errors.setdefault('username', []).append('Maximum 50 caractères')

        # Validation email
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, self.email):
            errors.setdefault('email', []).append('Format email invalide')

        # Validation des statistiques
        if self.wins > self.total_games:
            errors.setdefault('wins', []).append('Victoires > parties totales')

        return errors

    # === MÉTHODES D'EXPORT ===
    def to_public_dict(self) -> Dict[str, Any]:
        """Exporte les données publiques (sans infos sensibles)"""
        return {
            'id': str(self.id),
            'username': self.username,
            'total_games': self.total_games,
            'wins': self.wins,
            'win_rate': self.win_rate,
            'best_time': self.best_time,
            'quantum_score': self.quantum_score,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'is_verified': self.is_verified
        }

    def to_profile_dict(self) -> Dict[str, Any]:
        """Exporte le profil complet (pour le propriétaire)"""
        public_data = self.to_public_dict()
        public_data.update({
            'email': self.email,
            'is_active': self.is_active,
            'login_count': self.login_count,
            'average_time': self.average_time,
            'preferences': self.preferences or {},
            'updated_at': self.updated_at.isoformat()
        })
        return public_data

    def __str__(self) -> str:
        """Représentation string"""
        return f"User(username='{self.username}', email='{self.email}')"