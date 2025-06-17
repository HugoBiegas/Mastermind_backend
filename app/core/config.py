"""
Configuration de l'application Quantum Mastermind
MODIFIÉ: Ajout des paramètres de configuration quantique
"""
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from pydantic import validator, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration principale de l'application"""

    # === INFORMATIONS DE BASE ===
    PROJECT_NAME: str = "Quantum Mastermind"
    VERSION: str = "1.0.0-quantum"
    DESCRIPTION: str = "Jeu de Mastermind avec informatique quantique"

    # === ENVIRONNEMENT ===
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # === API ===
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_PREFIX: str = "/api/v1"

    # === BASE DE DONNÉES ===
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://quantum_user:quantum_pass@localhost:5432/quantum_mastermind"
    )

    # Paramètres de connexion
    DB_ECHO: bool = DEBUG
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))

    # === REDIS ===
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_MAX_CONNECTIONS: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "10"))

    # === SÉCURITÉ ===
    SECRET_KEY: str = os.getenv("SECRET_KEY", "quantum-secret-key-change-in-production")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "jwt-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    JWT_REFRESH_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7"))

    # === CORS ===
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:4200",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:4200"
    ]
    TRUSTED_HOSTS: List[str] = ["localhost", "127.0.0.1"]

    # === NOUVEAU: CONFIGURATION QUANTIQUE ===

    # Backend quantique
    QISKIT_BACKEND: str = os.getenv("QISKIT_BACKEND", "qasm_simulator")
    QUANTUM_BACKEND_TYPE: str = os.getenv("QUANTUM_BACKEND_TYPE", "simulator")  # simulator, ibm_quantum, local

    # Paramètres de performance quantique
    MAX_QUBITS: int = int(os.getenv("MAX_QUBITS", "5"))
    QUANTUM_SHOTS: int = int(os.getenv("QUANTUM_SHOTS", "1024"))
    QUANTUM_OPTIMIZATION_LEVEL: int = int(os.getenv("QUANTUM_OPTIMIZATION_LEVEL", "1"))
    QUANTUM_TIMEOUT: int = int(os.getenv("QUANTUM_TIMEOUT", "30"))  # secondes

    # Limites quantiques pour la sécurité
    MAX_QUANTUM_SHOTS: int = int(os.getenv("MAX_QUANTUM_SHOTS", "8192"))
    MAX_QUANTUM_QUBITS: int = int(os.getenv("MAX_QUANTUM_QUBITS", "10"))
    QUANTUM_RATE_LIMIT: int = int(os.getenv("QUANTUM_RATE_LIMIT", "100"))  # requêtes/heure

    # Configuration des algorithmes quantiques
    ENABLE_GROVER: bool = os.getenv("ENABLE_GROVER", "true").lower() == "true"
    ENABLE_SUPERPOSITION: bool = os.getenv("ENABLE_SUPERPOSITION", "true").lower() == "true"
    ENABLE_ENTANGLEMENT: bool = os.getenv("ENABLE_ENTANGLEMENT", "true").lower() == "true"
    ENABLE_QUANTUM_SOLUTION_GEN: bool = os.getenv("ENABLE_QUANTUM_SOLUTION_GEN", "true").lower() == "true"
    ENABLE_QUANTUM_HINTS_CALC: bool = os.getenv("ENABLE_QUANTUM_HINTS_CALC", "true").lower() == "true"

    # Fallback et tolérance aux pannes
    QUANTUM_FALLBACK_ENABLED: bool = os.getenv("QUANTUM_FALLBACK_ENABLED", "true").lower() == "true"
    QUANTUM_ERROR_THRESHOLD: int = int(os.getenv("QUANTUM_ERROR_THRESHOLD", "5"))  # erreurs avant fallback
    QUANTUM_RETRY_ATTEMPTS: int = int(os.getenv("QUANTUM_RETRY_ATTEMPTS", "3"))

    # Logging et monitoring quantique
    QUANTUM_METRICS_ENABLED: bool = os.getenv("QUANTUM_METRICS_ENABLED", "true").lower() == "true"
    QUANTUM_DETAILED_LOGGING: bool = os.getenv("QUANTUM_DETAILED_LOGGING", "false").lower() == "true"

    # === CONFIGURATION IBM QUANTUM (si utilisé) ===
    IBM_QUANTUM_TOKEN: Optional[str] = os.getenv("IBM_QUANTUM_TOKEN")
    IBM_QUANTUM_HUB: Optional[str] = os.getenv("IBM_QUANTUM_HUB", "ibm-q")
    IBM_QUANTUM_GROUP: Optional[str] = os.getenv("IBM_QUANTUM_GROUP", "open")
    IBM_QUANTUM_PROJECT: Optional[str] = os.getenv("IBM_QUANTUM_PROJECT", "main")

    # === VALIDATION ===

    @validator('CORS_ORIGINS', pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @validator('TRUSTED_HOSTS', pre=True)
    def parse_trusted_hosts(cls, v):
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v

    @validator('QUANTUM_SHOTS')
    def validate_quantum_shots(cls, v):
        if v < 100 or v > 8192:
            raise ValueError("QUANTUM_SHOTS doit être entre 100 et 8192")
        return v

    @validator('MAX_QUBITS')
    def validate_max_qubits(cls, v):
        if v < 1 or v > 20:
            raise ValueError("MAX_QUBITS doit être entre 1 et 20")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


class SecurityConfig:
    """Configuration de sécurité avancée"""

    # Mots de passe
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_LOWERCASE = True
    PASSWORD_REQUIRE_DIGITS = True
    PASSWORD_REQUIRE_SPECIAL = True

    # Sessions
    SESSION_TIMEOUT_MINUTES = 30
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15

    # Rate limiting
    RATE_LIMIT_PER_MINUTE = 60
    RATE_LIMIT_PER_HOUR = 1000

    # NOUVEAU: Sécurité quantique
    QUANTUM_OPERATIONS_PER_HOUR = 100
    QUANTUM_MAX_CONCURRENT_CIRCUITS = 5
    QUANTUM_CIRCUIT_COMPLEXITY_LIMIT = 50  # nombre de portes max


class QuantumConfig:
    """Configuration spécialisée pour les opérations quantiques"""

    # Backends disponibles
    AVAILABLE_BACKENDS = [
        "qasm_simulator",
        "statevector_simulator",
        "unitary_simulator",
        "aer_simulator"
    ]

    # Algorithmes supportés
    SUPPORTED_ALGORITHMS = [
        "quantum_solution_generation",
        "quantum_hints_calculation",
        "grover_search",
        "superposition_analysis",
        "entanglement_detection"
    ]

    # Types de hints quantiques
    QUANTUM_HINT_TYPES = [
        "grover",
        "superposition",
        "entanglement",
        "basic"
    ]

    # Coûts des opérations quantiques (en points de jeu)
    QUANTUM_OPERATION_COSTS = {
        "grover_hint": 50,
        "superposition_hint": 25,
        "entanglement_hint": 35,
        "basic_hint": 10,
        "solution_generation": 0,  # Gratuit car automatique
        "hints_calculation": 0     # Gratuit car automatique
    }

    # Limites de performance
    DEFAULT_SHOTS = 1024
    MIN_SHOTS = 100
    MAX_SHOTS = 8192
    DEFAULT_QUBITS = 4
    MAX_QUBITS = 10

    # Timeouts
    CIRCUIT_EXECUTION_TIMEOUT = 30  # secondes
    QUANTUM_OPERATION_TIMEOUT = 60  # secondes

    # Qualité et précision
    MINIMUM_FIDELITY = 0.8
    STATISTICAL_SIGNIFICANCE_THRESHOLD = 0.05
    CONVERGENCE_TOLERANCE = 1e-6


class GameConfig:
    """Configuration spécifique au jeu"""

    # Paramètres de jeu par défaut
    DEFAULT_COMBINATION_LENGTH = 4
    DEFAULT_AVAILABLE_COLORS = 6
    DEFAULT_MAX_ATTEMPTS = 12
    DEFAULT_TIME_LIMIT = None

    # Limites
    MIN_COMBINATION_LENGTH = 3
    MAX_COMBINATION_LENGTH = 8
    MIN_COLORS = 4
    MAX_COLORS = 10
    MIN_ATTEMPTS = 1
    MAX_ATTEMPTS = 50
    MIN_TIME_LIMIT = 60  # secondes
    MAX_TIME_LIMIT = 3600  # 1 heure

    # Multijoueur
    MAX_PLAYERS_PER_GAME = 8
    DEFAULT_ROOM_CODE_LENGTH = 8

    # Scoring
    BASE_SCORE = 1000
    ATTEMPT_PENALTY = 50
    TIME_PENALTY_FACTOR = 10

    # NOUVEAU: Configuration quantique spécifique au jeu
    QUANTUM_SCORE_MULTIPLIER = 1.5
    QUANTUM_HINT_BONUS = 10
    QUANTUM_SOLUTION_BONUS = 25
    QUANTUM_CALCULATION_BONUS = 5


class WebSocketConfig:
    """Configuration WebSocket"""

    MAX_CONNECTIONS = 1000
    PING_INTERVAL = 30
    PING_TIMEOUT = 10
    MESSAGE_QUEUE_SIZE = 100

    # Types de messages
    MESSAGE_TYPES = [
        "game_update",
        "player_joined",
        "player_left",
        "attempt_made",
        "game_finished",
        "quantum_hint_generated",  # NOUVEAU
        "quantum_calculation_done"  # NOUVEAU
    ]


class DevelopmentConfig:
    """Configuration pour le développement"""

    DEBUG = True
    LOG_LEVEL = "DEBUG"

    # Base de données en mode développement
    DB_ECHO = True
    DB_POOL_SIZE = 5
    DB_MAX_OVERFLOW = 10

    # Quantum en mode dev
    QISKIT_BACKEND = "qasm_simulator"
    MAX_QUBITS = 5
    QUANTUM_SHOTS = 512
    QUANTUM_DETAILED_LOGGING = True


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
    QUANTUM_RATE_LIMIT = 50  # Plus restrictif en production


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


def get_quantum_config() -> Dict[str, Any]:
    """
    Retourne la configuration quantique complète

    Returns:
        Configuration quantique avec tous les paramètres
    """
    return {
        "backend": settings.QISKIT_BACKEND,
        "max_qubits": settings.MAX_QUBITS,
        "default_shots": settings.QUANTUM_SHOTS,
        "optimization_level": settings.QUANTUM_OPTIMIZATION_LEVEL,
        "timeout": settings.QUANTUM_TIMEOUT,
        "rate_limit": settings.QUANTUM_RATE_LIMIT,
        "algorithms_enabled": {
            "grover": settings.ENABLE_GROVER,
            "superposition": settings.ENABLE_SUPERPOSITION,
            "entanglement": settings.ENABLE_ENTANGLEMENT,
            "solution_generation": settings.ENABLE_QUANTUM_SOLUTION_GEN,
            "hints_calculation": settings.ENABLE_QUANTUM_HINTS_CALC
        },
        "fallback_enabled": settings.QUANTUM_FALLBACK_ENABLED,
        "error_threshold": settings.QUANTUM_ERROR_THRESHOLD,
        "retry_attempts": settings.QUANTUM_RETRY_ATTEMPTS,
        "ibm_quantum": {
            "token_configured": bool(settings.IBM_QUANTUM_TOKEN),
            "hub": settings.IBM_QUANTUM_HUB,
            "group": settings.IBM_QUANTUM_GROUP,
            "project": settings.IBM_QUANTUM_PROJECT
        }
    }


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

    # Validation des limites quantiques
    if settings.QUANTUM_SHOTS < quantum_config.MIN_SHOTS or settings.QUANTUM_SHOTS > quantum_config.MAX_SHOTS:
        errors.append(f"QUANTUM_SHOTS doit être entre {quantum_config.MIN_SHOTS} et {quantum_config.MAX_SHOTS}")

    if settings.MAX_QUBITS > quantum_config.MAX_QUBITS:
        errors.append(f"MAX_QUBITS ne peut pas dépasser {quantum_config.MAX_QUBITS}")

    # Validation des clés secrètes en production
    if settings.ENVIRONMENT == "production":
        if settings.SECRET_KEY == "quantum-secret-key-change-in-production":
            errors.append("SECRET_KEY doit être changée en production")

        if settings.JWT_SECRET_KEY == "jwt-secret-key-change-in-production":
            errors.append("JWT_SECRET_KEY doit être changée en production")

    return errors


def get_feature_flags() -> Dict[str, bool]:
    """
    Retourne les flags de fonctionnalités quantiques

    Returns:
        Dictionnaire des fonctionnalités activées/désactivées
    """
    return {
        "quantum_backend_available": True,  # À déterminer dynamiquement
        "grover_algorithm": settings.ENABLE_GROVER,
        "superposition_analysis": settings.ENABLE_SUPERPOSITION,
        "entanglement_detection": settings.ENABLE_ENTANGLEMENT,
        "quantum_solution_generation": settings.ENABLE_QUANTUM_SOLUTION_GEN,
        "quantum_hints_calculation": settings.ENABLE_QUANTUM_HINTS_CALC,
        "fallback_algorithms": settings.QUANTUM_FALLBACK_ENABLED,
        "metrics_collection": settings.QUANTUM_METRICS_ENABLED,
        "detailed_logging": settings.QUANTUM_DETAILED_LOGGING,
        "rate_limiting": True,
        "security_validation": True
    }


# === EXPORTS ===

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
    "get_quantum_config",
    "validate_configuration",
    "get_feature_flags"
]