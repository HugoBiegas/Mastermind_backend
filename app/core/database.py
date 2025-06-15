"""
Configuration de base de données pour Quantum Mastermind
SQLAlchemy 2.0.41 avec support async et PostgreSQL
"""
from typing import AsyncGenerator, Optional
import asyncio
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.ext.declarative import DeclarativeBase
from sqlalchemy.orm import (
    sessionmaker,
    Session,
    Mapped,
    mapped_column,
    relationship
)
from sqlalchemy import (
    create_engine,
    MetaData,
    inspect,
    text,
    event
)
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
        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,  # Log SQL en mode debug
            pool_size=20,
            max_overflow=30,
            pool_timeout=30,
            pool_pre_ping=True,  # Vérification des connexions
            pool_recycle=3600,   # Renouvellement des connexions
            connect_args={
                "server_settings": {
                    "application_name": "quantum_mastermind",
                    "jit": "off",  # Désactiver JIT pour la stabilité
                }
            }
        )

    return engine


def create_sync_database_engine():
    """
    Crée le moteur de base de données sync pour Alembic

    Returns:
        Moteur SQLAlchemy sync
    """
    if is_test():
        return create_engine(
            "sqlite:///./test.db",
            echo=False,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False}
        )
    else:
        # Convertir l'URL async en URL sync pour Alembic
        sync_url = settings.DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql://"
        )
        return create_engine(
            sync_url,
            echo=settings.DEBUG,
            pool_size=20,
            max_overflow=30,
            pool_timeout=30,
            pool_pre_ping=True,
            pool_recycle=3600
        )


# === INITIALISATION ===

async def init_db() -> None:
    """
    Initialise la base de données et crée les tables

    Cette fonction doit être appelée au démarrage de l'application
    """
    global async_engine, AsyncSessionLocal, sync_engine

    try:
        # Créer les moteurs
        async_engine = create_async_database_engine()
        sync_engine = create_sync_database_engine()

        # Créer la session factory
        AsyncSessionLocal = async_sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )

        # Test de connexion
        async with async_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        print("✅ Connexion à la base de données établie")

        # Créer les tables si nécessaire (en développement uniquement)
        if settings.DEBUG:
            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print("✅ Tables créées/vérifiées")

        # Configuration des événements de connexion
        setup_database_events()

    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la base de données: {e}")
        raise


async def close_db() -> None:
    """
    Ferme proprement les connexions de base de données
    """
    global async_engine, sync_engine

    if async_engine:
        await async_engine.dispose()
        print("✅ Connexions async fermées")

    if sync_engine:
        sync_engine.dispose()
        print("✅ Connexions sync fermées")


# === GESTION DES SESSIONS ===

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Générateur de sessions de base de données pour l'injection de dépendance

    Yields:
        Session de base de données async

    Example:
        ```python
        async def my_route(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
        ```
    """
    if not AsyncSessionLocal:
        raise RuntimeError("Base de données non initialisée")

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager pour obtenir une session de base de données

    Usage:
        ```python
        async with get_db_session() as db:
            result = await db.execute(select(User))
            await db.commit()
        ```
    """
    if not AsyncSessionLocal:
        raise RuntimeError("Base de données non initialisée")

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# === UTILITAIRES DE BASE DE DONNÉES ===

async def create_database_if_not_exists() -> None:
    """
    Crée la base de données si elle n'existe pas

    Utile pour l'initialisation en développement
    """
    if is_test():
        return  # SQLite en mémoire, pas besoin

    try:
        # Extraire le nom de la base de données
        import asyncpg
        from urllib.parse import urlparse

        parsed_url = urlparse(settings.DATABASE_URL)
        db_name = parsed_url.path[1:]  # Supprimer le '/' initial

        # Connexion à la base de données par défaut
        admin_url = settings.DATABASE_URL.replace(f"/{db_name}", "/postgres")

        conn = await asyncpg.connect(admin_url)
        try:
            # Vérifier si la base existe
            result = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", db_name
            )

            if not result:
                await conn.execute(f'CREATE DATABASE "{db_name}"')
                print(f"✅ Base de données '{db_name}' créée")
            else:
                print(f"✅ Base de données '{db_name}' existe déjà")

        finally:
            await conn.close()

    except Exception as e:
        print(f"⚠️ Impossible de créer la base de données: {e}")


async def check_database_connection() -> bool:
    """
    Vérifie la connexion à la base de données

    Returns:
        True si la connexion est fonctionnelle
    """
    try:
        async with get_db_session() as db:
            await db.execute(text("SELECT 1"))
            return True
    except Exception:
        return False


async def get_database_info() -> dict:
    """
    Récupère les informations sur la base de données

    Returns:
        Dictionnaire avec les informations de la base
    """
    try:
        async with get_db_session() as db:
            if is_test():
                return {
                    "type": "SQLite",
                    "version": "Test Database",
                    "size": "In Memory"
                }
            else:
                # PostgreSQL
                version_result = await db.execute(text("SELECT version()"))
                version = version_result.scalar()

                size_result = await db.execute(text(
                    "SELECT pg_size_pretty(pg_database_size(current_database()))"
                ))
                size = size_result.scalar()

                return {
                    "type": "PostgreSQL",
                    "version": version,
                    "size": size,
                    "url": settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else "Hidden"
                }
    except Exception as e:
        return {"error": str(e)}


# === ÉVÉNEMENTS DE BASE DE DONNÉES ===

def setup_database_events() -> None:
    """
    Configure les événements de base de données
    """
    if not async_engine:
        return

    @event.listens_for(async_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Configure SQLite pour les tests"""
        if "sqlite" in str(dbapi_connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    @event.listens_for(async_engine.sync_engine, "connect")
    def set_postgresql_search_path(dbapi_connection, connection_record):
        """Configure le search_path pour PostgreSQL"""
        if "postgresql" in str(dbapi_connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("SET search_path TO public")
            cursor.close()


# === MIGRATIONS ET MAINTENANCE ===

async def run_database_migration(revision: str = "head") -> None:
    """
    Exécute les migrations Alembic

    Args:
        revision: Révision cible (défaut: head)
    """
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, revision)
        print(f"✅ Migration vers {revision} effectuée")

    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        raise


async def backup_database(backup_path: str) -> None:
    """
    Crée une sauvegarde de la base de données

    Args:
        backup_path: Chemin de sauvegarde
    """
    if is_test():
        print("⚠️ Sauvegarde non supportée pour les tests")
        return

    try:
        import subprocess
        from urllib.parse import urlparse

        parsed_url = urlparse(settings.DATABASE_URL)

        cmd = [
            "pg_dump",
            f"--host={parsed_url.hostname}",
            f"--port={parsed_url.port or 5432}",
            f"--username={parsed_url.username}",
            f"--dbname={parsed_url.path[1:]}",
            f"--file={backup_path}",
            "--verbose",
            "--no-password"
        ]

        env = {"PGPASSWORD": parsed_url.password}

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✅ Sauvegarde créée: {backup_path}")
        else:
            print(f"❌ Erreur de sauvegarde: {result.stderr}")

    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")


# === HELPERS POUR LES TESTS ===

async def reset_test_database() -> None:
    """
    Remet à zéro la base de données de test
    """
    if not is_test():
        raise RuntimeError("Cette fonction est réservée aux tests")

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def get_test_session() -> AsyncSession:
    """
    Retourne une session de test

    Returns:
        Session de base de données pour les tests
    """
    if not is_test():
        raise RuntimeError("Cette fonction est réservée aux tests")

    return AsyncSessionLocal()


# === TRANSACTION HELPERS ===

@asynccontextmanager
async def database_transaction():
    """
    Context manager pour les transactions manuelles

    Usage:
        ```python
        async with database_transaction() as db:
            user = User(username="test")
            db.add(user)
            # Auto-commit à la fin du contexte
        ```
    """
    async with get_db_session() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise


async def execute_in_transaction(query_func, *args, **kwargs):
    """
    Exécute une fonction dans une transaction

    Args:
        query_func: Fonction async à exécuter
        *args, **kwargs: Arguments pour la fonction

    Returns:
        Résultat de la fonction
    """
    async with database_transaction() as db:
        return await query_func(db, *args, **kwargs)


# === MONITORING ET STATISTIQUES ===

async def get_database_stats() -> dict:
    """
    Récupère les statistiques de la base de données

    Returns:
        Statistiques de performance
    """
    try:
        async with get_db_session() as db:
            if is_test():
                return {"connections": 1, "type": "test"}

            # PostgreSQL stats
            stats_query = text("""
                SELECT 
                    numbackends as connections,
                    xact_commit as commits,
                    xact_rollback as rollbacks,
                    blks_read as blocks_read,
                    blks_hit as blocks_hit
                FROM pg_stat_database 
                WHERE datname = current_database()
            """)

            result = await db.execute(stats_query)
            row = result.fetchone()

            if row:
                return {
                    "connections": row.connections,
                    "commits": row.commits,
                    "rollbacks": row.rollbacks,
                    "blocks_read": row.blocks_read,
                    "blocks_hit": row.blocks_hit,
                    "cache_hit_ratio": round(
                        (row.blocks_hit / (row.blocks_hit + row.blocks_read)) * 100, 2
                    ) if (row.blocks_hit + row.blocks_read) > 0 else 0
                }

            return {}

    except Exception as e:
        return {"error": str(e)}


# === EXPORT ===

__all__ = [
    "Base",
    "async_engine",
    "AsyncSessionLocal",
    "init_db",
    "close_db",
    "get_db",
    "get_db_session",
    "create_database_if_not_exists",
    "check_database_connection",
    "get_database_info",
    "run_database_migration",
    "backup_database",
    "reset_test_database",
    "get_test_session",
    "database_transaction",
    "execute_in_transaction",
    "get_database_stats"
]