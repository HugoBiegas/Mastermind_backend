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
    DEBUG: bool = True

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
    ENABLE_REGISTRATION: bool = True
    ENABLE_EMAIL_VERIFICATION: bool = False

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
        raise ValueError("CORS_ORIGINS doit être une liste ou une chaîne")

    # === QUANTUM COMPUTING ===
    QISKIT_BACKEND: str = "qasm_simulator"
    MAX_QUBITS: int = 10
    QUANTUM_SHOTS: int = 1024
    QUANTUM_TIMEOUT: int = 300
    ENABLE_QUANTUM_HINTS: bool = True

    # === EMAIL ===
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = None
    EMAILS_FROM_NAME: Optional[str] = None

    @field_validator("EMAILS_FROM_NAME")
    @classmethod
    def get_project_name(cls, v: Optional[str], info) -> str:
        if not v:
            return info.data.get("PROJECT_NAME", "Quantum Mastermind")
        return v

    # === SÉCURITÉ AVANCÉE ===
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_NUMBERS: bool = True
    PASSWORD_REQUIRE_SYMBOLS: bool = False
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    # === RATE LIMITING ===
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 3600  # 1 heure
    RATE_LIMIT_STORAGE: str = "memory"  # ou "redis"

    # === WEBSOCKETS ===
    WS_MAX_CONNECTIONS: int = 1000
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_CONNECTION_TIMEOUT: int = 60

    # === LOGGING ===
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: Optional[str] = None
    ENABLE_ACCESS_LOG: bool = True

    # === MONITORING ===
    ENABLE_METRICS: bool = True
    METRICS_PATH: str = "/metrics"
    HEALTH_CHECK_PATH: str = "/health"

    class Config:
        case_sensitive = True
        env_file = ".env"


class SecurityConfig:
    """Configuration de sécurité"""

    # Algorithmes de hachage supportés
    SUPPORTED_HASH_ALGORITHMS = ["bcrypt", "argon2"]
    DEFAULT_HASH_ALGORITHM = "bcrypt"

    # Configuration bcrypt
    BCRYPT_ROUNDS = 12

    # Configuration Argon2
    ARGON2_TIME_COST = 2
    ARGON2_MEMORY_COST = 65536
    ARGON2_PARALLELISM = 1

    # Longueurs de tokens
    TOKEN_LENGTH = 32
    API_KEY_LENGTH = 64

    # Expiration des tokens spéciaux
    PASSWORD_RESET_EXPIRE_HOURS = 24
    EMAIL_VERIFICATION_EXPIRE_HOURS = 48

    # Headers de sécurité
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }


class QuantumConfig:
    """Configuration des fonctionnalités quantiques"""

    # Backends disponibles
    AVAILABLE_BACKENDS = [
        "qasm_simulator",
        "aer_simulator",
        "statevector_simulator",
        "unitary_simulator"
    ]

    # Limites par défaut
    DEFAULT_QUBITS = 4
    MAX_QUBITS = 20
    DEFAULT_SHOTS = 1024
    MAX_SHOTS = 8192

    # Types d'algorithmes supportés
    SUPPORTED_ALGORITHMS = [
        "grover_search",
        "quantum_fourier",
        "phase_estimation",
        "amplitude_amplification"
    ]

    # Configuration des hints
    HINT_COSTS = {
        "grover": 10,
        "superposition": 5,
        "entanglement": 15,
        "interference": 8
    }

    # Timeouts
    CIRCUIT_EXECUTION_TIMEOUT = 30
    ALGORITHM_TIMEOUT = 60


class GameConfig:
    """Configuration des paramètres de jeu"""

    # Paramètres par défaut
    DEFAULT_COMBINATION_LENGTH = 4
    DEFAULT_COLOR_COUNT = 6
    DEFAULT_MAX_ATTEMPTS = 10

    # Limites
    MIN_COMBINATION_LENGTH = 3
    MAX_COMBINATION_LENGTH = 8
    MIN_COLOR_COUNT = 4
    MAX_COLOR_COUNT = 10
    MAX_ATTEMPTS_LIMIT = 20

    # Scoring
    BASE_SCORE = 1000
    ATTEMPT_PENALTY = 50
    TIME_BONUS_MULTIPLIER = 0.1
    QUANTUM_BONUS_MULTIPLIER = 1.5

    # Difficultés
    DIFFICULTY_SETTINGS = {
        "easy": {
            "combination_length": 3,
            "color_count": 4,
            "max_attempts": 15,
            "time_limit": None,
            "duplicates_allowed": True
        },
        "normal": {
            "combination_length": 4,
            "color_count": 6,
            "max_attempts": 10,
            "time_limit": 600,  # 10 minutes
            "duplicates_allowed": True
        },
        "hard": {
            "combination_length": 5,
            "color_count": 8,
            "max_attempts": 8,
            "time_limit": 300,  # 5 minutes
            "duplicates_allowed": False
        },
        "expert": {
            "combination_length": 6,
            "color_count": 10,
            "max_attempts": 6,
            "time_limit": 180,  # 3 minutes
            "duplicates_allowed": False
        }
    }


class WebSocketConfig:
    """Configuration WebSocket"""

    # Limites de connexion
    MAX_CONNECTIONS_PER_USER = 3
    MAX_ROOMS_PER_USER = 5
    MAX_USERS_PER_ROOM = 8

    # Timeouts
    CONNECTION_TIMEOUT = 60
    HEARTBEAT_INTERVAL = 30
    CLEANUP_INTERVAL = 300

    # Tailles de messages
    MAX_MESSAGE_SIZE = 1024 * 64  # 64KB
    MAX_QUEUE_SIZE = 100

    # Types d'événements
    ALLOWED_EVENT_TYPES = [
        "authenticate", "join_room", "leave_room",
        "make_attempt", "get_hint", "chat_message",
        "heartbeat", "game_state_request"
    ]


class DevelopmentConfig:
    """Configuration pour le développement"""

    DEBUG = True
    LOG_LEVEL = "DEBUG"
    ENABLE_METRICS = True
    CORS_ORIGINS = ["*"]
    TRUSTED_HOSTS = ["*"]

    # Base de données de développement
    DB_ECHO = True
    DB_POOL_SIZE = 5
    DB_MAX_OVERFLOW = 10

    # Quantum computing en mode dev
    QISKIT_BACKEND = "qasm_simulator"
    MAX_QUBITS = 5
    QUANTUM_SHOTS = 512


class ProductionConfig:
    """Configuration pour la production"""

    DEBUG = False
    LOG_LEVEL = "WARNING"
    ENABLE_METRICS = True

    # Base de données optimisée pour la production
    DB_ECHO = False
    DB_POOL_SIZE = 20
    DB_MAX_OVERFLOW = 30
    DB_POOL_RECYCLE = 3600

    # Sécurité renforcée
    PASSWORD_MIN_LENGTH = 12
    MAX_LOGIN_ATTEMPTS = 3
    LOCKOUT_DURATION_MINUTES = 30

    # Performance quantique optimisée
    QUANTUM_SHOTS = 2048
    MAX_QUBITS = 15


# === INSTANCES GLOBALES ===

settings = Settings()
security_config = SecurityConfig()
quantum_config = QuantumConfig()
game_config = GameConfig()
websocket_config = WebSocketConfig()
development_config = DevelopmentConfig()
production_config = ProductionConfig()


# === FONCTIONS UTILITAIRES ===

@lru_cache()
def get_settings() -> Settings:
    """Retourne l'instance de configuration mise en cache"""
    return Settings()


def get_config_for_environment(env: str) -> Dict[str, Any]:
    """
    Retourne la configuration pour un environnement spécifique

    Args:
        env: Environnement (development, production, test)

    Returns:
        Configuration pour l'environnement
    """
    if env == "development":
        return development_config.__dict__
    elif env == "production":
        return production_config.__dict__
    else:
        return {}


def validate_configuration() -> List[str]:
    """
    Valide la configuration actuelle et retourne les erreurs

    Returns:
        Liste des erreurs de configuration
    """
    errors = []

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