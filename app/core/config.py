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

    # === CORS ===
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # === HOSTS DE CONFIANCE ===
    TRUSTED_HOSTS: List[str] = ["localhost", "127.0.0.1"]

    # === QUANTUM COMPUTING ===
    QISKIT_BACKEND: str = "qasm_simulator"
    MAX_QUBITS: int = 30
    QUANTUM_SHOTS: int = 1024
    QUANTUM_OPTIMIZATION_LEVEL: int = 1
    QUANTUM_TIMEOUT_SECONDS: int = 30

    # === LOGGING ===
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: str = "/app/logs/quantum_mastermind.log"

    # === MONITORING ===
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    HEALTH_CHECK_INTERVAL: int = 30

    # === RATE LIMITING ===
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10

    # === WEBSOCKET ===
    WEBSOCKET_HEARTBEAT_INTERVAL: int = 30
    WEBSOCKET_MAX_CONNECTIONS_PER_USER: int = 3
    WEBSOCKET_MESSAGE_MAX_SIZE: int = 1024 * 10  # 10KB

    # === GAME SETTINGS ===
    MAX_GAME_DURATION_MINUTES: int = 30
    MAX_PLAYERS_PER_GAME: int = 8
    MIN_PLAYERS_BATTLE_ROYALE: int = 3
    DEFAULT_MAX_ATTEMPTS: int = 10
    QUANTUM_HINTS_MAX_PER_GAME: int = 3

    # === PAGINATION ===
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # === CORS ET SÉCURITÉ AVANCÉE ===
    ALLOWED_HOSTS: List[str] = ["*"]
    CORS_ORIGINS: List[AnyHttpUrl] = []

    # === CACHE ET SESSIONS ===
    CACHE_TTL: int = 3600
    SESSION_TTL: int = 7200

    # === RATE LIMITING AVANCÉ ===
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    # === EMAIL (pour les fonctionnalités futures) ===
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: Optional[str] = None

    # === LIMITES ET PERFORMANCES ===
    MAX_CONNECTION_POOL_SIZE: int = 20
    MAX_OVERFLOW: int = 30
    CONNECTION_TIMEOUT: int = 30
    REQUEST_TIMEOUT: int = 60

    # === SÉCURITÉ AVANCÉE ===
    ALLOWED_IPS: List[str] = []
    BLOCKED_IPS: List[str] = []
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_DURATION: int = 900  # 15 minutes

    # === QUANTUM SPECIFIC ===
    MAX_QUBITS_DEFAULT: int = 10
    MAX_QUANTUM_OPERATIONS: int = 1000
    QUANTUM_SIMULATION_MEMORY_LIMIT: int = 2048  # MB

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "validate_assignment": True,
        "case_sensitive": False
    }

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from string or list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse allowed hosts from string or list"""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",") if host.strip()]
        return v

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v: Union[str, bool]) -> bool:
        """Parse DEBUG from string or bool"""
        if isinstance(v, str):
            return v.lower() in ("true", "1", "on", "yes")
        return v

    @property
    def database_url_sync(self) -> str:
        """URL de base de données synchrone pour Alembic"""
        if self.DATABASE_URL:
            return self.DATABASE_URL.replace("+asyncpg", "")
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def redis_url_parsed(self) -> str:
        """URL Redis parsée avec mot de passe si nécessaire"""
        if self.REDIS_PASSWORD:
            return self.REDIS_URL.replace("redis://", f"redis://:{self.REDIS_PASSWORD}@")
        return self.REDIS_URL

    def get_logging_config(self) -> Dict[str, Any]:
        """Configuration complète du logging"""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
                "access": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
                "access": {
                    "formatter": "access",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": self.LOG_LEVEL},
                "uvicorn.error": {"level": "INFO"},
                "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
                "quantum_mastermind": {"handlers": ["default"], "level": self.LOG_LEVEL, "propagate": False},
            },
        }


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
    }

    # IP Whitelisting pour admin
    ADMIN_IP_WHITELIST = ["127.0.0.1", "::1"]


# === CONFIGURATION QUANTUM ===
class QuantumConfig:
    """Configuration pour les opérations quantiques"""

    # Backends disponibles
    AVAILABLE_BACKENDS = [
        "qasm_simulator",
        "statevector_simulator",
        "unitary_simulator"
    ]

    # Paramètres par défaut des circuits
    DEFAULT_CIRCUIT_DEPTH = 5
    MAX_CIRCUIT_DEPTH = 20

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


# Instances globales des configurations
security_config = SecurityConfig()
quantum_config = QuantumConfig()