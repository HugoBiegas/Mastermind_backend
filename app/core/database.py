"""
Configuration de la base de données pour Quantum Mastermind
SQLAlchemy 2.0 avec support async et optimisations
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from .config import settings

# Configuration du logger
logger = logging.getLogger(__name__)


# === BASE DECLARATIVE ===
class Base(DeclarativeBase):
    """Base déclarative pour tous les modèles SQLAlchemy"""
    pass


# === MOTEUR DE BASE DE DONNÉES ===
# Moteur asynchrone pour l'application principale
async_engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=settings.DEBUG,  # Log SQL en mode debug
    future=True,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Vérifie la connexion avant utilisation
    pool_recycle=3600,  # Renouvelle les connexions toutes les heures
    connect_args={
        "server_settings": {
            "application_name": "quantum_mastermind",
        }
    }
)

# Moteur synchrone pour les migrations Alembic
sync_engine = create_engine(
    str(settings.DATABASE_URL).replace("+asyncpg", ""),
    echo=settings.DEBUG,
    future=True,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)

# Session factory asynchrone
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
    autocommit=False
)


# === GESTIONNAIRE DE SESSIONS ===
class DatabaseManager:
    """Gestionnaire centralisé des sessions de base de données"""

    def __init__(self):
        self.async_engine = async_engine
        self.session_factory = AsyncSessionLocal

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager pour les sessions de base de données"""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def get_session_dependency(self) -> AsyncGenerator[AsyncSession, None]:
        """Dépendance FastAPI pour l'injection de session"""
        async with self.get_session() as session:
            yield session

    async def health_check(self) -> bool:
        """Vérifie la santé de la connexion à la base de données"""
        try:
            async with self.get_session() as session:
                result = await session.execute("SELECT 1")
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def close(self):
        """Ferme toutes les connexions"""
        await self.async_engine.dispose()


# === EVENTS SQLALCHEMY ===
@event.listens_for(async_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Configure les pragmas pour SQLite (si utilisé en dev)"""
    if 'sqlite' in str(settings.DATABASE_URL):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@event.listens_for(async_engine.sync_engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log des requêtes lentes en production"""
    if not settings.DEBUG:
        context._query_start_time = asyncio.get_event_loop().time()


@event.listens_for(async_engine.sync_engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log des requêtes lentes en production"""
    if not settings.DEBUG:
        total = asyncio.get_event_loop().time() - context._query_start_time
        if total > 0.5:  # Log si > 500ms
            logger.warning(f"Slow query ({total:.2f}s): {statement[:100]}...")


# === UTILITAIRES DE TRANSACTION ===
class TransactionManager:
    """Gestionnaire de transactions pour opérations complexes"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._savepoints = []

    async def savepoint(self, name: str = None) -> str:
        """Crée un point de sauvegarde"""
        if not name:
            name = f"sp_{len(self._savepoints)}"

        await self.session.begin_nested()
        self._savepoints.append(name)
        return name

    async def rollback_to_savepoint(self, name: str = None):
        """Rollback vers un point de sauvegarde"""
        if name:
            if name in self._savepoints:
                idx = self._savepoints.index(name)
                self._savepoints = self._savepoints[:idx]

        await self.session.rollback()

    async def commit_savepoint(self, name: str = None):
        """Confirme un point de sauvegarde"""
        if name and name in self._savepoints:
            self._savepoints.remove(name)

        await self.session.commit()


# === HELPERS DE PAGINATION ===
class PaginationHelper:
    """Helper pour la pagination des requêtes"""

    @staticmethod
    def apply_pagination(query, page: int = 1, size: int = 20):
        """Applique la pagination à une requête"""
        # Validation des paramètres
        page = max(1, page)
        size = min(max(1, size), settings.MAX_PAGE_SIZE)

        # Calcul offset
        offset = (page - 1) * size

        return query.offset(offset).limit(size)

    @staticmethod
    def create_pagination_response(items, total: int, page: int, size: int):
        """Crée une réponse paginée standardisée"""
        total_pages = (total + size - 1) // size

        return {
            "items": items,
            "pagination": {
                "current_page": page,
                "page_size": size,
                "total_items": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1
            }
        }


# === OPTIMISATIONS REQUÊTES ===
class QueryOptimizer:
    """Optimiseur de requêtes pour de meilleures performances"""

    @staticmethod
    def with_eager_loading(query, *relationships):
        """Ajoute le chargement eager des relations"""
        from sqlalchemy.orm import selectinload

        for relationship in relationships:
            query = query.options(selectinload(relationship))

        return query

    @staticmethod
    def with_join_loading(query, *relationships):
        """Ajoute le chargement par jointure"""
        from sqlalchemy.orm import joinedload

        for relationship in relationships:
            query = query.options(joinedload(relationship))

        return query


# === INSTANCE GLOBALE ===
db_manager = DatabaseManager()


# Fonction de dépendance pour FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dépendance FastAPI pour obtenir une session de base de données"""
    async with db_manager.get_session() as session:
        yield session


# === INITIALISATION ===
async def init_db():
    """Initialise la base de données"""
    logger.info("Initializing database...")

    # Test de connexion
    if await db_manager.health_check():
        logger.info("Database connection successful")
    else:
        logger.error("Database connection failed")
        raise Exception("Cannot connect to database")

    logger.info("Database initialized successfully")


async def close_db():
    """Ferme les connexions à la base de données"""
    logger.info("Closing database connections...")
    await db_manager.close()
    logger.info("Database connections closed")


# === CRÉATION DES TABLES (DEV UNIQUEMENT) ===
async def create_tables():
    """Crée toutes les tables (pour le développement uniquement)"""
    if settings.ENVIRONMENT == "development":
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables created successfully")


async def drop_tables():
    """Supprime toutes les tables (pour les tests uniquement)"""
    if settings.ENVIRONMENT in ["development", "testing"]:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Tables dropped successfully")