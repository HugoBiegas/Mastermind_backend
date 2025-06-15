"""
Configuration de base de données pour Quantum Mastermind
SQLAlchemy 2.0.41 avec support async et PostgreSQL
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    create_engine,
    MetaData,
    text,
    event,
    DateTime
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from app.core.config import settings, is_test


# === BASE DÉCLARATIVE SQLAlchemy 2.0 ===

class Base(DeclarativeBase):
    """
    Classe de base pour tous les modèles SQLAlchemy 2.0
    Remplace declarative_base() qui est déprécié
    """

    # Métadonnées avec contraintes de nommage pour PostgreSQL
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s"
        }
    )

    # Colonnes communes à tous les modèles
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True
    )

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

    def __repr__(self) -> str:
        """Représentation string commune"""
        return f"<{self.__class__.__name__}(id={self.id})>"


# === MOTEUR DE BASE DE DONNÉES ===

# Moteur async principal
async_engine: Optional[AsyncEngine] = None

# Session factory async
AsyncSessionLocal: Optional[async_sessionmaker[AsyncSession]] = None

# Moteur sync pour les migrations Alembic
sync_engine = None


def create_async_database_engine() -> AsyncEngine:
    """
    Crée le moteur de base de données async

    Returns:
        Moteur SQLAlchemy async configuré
    """

    # Configuration pour les tests
    if is_test():
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
            poolclass=StaticPool,
            connect_args={
                "check_same_thread": False,
            },
        )
    else:
        # Configuration pour développement/production
        engine_kwargs = {
            "echo": settings.DEBUG,
            "pool_size": 20,
            "max_overflow": 30,
            "pool_timeout": 30,
            "pool_recycle": 3600,
            "pool_pre_ping": True,
        }

        # Ajout des options spécifiques à asyncpg
        connect_args = {
            "server_settings": {
                "application_name": settings.PROJECT_NAME,
                "jit": "off"  # Optimisation pour PostgreSQL
            }
        }

        engine = create_async_engine(
            settings.DATABASE_URL,
            connect_args=connect_args,
            **engine_kwargs
        )

    return engine


def create_sync_database_engine():
    """
    Crée le moteur de base de données synchrone pour Alembic

    Returns:
        Moteur SQLAlchemy synchrone
    """
    # URL synchrone pour Alembic (remplace asyncpg par psycopg2)
    sync_url = settings.DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql://"
    )

    return create_engine(
        sync_url,
        echo=settings.DEBUG,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600
    )


async def init_db() -> None:
    """
    Initialise la base de données et crée les connexions

    Appelé au démarrage de l'application
    """
    global async_engine, AsyncSessionLocal, sync_engine

    try:
        # Création du moteur async
        async_engine = create_async_database_engine()

        # Création de la session factory
        AsyncSessionLocal = async_sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )

        # Moteur sync pour Alembic
        if not is_test():
            sync_engine = create_sync_database_engine()

        # Configuration des événements après création du moteur
        if async_engine and settings.DEBUG:
            setup_database_events(async_engine)

        # Test de connexion
        async with async_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        print("✅ Base de données initialisée avec succès")

    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la base de données: {e}")
        raise


async def close_db() -> None:
    """
    Ferme les connexions à la base de données

    Appelé à l'arrêt de l'application
    """
    global async_engine, sync_engine

    try:
        if async_engine:
            await async_engine.dispose()
            print("✅ Connexions async fermées")

        if sync_engine:
            sync_engine.dispose()
            print("✅ Connexions sync fermées")

    except Exception as e:
        print(f"❌ Erreur lors de la fermeture de la base de données: {e}")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Générateur de session de base de données pour FastAPI

    Yields:
        Session de base de données async

    Usage:
        @app.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    if not AsyncSessionLocal:
        raise RuntimeError("Base de données non initialisée. Appelez init_db() d'abord.")

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context():
    """
    Context manager pour obtenir une session de base de données

    Usage:
        async with get_db_context() as db:
            result = await db.execute(...)
    """
    if not AsyncSessionLocal:
        raise RuntimeError("Base de données non initialisée")

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# === UTILITAIRES DE PAGINATION ===

class PaginationParams:
    """Paramètres de pagination standardisés"""

    def __init__(
        self,
        page: int = 1,
        per_page: int = 20,
        max_per_page: int = 100
    ):
        self.page = max(1, page)
        self.per_page = min(max(1, per_page), max_per_page)

    @property
    def offset(self) -> int:
        """Calcule l'offset pour la pagination"""
        return (self.page - 1) * self.per_page

    @property
    def limit(self) -> int:
        """Limite d'éléments par page"""
        return self.per_page

    def paginate_query(self, query):
        """Applique la pagination à une requête SQLAlchemy"""
        return query.offset(self.offset).limit(self.limit)


class PaginationResult:
    """Résultat de pagination avec métadonnées"""

    def __init__(
        self,
        items: list,
        total: int,
        page: int,
        per_page: int
    ):
        self.items = items
        self.total = total
        self.page = page
        self.per_page = per_page

    @property
    def pages(self) -> int:
        """Nombre total de pages"""
        return (self.total + self.per_page - 1) // self.per_page

    @property
    def has_prev(self) -> bool:
        """True s'il y a une page précédente"""
        return self.page > 1

    @property
    def has_next(self) -> bool:
        """True s'il y a une page suivante"""
        return self.page < self.pages

    @property
    def prev_page(self) -> Optional[int]:
        """Numéro de la page précédente"""
        return self.page - 1 if self.has_prev else None

    @property
    def next_page(self) -> Optional[int]:
        """Numéro de la page suivante"""
        return self.page + 1 if self.has_next else None


# === ÉVÉNEMENTS SQLAlchemy ===

def setup_database_events(engine: AsyncEngine) -> None:
    """
    Configure les événements SQLAlchemy après création du moteur

    Args:
        engine: Moteur de base de données créé
    """
    if not settings.DEBUG:
        return

    @event.listens_for(engine.sync_engine, "before_cursor_execute", retval=True)
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Événement avant exécution SQL pour debug"""
        print(f"🔍 Exécution SQL: {statement[:100]}...")
        return statement, parameters

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Événement après exécution SQL pour monitoring"""
        # Note: Les événements de timing ne sont pas disponibles sur async engines
        pass


# === FONCTIONS UTILITAIRES ===

async def create_tables():
    """
    Crée toutes les tables de la base de données

    Utilisé pour les tests ou l'initialisation
    """
    if not async_engine:
        raise RuntimeError("Moteur de base de données non initialisé")

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables():
    """
    Supprime toutes les tables de la base de données

    ⚠️ Utilisé uniquement pour les tests
    """
    if not async_engine:
        raise RuntimeError("Moteur de base de données non initialisé")

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def check_database_connection() -> bool:
    """
    Vérifie la connexion à la base de données

    Returns:
        True si la connexion fonctionne
    """
    try:
        if not async_engine:
            return False

        async with async_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            return True
    except Exception:
        return False


async def get_database_info() -> Dict[str, Any]:
    """
    Récupère les informations sur la base de données

    Returns:
        Dictionnaire avec les métadonnées
    """
    if not async_engine:
        return {"status": "not_initialized"}

    try:
        async with async_engine.begin() as conn:
            # Version PostgreSQL
            version_result = await conn.execute(text("SELECT version()"))
            version = version_result.scalar()

            # Nombre de connexions actives
            connections_result = await conn.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            )
            active_connections = connections_result.scalar()

            return {
                "status": "connected",
                "version": version,
                "active_connections": active_connections,
                "pool_size": async_engine.pool.size(),
                "checked_in": async_engine.pool.checkedin(),
                "checked_out": async_engine.pool.checkedout(),
                "overflow": async_engine.pool.overflow(),
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# === EXPORTS ===

__all__ = [
    "Base",
    "async_engine",
    "AsyncSessionLocal",
    "sync_engine",
    "init_db",
    "close_db",
    "get_db",
    "get_db_context",
    "PaginationParams",
    "PaginationResult",
    "create_tables",
    "drop_tables",
    "check_database_connection",
    "get_database_info",
    "setup_database_events"
]