"""
Configuration globale de l'application Quantum Mastermind
Gestion sécurisée des variables d'environnement et paramètres
"""
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union
from pydantic import AnyHttpUrl, BaseSettings, PostgresDsn, validator
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
    DATABASE_URL: Optional[PostgresDsn] = None

    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            user=values.get("DB_USER"),
            password=values.get("DB_PASSWORD"),
            host=values.get("DB_HOST"),
            port=str(values.get("DB_PORT")),
            path=f"/{values.get('DB_NAME') or ''}",
        )

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
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = [
        "http://localhost:3000",
        "http://localhost:4200",
        "http://localhost:8080"
    ]

    @validator("BACKEND_CORS_ORIGINS", pre=True)
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

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Singleton pour la configuration - utilise le cache LRU"""
    return Settings()


# Instance globale
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