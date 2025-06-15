"""
Configuration globale de l'application Quantum Mastermind
Gestion sécurisée des variables d'environnement et paramètres
"""
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings
from pydantic_core import MultiHostUrl
import secrets


class Settings(BaseSettings):
    """Configuration principale de l'application"""

    # === APPLICATION ===
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    PROJECT_NAME: str = "Quantum Mastermind API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # === SERVEUR ===
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    WORKERS: int = 1
    MAX_REQUESTS: int = 1000
    MAX_REQUESTS_JITTER: int = 100

    # === BASE DE DONNÉES ===
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "quantum_user"
    DB_PASSWORD: str = "quantum_pass"
    DB_NAME: str = "quantum_mastermind"
    DATABASE_URL: Optional[str] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info) -> Any:
        if isinstance(v, str):
            return v

        # Accès aux valeurs via info.data dans Pydantic v2
        values = info.data
        return str(MultiHostUrl.build(
            scheme="postgresql+asyncpg",
            username=values.get("DB_USER"),
            password=values.get("DB_PASSWORD"),
            host=values.get("DB_HOST"),
            port=values.get("DB_PORT"),
            path=f"/{values.get('DB_NAME') or ''}",
        ))

    # === REDIS ===
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_MAX_CONNECTIONS: int = 20

    # === SÉCURITÉ JWT ===
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # === CORS ET SÉCURITÉ ===
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:4200"]
    TRUSTED_HOSTS: List[str] = ["localhost", "127.0.0.1"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    @field_validator("TRUSTED_HOSTS", mode="before")
    @classmethod
    def assemble_trusted_hosts(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # === QUANTUM COMPUTING ===
    QISKIT_BACKEND: str = "qasm_simulator"
    MAX_QUBITS: int = 30
    QUANTUM_SHOTS: int = 1024
    QUANTUM_OPTIMIZATION_LEVEL: int = 1
    QUANTUM_TIMEOUT: int = 300  # 5 minutes

    # === EMAIL (pour futures fonctionnalités) ===
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = None
    EMAILS_FROM_NAME: Optional[str] = None

    # === FICHIERS ET UPLOADS ===
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_FILE_TYPES: List[str] = ["json", "csv", "txt"]
    UPLOAD_PATH: str = "uploads"

    # === CACHE ET SESSIONS ===
    CACHE_TTL: int = 300  # 5 minutes
    SESSION_TIMEOUT: int = 1800  # 30 minutes
    REMEMBER_ME_EXPIRE_DAYS: int = 30

    # === RATE LIMITING ===
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # secondes

    # === LOGGING ===
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: Optional[str] = None
    ENABLE_REQUEST_LOGGING: bool = True

    # === MONITORING ===
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    HEALTH_CHECK_INTERVAL: int = 30

    # === FEATURES FLAGS ===
    ENABLE_REGISTRATION: bool = True
    ENABLE_EMAIL_VERIFICATION: bool = False
    ENABLE_QUANTUM_FEATURES: bool = True
    ENABLE_MULTIPLAYER: bool = True
    ENABLE_CHAT: bool = True
    ENABLE_TOURNAMENTS: bool = False  # Futur

    # === GAME SETTINGS ===
    DEFAULT_MAX_ATTEMPTS: int = 12
    DEFAULT_COMBINATION_LENGTH: int = 4
    DEFAULT_COLOR_COUNT: int = 6
    MAX_PLAYERS_PER_GAME: int = 8
    GAME_TIMEOUT_MINUTES: int = 60

    # === WEBSOCKET ===
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_CONNECTION_TIMEOUT: int = 60
    WS_MAX_CONNECTIONS_PER_USER: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Retourne les paramètres de configuration avec cache
    Pattern Singleton pour optimiser les performances
    """
    return Settings()


# Instance globale des paramètres
settings = get_settings()


# === CONFIGURATION SÉCURITÉ ===
class SecurityConfig:
    """Configuration spécifique à la sécurité"""

    # Algorithmes de hachage autorisés
    ALLOWED_HASH_ALGORITHMS = ["HS256", "RS256"]

    # Durées d'expiration
    PASSWORD_RESET_EXPIRE_HOURS = 24
    EMAIL_VERIFICATION_EXPIRE_HOURS = 48

    # Complexité mot de passe
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_LOWERCASE = True
    PASSWORD_REQUIRE_DIGITS = True
    PASSWORD_REQUIRE_SPECIAL = True

    # Headers de sécurité
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }

    # IP Whitelisting pour admin
    ADMIN_IP_WHITELIST = ["127.0.0.1", "::1"]

    # Tentatives de connexion
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15

    # Validation des tokens
    TOKEN_BLACKLIST_CHECK = True
    REFRESH_TOKEN_ROTATION = True


# === CONFIGURATION QUANTUM ===
class QuantumConfig:
    """Configuration pour les opérations quantiques"""

    # Backends disponibles (Qiskit 2.0.2 compatible)
    AVAILABLE_BACKENDS = [
        "qasm_simulator",
        "statevector_simulator",
        "unitary_simulator"
    ]

    # Paramètres par défaut des circuits
    DEFAULT_CIRCUIT_DEPTH = 5
    MAX_CIRCUIT_DEPTH = 20
    DEFAULT_SHOTS = 1024
    MAX_SHOTS = 8192

    # Algorithmes quantiques supportés
    SUPPORTED_ALGORITHMS = [
        "grover_search",
        "quantum_superposition",
        "entanglement_generation",
        "quantum_interference"
    ]

    # Scoring quantique
    GROVER_HINT_POINTS = 50
    SUPERPOSITION_POINTS = 25
    ENTANGLEMENT_POINTS = 30
    MEASUREMENT_COST = 5

    # Limites de sécurité
    MAX_QUBITS_PER_CIRCUIT = 30
    MAX_OPERATIONS_PER_CIRCUIT = 1000
    QUANTUM_OPERATION_TIMEOUT = 30  # secondes

    # Cache des résultats quantiques
    CACHE_QUANTUM_RESULTS = True
    QUANTUM_CACHE_TTL = 600  # 10 minutes


# === CONFIGURATION DES JEUX ===
class GameConfig:
    """Configuration spécifique aux jeux"""

    # Types de jeux disponibles
    GAME_TYPES = [
        "classic",
        "quantum",
        "hybrid",
        "tournament"
    ]

    # Modes de jeu
    GAME_MODES = [
        "solo",
        "multiplayer",
        "ranked",
        "training"
    ]

    # Difficultés
    DIFFICULTIES = {
        "easy": {
            "colors": 4,
            "length": 3,
            "max_attempts": 15,
            "hints_allowed": True
        },
        "normal": {
            "colors": 6,
            "length": 4,
            "max_attempts": 12,
            "hints_allowed": True
        },
        "hard": {
            "colors": 8,
            "length": 5,
            "max_attempts": 10,
            "hints_allowed": False
        },
        "expert": {
            "colors": 10,
            "length": 6,
            "max_attempts": 8,
            "hints_allowed": False
        }
    }

    # Scoring
    BASE_SCORE = 1000
    ATTEMPT_PENALTY = 50
    TIME_BONUS_MULTIPLIER = 2.0
    QUANTUM_BONUS_MULTIPLIER = 1.5
    PERFECT_GAME_BONUS = 500

    # Limites
    MAX_GAME_DURATION_HOURS = 24
    MAX_CONCURRENT_GAMES_PER_USER = 5
    MIN_PLAYERS_FOR_MULTIPLAYER = 2


# === CONFIGURATION WEBSOCKET ===
class WebSocketConfig:
    """Configuration WebSocket"""

    # Types de connexions
    CONNECTION_TYPES = [
        "game",
        "chat",
        "admin",
        "tournament"
    ]

    # Événements supportés
    SUPPORTED_EVENTS = [
        "connection_established",
        "user_connected",
        "user_disconnected",
        "authenticate",
        "join_game_room",
        "leave_game_room",
        "game_state_update",
        "attempt_made",
        "quantum_hint_used",
        "chat_message",
        "heartbeat"
    ]

    # Limites
    MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
    MAX_MESSAGES_PER_SECOND = 10
    HEARTBEAT_INTERVAL = 30
    CONNECTION_TIMEOUT = 60

    # Rate limiting WebSocket
    WS_RATE_LIMIT_WINDOW = 60  # secondes
    WS_RATE_LIMIT_MAX_MESSAGES = 100


# === CONFIGURATION DE DÉVELOPPEMENT ===
class DevelopmentConfig:
    """Configuration pour le développement"""

    # Debug
    ENABLE_DEBUG_ROUTES = True
    ENABLE_SOLUTION_REVEAL = True
    ENABLE_MOCK_QUANTUM = False

    # Base de données
    ECHO_SQL = False
    DROP_TABLES_ON_START = False

    # Tests
    TEST_DATABASE_URL = "postgresql+asyncpg://test_user:test_pass@localhost/test_quantum"
    ENABLE_TEST_FIXTURES = True

    # Performance
    DISABLE_RATE_LIMITING = True
    FAST_PASSWORD_HASHING = True


# === CONFIGURATION DE PRODUCTION ===
class ProductionConfig:
    """Configuration pour la production"""

    # Sécurité renforcée
    REQUIRE_HTTPS = True
    STRICT_CORS = True
    ENABLE_CSRF_PROTECTION = True

    # Performance
    ENABLE_COMPRESSION = True
    ENABLE_CACHING = True
    CACHE_STATIC_ASSETS = True

    # Monitoring
    ENABLE_METRICS = True
    ENABLE_HEALTH_CHECKS = True
    ENABLE_DISTRIBUTED_TRACING = False

    # Base de données
    DB_POOL_SIZE = 20
    DB_MAX_OVERFLOW = 30
    DB_POOL_TIMEOUT = 30


# Instances globales des configurations
security_config = SecurityConfig()
quantum_config = QuantumConfig()
game_config = GameConfig()
websocket_config = WebSocketConfig()
development_config = DevelopmentConfig()
production_config = ProductionConfig()


# === HELPERS DE CONFIGURATION ===

def get_config_for_environment(env: str = None) -> Dict[str, Any]:
    """
    Retourne la configuration appropriée pour l'environnement

    Args:
        env: Environnement (development, production, test)

    Returns:
        Configuration environnementale
    """
    env = env or settings.ENVIRONMENT.lower()

    base_config = {
        "settings": settings,
        "security": security_config,
        "quantum": quantum_config,
        "game": game_config,
        "websocket": websocket_config
    }

    if env == "development":
        base_config["development"] = development_config
    elif env == "production":
        base_config["production"] = production_config

    return base_config


def validate_configuration() -> List[str]:
    """
    Valide la configuration et retourne les erreurs

    Returns:
        Liste des erreurs de configuration
    """
    errors = []

    # Validation des variables obligatoires
    if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32:
        errors.append("SECRET_KEY doit faire au moins 32 caractères")

    if not settings.JWT_SECRET_KEY or len(settings.JWT_SECRET_KEY) < 32:
        errors.append("JWT_SECRET_KEY doit faire au moins 32 caractères")

    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL est requis")

    # Validation de l'environnement
    valid_environments = ["development", "production", "test"]
    if settings.ENVIRONMENT.lower() not in valid_environments:
        errors.append(f"ENVIRONMENT doit être dans {valid_environments}")

    # Validation des backends quantiques
    if settings.QISKIT_BACKEND not in quantum_config.AVAILABLE_BACKENDS:
        errors.append(f"QISKIT_BACKEND doit être dans {quantum_config.AVAILABLE_BACKENDS}")

    # Validation des limites
    if settings.MAX_QUBITS > 50:  # Limite raisonnable pour la simulation
        errors.append("MAX_QUBITS ne devrait pas dépasser 50 pour les performances")

    if settings.QUANTUM_SHOTS > quantum_config.MAX_SHOTS:
        errors.append(f"QUANTUM_SHOTS ne peut pas dépasser {quantum_config.MAX_SHOTS}")

    # Validation des CORS en production
    if settings.ENVIRONMENT == "production":
        dangerous_origins = ["*", "http://localhost:3000"]
        for origin in settings.CORS_ORIGINS:
            if origin in dangerous_origins:
                errors.append(f"Origine CORS dangereuse en production: {origin}")

    return errors


def is_development() -> bool:
    """Vérifie si on est en mode développement"""
    return settings.ENVIRONMENT.lower() == "development"


def is_production() -> bool:
    """Vérifie si on est en mode production"""
    return settings.ENVIRONMENT.lower() == "production"


def is_test() -> bool:
    """Vérifie si on est en mode test"""
    return settings.ENVIRONMENT.lower() == "test"


# === VALIDATION AU DÉMARRAGE ===

def startup_config_check():
    """Vérifie la configuration au démarrage de l'application"""
    errors = validate_configuration()

    if errors:
        print("❌ Erreurs de configuration détectées:")
        for error in errors:
            print(f"  - {error}")

        if is_production():
            raise ValueError("Configuration invalide en production")
        else:
            print("⚠️  Application démarrée avec des avertissements de configuration")
    else:
        print("✅ Configuration validée avec succès")


# === EXPORT DE LA CONFIGURATION ===

__all__ = [
    "settings",
    "security_config",
    "quantum_config",
    "game_config",
    "websocket_config",
    "development_config",
    "production_config",
    "get_settings",
    "get_config_for_environment",
    "validate_configuration",
    "is_development",
    "is_production",
    "is_test",
    "startup_config_check"
]