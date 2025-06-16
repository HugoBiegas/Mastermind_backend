"""
Modèle de base pour tous les modèles SQLAlchemy
Fonctionnalités communes : UUID, timestamps, méthodes utilitaires
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import expression
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import DateTime as DateTimeType

from app.core.database import Base


# === UTILITAIRES SQLALCHEMY ===
class utcnow(expression.FunctionElement):
    """Fonction UTC NOW pour PostgreSQL"""
    type = DateTimeType()
    inherit_cache = True


@compiles(utcnow, 'postgresql')
def pg_utcnow(element, compiler, **kw):
    return "TIMEZONE('utc', CURRENT_TIMESTAMP)"


@compiles(utcnow, 'sqlite')
def sqlite_utcnow(element, compiler, **kw):
    return "CURRENT_TIMESTAMP"


# === MODÈLE DE BASE ===
class BaseModel(Base):
    """
    Modèle de base abstrait avec fonctionnalités communes
    - UUID comme clé primaire
    - Timestamps automatiques
    - Méthodes utilitaires pour sérialisation
    """
    __abstract__ = True

    # Clé primaire UUID
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
        comment="Identifiant unique UUID"
    )

    # Timestamps automatiques
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=utcnow(),
        nullable=False,
        comment="Date de création"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=utcnow(),
        onupdate=utcnow(),
        nullable=False,
        comment="Date de dernière modification"
    )

    def __repr__(self) -> str:
        """Représentation string du modèle"""
        class_name = self.__class__.__name__
        return f"<{class_name}(id={self.id})>"

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Convertit le modèle en dictionnaire

        Args:
            exclude: Liste des champs à exclure

        Returns:
            Dictionnaire des attributs du modèle
        """
        exclude = exclude or []
        result = {}

        for column in self.__table__.columns:
            column_name = column.name
            if column_name not in exclude:
                value = getattr(self, column_name)

                # Conversion des types spéciaux
                if isinstance(value, datetime):
                    result[column_name] = value.isoformat()
                elif isinstance(value, UUID):
                    result[column_name] = str(value)
                else:
                    result[column_name] = value

        return result

    def update_from_dict(self, data: Dict[str, Any], exclude: Optional[List[str]] = None) -> None:
        """
        Met à jour le modèle à partir d'un dictionnaire

        Args:
            data: Dictionnaire des nouvelles valeurs
            exclude: Liste des champs à exclure de la mise à jour
        """
        exclude = exclude or ['id', 'created_at']

        for key, value in data.items():
            if key not in exclude and hasattr(self, key):
                setattr(self, key, value)

    @classmethod
    def get_table_name(cls) -> str:
        """Retourne le nom de la table"""
        return cls.__tablename__

    @classmethod
    def get_columns(cls) -> List[str]:
        """Retourne la liste des colonnes de la table"""
        return [column.name for column in cls.__table__.columns]

    def is_new(self) -> bool:
        """Vérifie si l'objet est nouveau (pas encore en base)"""
        return self.id is None or not hasattr(self, '_sa_instance_state')

    def get_primary_key(self) -> UUID:
        """Retourne la clé primaire"""
        return self.id

    def soft_delete(self) -> None:
        """Suppression logique (si le modèle l'implémente)"""
        if hasattr(self, 'is_deleted'):
            self.is_deleted = True
            self.deleted_at = datetime.utcnow()

    def validate(self) -> Dict[str, List[str]]:
        """
        Valide le modèle et retourne les erreurs
        À surcharger dans les modèles enfants

        Returns:
            Dictionnaire des erreurs par champ
        """
        return {}

    def __eq__(self, other) -> bool:
        """Comparaison basée sur l'ID"""
        if not isinstance(other, self.__class__):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash basé sur l'ID"""
        return hash(self.id) if self.id else hash(id(self))


# === MIXIN POUR SUPPRESSION LOGIQUE ===
class SoftDeleteMixin:
    """Mixin pour la suppression logique"""

    is_deleted: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        index=True,
        comment="Marqueur de suppression logique"
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date de suppression logique"
    )

    def soft_delete(self) -> None:
        """Marque l'objet comme supprimé"""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()

    def restore(self) -> None:
        """Restaure un objet supprimé logiquement"""
        self.is_deleted = False
        self.deleted_at = None

    @classmethod
    def active_only(cls, query):
        """Filtre pour ne récupérer que les objets non supprimés"""
        return query.filter(cls.is_deleted == False)


# === MIXIN POUR AUDIT ===
class AuditMixin:
    """Mixin pour l'audit des modifications"""

    created_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="Utilisateur créateur"
    )

    updated_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        comment="Dernier utilisateur modificateur"
    )

    def set_created_by(self, user_id: UUID) -> None:
        """Définit l'utilisateur créateur"""
        self.created_by = user_id

    def set_updated_by(self, user_id: UUID) -> None:
        """Définit l'utilisateur modificateur"""
        self.updated_by = user_id

class BaseModelWithoutTimestamps(Base):
    """
    Modèle de base abstrait SANS timestamps automatiques
    Pour les tables comme game_participations
    """
    __abstract__ = True

    # Clé primaire UUID seulement
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
        comment="Identifiant unique UUID"
    )

    def __repr__(self) -> str:
        """Représentation string du modèle"""
        class_name = self.__class__.__name__
        return f"<{class_name}(id={self.id})>"

    def to_dict(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convertit le modèle en dictionnaire"""
        exclude = exclude or []
        result = {}

        for column in self.__table__.columns:
            column_name = column.name
            if column_name not in exclude:
                value = getattr(self, column_name)

                # Conversion des types spéciaux
                if isinstance(value, datetime):
                    result[column_name] = value.isoformat()
                elif isinstance(value, UUID):
                    result[column_name] = str(value)
                else:
                    result[column_name] = value

        return result


class BaseModelWithCreatedAt(Base):
    """Modèle de base avec SEULEMENT created_at pour game_attempts"""
    __abstract__ = True

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )


# === MIXIN POUR MÉTADONNÉES JSON ===
class MetadataMixin:
    """Mixin pour stocker des métadonnées JSON flexibles - SQLAlchemy 2.0 compatible"""

    from sqlalchemy.dialects.postgresql import JSONB

    # CORRECTION CRITIQUE: Utiliser directement JSONB (projet PostgreSQL)
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,  # ✅ Correction : utilisation directe de JSONB (pas de détection dynamique)
        nullable=True,
        default=dict,
        comment="Métadonnées JSON flexibles"
    )

    def set_metadata(self, key: str, value: Any) -> None:
        """Définit une métadonnée"""
        if self.metadata is None:
            self.metadata = {}
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Récupère une métadonnée"""
        if self.metadata is None:
            return default
        return self.metadata.get(key, default)

    def remove_metadata(self, key: str) -> None:
        """Supprime une métadonnée"""
        if self.metadata and key in self.metadata:
            del self.metadata[key]


# === MODÈLE DE BASE COMPLET ===
class TimestampedModel(BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin):
    """
    Modèle de base complet avec toutes les fonctionnalités :
    - UUID + timestamps
    - Suppression logique
    - Audit
    - Métadonnées JSON
    """
    __abstract__ = True

    def get_audit_info(self) -> Dict[str, Any]:
        """Retourne les informations d'audit"""
        return {
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": str(self.created_by) if self.created_by else None,
            "updated_by": str(self.updated_by) if self.updated_by else None,
            "is_deleted": self.is_deleted,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None
        }

    def to_dict_with_audit(self, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convertit en dictionnaire avec les infos d'audit"""
        result = self.to_dict(exclude=exclude)
        result.update(self.get_audit_info())
        return result