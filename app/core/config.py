"""
Configuration globale de l'application Quantum Mastermind
Gestion sécurisée des variables d'environnement et paramètres
MODIFIÉ: Ajout des paramètres de configuration quantique étendus
CORRECTION: Validation MAX_QUBITS étendue pour supporter jusqu'à 50 qubits
"""
import os
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
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    PROJECT_NAME: str = "Quantum Mastermind API"
    VERSION: str = "1.0.0-quantum"
    DESCRIPTION: str = "Jeu de Mastermind avec informatique quantique"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # === SERVEUR ===
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    API_PREFIX: str = "/api/v1"
    WORKERS: int = int(os.getenv("WORKERS", "1"))
    MAX_REQUESTS: int = int(os.getenv("MAX_REQUESTS", "1000"))
    MAX_REQUESTS_JITTER: int = int(os.getenv("MAX_REQUESTS_JITTER", "100"))

    # === BASE DE DONNÉES ===
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_USER: str = os.getenv("DB_USER", "quantum_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "quantum_pass")
    DB_NAME: str = os.getenv("DB_NAME", "quantum_mastermind")
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")

    # Paramètres de connexion
    DB_ECHO: bool = DEBUG
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))

    ENABLE_REGISTRATION: bool = os.getenv("ENABLE_REGISTRATION", "true").lower() == "true"
    ENABLE_EMAIL_VERIFICATION: bool = os.getenv("ENABLE_EMAIL_VERIFICATION", "false").lower() == "true"

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
            path=f"/{values.get('DB_NAME') or ''}"
        ))

    # === REDIS ===
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_MAX_CONNECTIONS: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))

    # === SÉCURITÉ JWT ===
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    JWT_REFRESH_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7"))

    # === CORS ET SÉCURITÉ ===
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:4200",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:4200"
    ]
    TRUSTED_HOSTS: List[str] = ["localhost", "127.0.0.1"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError("CORS_ORIGINS doit être une liste ou une chaîne")

    @field_validator('TRUSTED_HOSTS', mode="before")
    @classmethod
    def parse_trusted_hosts(cls, v):
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v

    # === WEBHOOKS - NOUVELLEMENT ACTIVÉS ===
    ENABLE_WEBHOOKS: bool = os.getenv("ENABLE_WEBHOOKS", "true").lower() == "true"  # AJOUTÉ: Activation des webhooks
    WEBHOOK_BASE_URL: Optional[str] = os.getenv("WEBHOOK_BASE_URL")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", secrets.token_urlsafe(32))
    WEBHOOK_TIMEOUT: int = int(os.getenv("WEBHOOK_TIMEOUT", "30"))
    WEBHOOK_RETRY_ATTEMPTS: int = int(os.getenv("WEBHOOK_RETRY_ATTEMPTS", "3"))
    WEBHOOK_EVENTS_ENABLED: List[str] = [
        "game.created",
        "game.started",
        "game.finished",
        "player.joined",
        "player.left",
        "attempt.made",
        "hint.generated"
    ]


    # === CONFIGURATION QUANTIQUE ÉTENDUE ===

    # Backend quantique
    QISKIT_BACKEND: str = os.getenv("QISKIT_BACKEND", "qasm_simulator")
    QUANTUM_BACKEND_TYPE: str = os.getenv("QUANTUM_BACKEND_TYPE", "simulator")

    # Paramètres de performance quantique - CORRECTION: Limites étendues
    MAX_QUBITS: int = int(os.getenv("MAX_QUBITS", "10"))
    QUANTUM_SHOTS: int = int(os.getenv("QUANTUM_SHOTS", "1024"))
    QUANTUM_OPTIMIZATION_LEVEL: int = int(os.getenv("QUANTUM_OPTIMIZATION_LEVEL", "1"))
    QUANTUM_TIMEOUT: int = int(os.getenv("QUANTUM_TIMEOUT", "300"))

    # Limites quantiques pour la sécurité
    MAX_QUANTUM_SHOTS: int = int(os.getenv("MAX_QUANTUM_SHOTS", "8192"))
    MAX_QUANTUM_QUBITS: int = int(os.getenv("MAX_QUANTUM_QUBITS", "50"))  # AUGMENTÉ
    QUANTUM_RATE_LIMIT: int = int(os.getenv("QUANTUM_RATE_LIMIT", "100"))

    # Configuration des algorithmes quantiques
    ENABLE_GROVER: bool = os.getenv("ENABLE_GROVER", "true").lower() == "true"
    ENABLE_SUPERPOSITION: bool = os.getenv("ENABLE_SUPERPOSITION", "true").lower() == "true"
    ENABLE_ENTANGLEMENT: bool = os.getenv("ENABLE_ENTANGLEMENT", "true").lower() == "true"
    ENABLE_QUANTUM_SOLUTION_GEN: bool = os.getenv("ENABLE_QUANTUM_SOLUTION_GEN", "true").lower() == "true"
    ENABLE_QUANTUM_HINTS_CALC: bool = os.getenv("ENABLE_QUANTUM_HINTS_CALC", "true").lower() == "true"
    ENABLE_QUANTUM_HINTS: bool = os.getenv("ENABLE_QUANTUM_HINTS", "true").lower() == "true"

    # Fallback et tolérance aux pannes
    QUANTUM_FALLBACK_ENABLED: bool = os.getenv("QUANTUM_FALLBACK_ENABLED", "true").lower() == "true"
    QUANTUM_ERROR_THRESHOLD: int = int(os.getenv("QUANTUM_ERROR_THRESHOLD", "5"))
    QUANTUM_RETRY_ATTEMPTS: int = int(os.getenv("QUANTUM_RETRY_ATTEMPTS", "3"))

    # Logging et monitoring quantique
    QUANTUM_METRICS_ENABLED: bool = os.getenv("QUANTUM_METRICS_ENABLED", "true").lower() == "true"
    QUANTUM_DETAILED_LOGGING: bool = os.getenv("QUANTUM_DETAILED_LOGGING", "false").lower() == "true"

    # === CONFIGURATION IBM QUANTUM ===
    IBM_QUANTUM_TOKEN: Optional[str] = os.getenv("IBM_QUANTUM_TOKEN")
    IBM_QUANTUM_HUB: Optional[str] = os.getenv("IBM_QUANTUM_HUB", "ibm-q")
    IBM_QUANTUM_GROUP: Optional[str] = os.getenv("IBM_QUANTUM_GROUP", "open")
    IBM_QUANTUM_PROJECT: Optional[str] = os.getenv("IBM_QUANTUM_PROJECT", "main")

    # === EMAIL ===
    SMTP_TLS: bool = os.getenv("SMTP_TLS", "true").lower() == "true"
    SMTP_PORT: Optional[int] = int(os.getenv("SMTP_PORT", "587")) if os.getenv("SMTP_PORT") else None
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST")
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    EMAILS_FROM_EMAIL: Optional[str] = os.getenv("EMAILS_FROM_EMAIL")
    EMAILS_FROM_NAME: Optional[str] = os.getenv("EMAILS_FROM_NAME")

    @field_validator("EMAILS_FROM_NAME")
    @classmethod
    def get_project_name(cls, v: Optional[str], info) -> str:
        if not v:
            return info.data.get("PROJECT_NAME", "Quantum Mastermind")
        return v

    # === SÉCURITÉ AVANCÉE ===
    PASSWORD_MIN_LENGTH: int = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
    PASSWORD_REQUIRE_UPPERCASE: bool = os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true"
    PASSWORD_REQUIRE_LOWERCASE: bool = os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true"
    PASSWORD_REQUIRE_NUMBERS: bool = os.getenv("PASSWORD_REQUIRE_NUMBERS", "true").lower() == "true"
    PASSWORD_REQUIRE_SYMBOLS: bool = os.getenv("PASSWORD_REQUIRE_SYMBOLS", "false").lower() == "true"
    MAX_LOGIN_ATTEMPTS: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    LOCKOUT_DURATION_MINUTES: int = int(os.getenv("LOCKOUT_DURATION_MINUTES", "15"))

    # === RATE LIMITING ===
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # 1 heure
    RATE_LIMIT_STORAGE: str = os.getenv("RATE_LIMIT_STORAGE", "memory")  # ou "redis"

    # === WEBSOCKETS ===
    WS_MAX_CONNECTIONS: int = int(os.getenv("WS_MAX_CONNECTIONS", "1000"))
    WS_HEARTBEAT_INTERVAL: int = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))
    WS_CONNECTION_TIMEOUT: int = int(os.getenv("WS_CONNECTION_TIMEOUT", "60"))

    # === LOGGING ===
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")
    ENABLE_ACCESS_LOG: bool = os.getenv("ENABLE_ACCESS_LOG", "true").lower() == "true"

    # === MONITORING ===
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    METRICS_PATH: str = os.getenv("METRICS_PATH", "/metrics")
    HEALTH_CHECK_PATH: str = os.getenv("HEALTH_CHECK_PATH", "/health")

    # === VALIDATIONS ÉTENDUES ===

    @field_validator('QUANTUM_SHOTS')
    @classmethod
    def validate_quantum_shots(cls, v):
        if v < 100 or v > 8192:
            raise ValueError("QUANTUM_SHOTS doit être entre 100 et 8192")
        return v

    @field_validator('MAX_QUBITS')
    @classmethod
    def validate_max_qubits(cls, v):
        # CORRECTION: Limite étendue de 20 à 50 qubits
        if v < 1 or v > 50:
            raise ValueError("MAX_QUBITS doit être entre 1 et 50")
        return v

    @field_validator('QUANTUM_OPTIMIZATION_LEVEL')
    @classmethod
    def validate_optimization_level(cls, v):
        if v < 0 or v > 3:
            raise ValueError("QUANTUM_OPTIMIZATION_LEVEL doit être entre 0 et 3")
        return v

    @field_validator('QUANTUM_TIMEOUT')
    @classmethod
    def validate_quantum_timeout(cls, v):
        if v < 5 or v > 300:
            raise ValueError("QUANTUM_TIMEOUT doit être entre 5 et 300 secondes")
        return v

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

    # Rate limiting
    RATE_LIMIT_PER_MINUTE = 60
    RATE_LIMIT_PER_HOUR = 1000

    # Sessions
    SESSION_TIMEOUT_MINUTES = 30
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15

    # NOUVEAU: Sécurité quantique
    QUANTUM_OPERATIONS_PER_HOUR = 100
    QUANTUM_MAX_CONCURRENT_CIRCUITS = 5
    QUANTUM_CIRCUIT_COMPLEXITY_LIMIT = 50  # nombre de portes max


class QuantumConfig:
    """Configuration des fonctionnalités quantiques"""

    # Backends disponibles
    AVAILABLE_BACKENDS = [
        "qasm_simulator",
        "aer_simulator",
        "statevector_simulator",
        "unitary_simulator"
    ]

    # Limites par défaut - CORRECTION: Synchronisé avec Settings
    DEFAULT_QUBITS = 4
    MAX_QUBITS = 50  # AUGMENTÉ de 20 à 50
    DEFAULT_SHOTS = 1024
    MAX_SHOTS = 8192
    MIN_SHOTS = 100

    # Types d'algorithmes supportés
    SUPPORTED_ALGORITHMS = [
        "quantum_solution_generation",
        "quantum_hints_calculation",
        "grover_search",
        "superposition_analysis",
        "entanglement_detection",
        "quantum_fourier",
        "phase_estimation",
        "amplitude_amplification"
    ]

    # Types de hints quantiques
    QUANTUM_HINT_TYPES = [
        "grover",
        "superposition",
        "entanglement",
        "interference",
        "basic"
    ]

    # Configuration des hints
    HINT_COSTS = {
        "grover": 10,
        "superposition": 5,
        "entanglement": 15,
        "interference": 8,
        "grover_hint": 50,
        "superposition_hint": 25,
        "entanglement_hint": 35,
        "basic_hint": 10,
        "solution_generation": 0,  # Gratuit car automatique
        "hints_calculation": 0     # Gratuit car automatique
    }

    # Coûts des opérations quantiques (en points de jeu)
    QUANTUM_OPERATION_COSTS = {
        "grover_hint": 50,
        "superposition_hint": 25,
        "entanglement_hint": 35,
        "basic_hint": 10,
        "solution_generation": 0,
        "hints_calculation": 0
    }

    # Timeouts
    CIRCUIT_EXECUTION_TIMEOUT = 30
    ALGORITHM_TIMEOUT = 60
    QUANTUM_OPERATION_TIMEOUT = 60

    # Qualité et précision
    MINIMUM_FIDELITY = 0.8
    STATISTICAL_SIGNIFICANCE_THRESHOLD = 0.05
    CONVERGENCE_TOLERANCE = 1e-6


class GameConfig:
    """Configuration des paramètres de jeu"""

    # Paramètres par défaut
    DEFAULT_COMBINATION_LENGTH = 4
    DEFAULT_COLOR_COUNT = 6
    DEFAULT_AVAILABLE_COLORS = 6
    DEFAULT_MAX_ATTEMPTS = 10

    # Limites
    MIN_COMBINATION_LENGTH = 3
    MAX_COMBINATION_LENGTH = 8
    MIN_COLOR_COUNT = 4
    MAX_COLOR_COUNT = 10
    MIN_COLORS = 4
    MAX_COLORS = 10
    MIN_ATTEMPTS = 1
    MAX_ATTEMPTS_LIMIT = 20
    MAX_ATTEMPTS = 50
    MIN_TIME_LIMIT = 60  # secondes
    MAX_TIME_LIMIT = 3600  # 1 heure
    DEFAULT_TIME_LIMIT = None

    # Multijoueur
    MAX_PLAYERS_PER_GAME = 8
    DEFAULT_ROOM_CODE_LENGTH = 8

    # Scoring
    BASE_SCORE = 1000
    ATTEMPT_PENALTY = 50
    TIME_BONUS_MULTIPLIER = 0.1
    TIME_PENALTY_FACTOR = 10
    QUANTUM_BONUS_MULTIPLIER = 1.5

    # NOUVEAU: Configuration quantique spécifique au jeu
    QUANTUM_SCORE_MULTIPLIER = 1.5
    QUANTUM_HINT_BONUS = 10
    QUANTUM_SOLUTION_BONUS = 25
    QUANTUM_CALCULATION_BONUS = 5

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
    """Configuration WebSocket - ÉTENDUE avec gestion des webhooks"""

    # Connexions
    MAX_CONNECTIONS_PER_USER = 3
    CONNECTION_TIMEOUT = 60
    HEARTBEAT_INTERVAL = 30
    RECONNECT_ATTEMPTS = 5

    # Messages autorisés
    ALLOWED_MESSAGE_TYPES = [
        "authenticate", "join_room", "leave_room",
        "make_attempt", "get_hint", "chat_message",
        "heartbeat", "game_state_request",
        "webhook_notification"  # AJOUTÉ: Support des notifications webhook
    ]

    # Types de messages
    MESSAGE_TYPES = [
        "game_update",
        "player_joined",
        "player_left",
        "attempt_made",
        "game_finished",
        "quantum_hint_generated",
        "quantum_calculation_done",
        "webhook_event"  # AJOUTÉ: Événements webhook
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
    MAX_QUBITS = 30  # AUGMENTÉ de 15 à 30
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


def get_webhook_config() -> Dict[str, Any]:
    """
    Retourne la configuration des webhooks - NOUVELLE FONCTION

    Returns:
        Configuration webhook avec tous les paramètres
    """
    return {
        "enabled": settings.ENABLE_WEBHOOKS,
        "base_url": settings.WEBHOOK_BASE_URL,
        "secret": settings.WEBHOOK_SECRET,
        "timeout": settings.WEBHOOK_TIMEOUT,
        "retry_attempts": settings.WEBHOOK_RETRY_ATTEMPTS,
        "events_enabled": settings.WEBHOOK_EVENTS_ENABLED,
        "signature_validation": True,
        "rate_limit": {
            "max_requests_per_minute": 60,
            "burst_limit": 10
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

    # CORRECTION: Validation cohérente avec les nouvelles limites
    if settings.MAX_QUBITS > quantum_config.MAX_QUBITS:
        errors.append(f"MAX_QUBITS ne peut pas dépasser {quantum_config.MAX_QUBITS}")

    # Validation des limites raisonnables
    if settings.MAX_QUBITS > 50:  # Limite raisonnable pour la simulation
        errors.append("MAX_QUBITS ne devrait pas dépasser 50 pour les performances")

    # Validation des CORS en production
    if settings.ENVIRONMENT == "production":
        dangerous_origins = ["*", "http://localhost:3000"]
        for origin in settings.CORS_ORIGINS:
            if origin in dangerous_origins:
                errors.append(f"Origine CORS dangereuse en production: {origin}")

    # Validation des clés secrètes en production
    if settings.ENVIRONMENT == "production":
        if settings.SECRET_KEY == "quantum-secret-key-change-in-production":
            errors.append("SECRET_KEY doit être changée en production")

        if settings.JWT_SECRET_KEY == "jwt-secret-key-change-in-production":
            errors.append("JWT_SECRET_KEY doit être changée en production")

    # AJOUTÉ: Validation des webhooks
    if settings.ENABLE_WEBHOOKS:
        if not settings.WEBHOOK_SECRET or len(settings.WEBHOOK_SECRET) < 16:
            errors.append("WEBHOOK_SECRET doit faire au moins 16 caractères")

        if settings.WEBHOOK_TIMEOUT < 5 or settings.WEBHOOK_TIMEOUT > 300:
            errors.append("WEBHOOK_TIMEOUT doit être entre 5 et 300 secondes")

    return errors


def get_feature_flags() -> Dict[str, bool]:
    """
    Retourne les flags de fonctionnalités quantiques - ÉTENDU avec webhooks

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
        "security_validation": True,
        "webhooks_enabled": settings.ENABLE_WEBHOOKS,  # AJOUTÉ: Flag webhooks
        "websocket_notifications": True,
        "real_time_updates": True
    }


def is_development() -> bool:
    """Vérifie si on est en mode développement"""
    return settings.ENVIRONMENT.lower() == "development"


def is_production() -> bool:
    """Vérifie si on est en mode production"""
    return settings.ENVIRONMENT.lower() == "production"


def is_test() -> bool:
    """Vérifie si on est en mode test"""
    return settings.ENVIRONMENT.lower() == "test"


def startup_config_check():
    """Vérifie la configuration au démarrage de l'application - ÉTENDU avec webhooks"""
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

    # Log des fonctionnalités activées
    features = get_feature_flags()
    print("🔧 Fonctionnalités activées:")
    for feature, enabled in features.items():
        status = "✅" if enabled else "❌"
        print(f"  {status} {feature}")


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
    "get_quantum_config",
    "get_webhook_config",  # AJOUTÉ: Export webhook config
    "validate_configuration",
    "get_feature_flags",
    "is_development",
    "is_production",
    "is_test",
    "startup_config_check"
]