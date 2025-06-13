"""
Exceptions personnalisées pour Quantum Mastermind
Hiérarchie d'exceptions avec codes d'erreur et gestion centralisée
"""
from typing import Any, Dict, Optional


class BaseQuantumMastermindError(Exception):
    """Exception de base pour toutes les erreurs de l'application"""

    def __init__(
            self,
            message: str,
            error_code: Optional[str] = None,
            details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'exception en dictionnaire pour l'API"""
        return {
            'error': self.error_code,
            'message': self.message,
            'details': self.details
        }


# === EXCEPTIONS D'AUTHENTIFICATION ===

class AuthenticationError(BaseQuantumMastermindError):
    """Erreur d'authentification"""
    pass


class AuthorizationError(BaseQuantumMastermindError):
    """Erreur d'autorisation"""
    pass


class AccountLockedError(AuthenticationError):
    """Compte utilisateur verrouillé"""

    def __init__(self, message: str, locked_until: Optional[str] = None):
        super().__init__(message, "ACCOUNT_LOCKED")
        if locked_until:
            self.details['locked_until'] = locked_until


class EmailNotVerifiedError(AuthorizationError):
    """Email non vérifié"""

    def __init__(self, message: str = "Email non vérifié"):
        super().__init__(message, "EMAIL_NOT_VERIFIED")


class InvalidTokenError(AuthenticationError):
    """Token invalide ou expiré"""

    def __init__(self, message: str = "Token invalide"):
        super().__init__(message, "INVALID_TOKEN")


class TokenExpiredError(AuthenticationError):
    """Token expiré"""

    def __init__(self, message: str = "Token expiré"):
        super().__init__(message, "TOKEN_EXPIRED")


# === EXCEPTIONS DE VALIDATION ===

class ValidationError(BaseQuantumMastermindError):
    """Erreur de validation des données"""

    def __init__(
            self,
            message: str,
            field: Optional[str] = None,
            validation_errors: Optional[Dict[str, str]] = None
    ):
        super().__init__(message, "VALIDATION_ERROR")
        if field:
            self.details['field'] = field
        if validation_errors:
            self.details['validation_errors'] = validation_errors


class DuplicateEntityError(ValidationError):
    """Entité déjà existante"""

    def __init__(self, message: str, entity_type: Optional[str] = None):
        super().__init__(message, "DUPLICATE_ENTITY")
        if entity_type:
            self.details['entity_type'] = entity_type


class EntityNotFoundError(BaseQuantumMastermindError):
    """Entité non trouvée"""

    def __init__(
            self,
            message: str,
            entity_type: Optional[str] = None,
            entity_id: Optional[str] = None
    ):
        super().__init__(message, "ENTITY_NOT_FOUND")
        if entity_type:
            self.details['entity_type'] = entity_type
        if entity_id:
            self.details['entity_id'] = entity_id


# === EXCEPTIONS DE BASE DE DONNÉES ===

class DatabaseError(BaseQuantumMastermindError):
    """Erreur de base de données"""

    def __init__(self, message: str, operation: Optional[str] = None):
        super().__init__(message, "DATABASE_ERROR")
        if operation:
            self.details['operation'] = operation


class DatabaseConnectionError(DatabaseError):
    """Erreur de connexion à la base de données"""

    def __init__(self, message: str = "Impossible de se connecter à la base de données"):
        super().__init__(message, "DATABASE_CONNECTION_ERROR")


class DatabaseIntegrityError(DatabaseError):
    """Erreur d'intégrité de la base de données"""

    def __init__(
            self,
            message: str,
            constraint: Optional[str] = None
    ):
        super().__init__(message, "DATABASE_INTEGRITY_ERROR")
        if constraint:
            self.details['constraint'] = constraint


# === EXCEPTIONS DE JEU ===

class GameError(BaseQuantumMastermindError):
    """Erreur générale de jeu"""
    pass


class GameNotFoundError(EntityNotFoundError):
    """Partie non trouvée"""

    def __init__(self, game_id: Optional[str] = None, room_code: Optional[str] = None):
        message = "Partie non trouvée"
        super().__init__(message, "game", game_id)
        if room_code:
            self.details['room_code'] = room_code


class GameNotActiveError(GameError):
    """Partie non active"""

    def __init__(self, message: str = "La partie n'est pas active"):
        super().__init__(message, "GAME_NOT_ACTIVE")


class GameFullError(GameError):
    """Partie complète"""

    def __init__(self, message: str = "La partie est complète"):
        super().__init__(message, "GAME_FULL")


class GameAlreadyStartedError(GameError):
    """Partie déjà démarrée"""

    def __init__(self, message: str = "La partie a déjà démarré"):
        super().__init__(message, "GAME_ALREADY_STARTED")


class PlayerNotInGameError(GameError):
    """Joueur non dans la partie"""

    def __init__(
            self,
            message: str = "Joueur non trouvé dans cette partie",
            user_id: Optional[str] = None
    ):
        super().__init__(message, "PLAYER_NOT_IN_GAME")
        if user_id:
            self.details['user_id'] = user_id


class InvalidAttemptError(GameError):
    """Tentative invalide"""

    def __init__(
            self,
            message: str,
            attempt_data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, "INVALID_ATTEMPT")
        if attempt_data:
            self.details['attempt_data'] = attempt_data


class MaxAttemptsReachedError(GameError):
    """Nombre maximum de tentatives atteint"""

    def __init__(
            self,
            message: str = "Nombre maximum de tentatives atteint",
            max_attempts: Optional[int] = None,
            current_attempts: Optional[int] = None
    ):
        super().__init__(message, "MAX_ATTEMPTS_REACHED")
        if max_attempts:
            self.details['max_attempts'] = max_attempts
        if current_attempts:
            self.details['current_attempts'] = current_attempts


# === EXCEPTIONS QUANTIQUES ===

class QuantumError(BaseQuantumMastermindError):
    """Erreur quantique générale"""
    pass


class QuantumBackendError(QuantumError):
    """Erreur du backend quantique"""

    def __init__(
            self,
            message: str,
            backend_name: Optional[str] = None
    ):
        super().__init__(message, "QUANTUM_BACKEND_ERROR")
        if backend_name:
            self.details['backend_name'] = backend_name


class QuantumCircuitError(QuantumError):
    """Erreur de circuit quantique"""

    def __init__(
            self,
            message: str,
            circuit_info: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, "QUANTUM_CIRCUIT_ERROR")
        if circuit_info:
            self.details['circuit_info'] = circuit_info


class QuantumMeasurementError(QuantumError):
    """Erreur de mesure quantique"""

    def __init__(
            self,
            message: str,
            qubit_index: Optional[int] = None
    ):
        super().__init__(message, "QUANTUM_MEASUREMENT_ERROR")
        if qubit_index is not None:
            self.details['qubit_index'] = qubit_index


class QuantumResourceExhaustedError(QuantumError):
    """Ressources quantiques épuisées"""

    def __init__(
            self,
            message: str = "Ressources quantiques épuisées",
            resource_type: Optional[str] = None
    ):
        super().__init__(message, "QUANTUM_RESOURCE_EXHAUSTED")
        if resource_type:
            self.details['resource_type'] = resource_type


# === EXCEPTIONS WEBSOCKET ===

class WebSocketError(BaseQuantumMastermindError):
    """Erreur WebSocket générale"""
    pass


class WebSocketConnectionError(WebSocketError):
    """Erreur de connexion WebSocket"""

    def __init__(
            self,
            message: str = "Erreur de connexion WebSocket",
            connection_id: Optional[str] = None
    ):
        super().__init__(message, "WEBSOCKET_CONNECTION_ERROR")
        if connection_id:
            self.details['connection_id'] = connection_id


class WebSocketAuthenticationError(WebSocketError):
    """Erreur d'authentification WebSocket"""

    def __init__(self, message: str = "Authentification WebSocket échouée"):
        super().__init__(message, "WEBSOCKET_AUTH_ERROR")


class WebSocketMessageError(WebSocketError):
    """Erreur de message WebSocket"""

    def __init__(
            self,
            message: str,
            message_type: Optional[str] = None
    ):
        super().__init__(message, "WEBSOCKET_MESSAGE_ERROR")
        if message_type:
            self.details['message_type'] = message_type


# === EXCEPTIONS DE CONFIGURATION ===

class ConfigurationError(BaseQuantumMastermindError):
    """Erreur de configuration"""

    def __init__(
            self,
            message: str,
            config_key: Optional[str] = None
    ):
        super().__init__(message, "CONFIGURATION_ERROR")
        if config_key:
            self.details['config_key'] = config_key


class MissingEnvironmentVariableError(ConfigurationError):
    """Variable d'environnement manquante"""

    def __init__(
            self,
            variable_name: str,
            message: Optional[str] = None
    ):
        message = message or f"Variable d'environnement manquante: {variable_name}"
        super().__init__(message, "MISSING_ENV_VAR")
        self.details['variable_name'] = variable_name


# === EXCEPTIONS DE RATE LIMITING ===

class RateLimitExceededError(BaseQuantumMastermindError):
    """Limite de taux dépassée"""

    def __init__(
            self,
            message: str = "Trop de requêtes",
            retry_after: Optional[int] = None
    ):
        super().__init__(message, "RATE_LIMIT_EXCEEDED")
        if retry_after:
            self.details['retry_after'] = retry_after


# === EXCEPTIONS DE FICHIER ===

class FileError(BaseQuantumMastermindError):
    """Erreur de fichier générale"""
    pass


class FileNotFoundError(FileError):
    """Fichier non trouvé"""

    def __init__(
            self,
            message: str,
            filename: Optional[str] = None
    ):
        super().__init__(message, "FILE_NOT_FOUND")
        if filename:
            self.details['filename'] = filename


class FilePermissionError(FileError):
    """Erreur de permissions de fichier"""

    def __init__(
            self,
            message: str,
            filename: Optional[str] = None,
            operation: Optional[str] = None
    ):
        super().__init__(message, "FILE_PERMISSION_ERROR")
        if filename:
            self.details['filename'] = filename
        if operation:
            self.details['operation'] = operation


# === EXCEPTIONS EXTERNES ===

class ExternalServiceError(BaseQuantumMastermindError):
    """Erreur de service externe"""

    def __init__(
            self,
            message: str,
            service_name: Optional[str] = None,
            status_code: Optional[int] = None
    ):
        super().__init__(message, "EXTERNAL_SERVICE_ERROR")
        if service_name:
            self.details['service_name'] = service_name
        if status_code:
            self.details['status_code'] = status_code


class EmailServiceError(ExternalServiceError):
    """Erreur du service email"""

    def __init__(
            self,
            message: str = "Erreur du service email",
            recipient: Optional[str] = None
    ):
        super().__init__(message, "email_service")
        if recipient:
            self.details['recipient'] = recipient


# === EXCEPTIONS DE VALIDATION MÉTIER ===

class BusinessRuleViolationError(BaseQuantumMastermindError):
    """Violation de règle métier"""

    def __init__(
            self,
            message: str,
            rule_name: Optional[str] = None,
            rule_parameters: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, "BUSINESS_RULE_VIOLATION")
        if rule_name:
            self.details['rule_name'] = rule_name
        if rule_parameters:
            self.details['rule_parameters'] = rule_parameters


# === UTILITAIRES D'EXCEPTION ===

def get_exception_details(exception: Exception) -> Dict[str, Any]:
    """
    Extrait les détails d'une exception pour le logging

    Args:
        exception: Exception à analyser

    Returns:
        Dictionnaire avec les détails de l'exception
    """
    if isinstance(exception, BaseQuantumMastermindError):
        return exception.to_dict()

    return {
        'error': exception.__class__.__name__,
        'message': str(exception),
        'details': {}
    }


def is_retryable_error(exception: Exception) -> bool:
    """
    Détermine si une erreur peut être retry

    Args:
        exception: Exception à vérifier

    Returns:
        True si l'erreur peut être retry
    """
    retryable_errors = (
        DatabaseConnectionError,
        ExternalServiceError,
        QuantumBackendError
    )

    return isinstance(exception, retryable_errors)


def get_http_status_code(exception: Exception) -> int:
    """
    Retourne le code de statut HTTP approprié pour une exception

    Args:
        exception: Exception à analyser

    Returns:
        Code de statut HTTP
    """
    status_codes = {
        # Authentification et autorisation
        AuthenticationError: 401,
        AuthorizationError: 403,
        AccountLockedError: 423,
        EmailNotVerifiedError: 403,
        InvalidTokenError: 401,
        TokenExpiredError: 401,

        # Validation et entités
        ValidationError: 400,
        DuplicateEntityError: 409,
        EntityNotFoundError: 404,

        # Base de données
        DatabaseError: 500,
        DatabaseConnectionError: 503,
        DatabaseIntegrityError: 409,

        # Jeu
        GameNotFoundError: 404,
        GameNotActiveError: 409,
        GameFullError: 409,
        GameAlreadyStartedError: 409,
        PlayerNotInGameError: 404,
        InvalidAttemptError: 400,
        MaxAttemptsReachedError: 409,

        # Quantique
        QuantumError: 500,
        QuantumBackendError: 503,
        QuantumCircuitError: 400,
        QuantumMeasurementError: 400,
        QuantumResourceExhaustedError: 429,

        # WebSocket
        WebSocketError: 500,
        WebSocketConnectionError: 503,
        WebSocketAuthenticationError: 401,
        WebSocketMessageError: 400,

        # Configuration
        ConfigurationError: 500,
        MissingEnvironmentVariableError: 500,

        # Rate limiting
        RateLimitExceededError: 429,

        # Fichiers
        FileNotFoundError: 404,
        FilePermissionError: 403,

        # Services externes
        ExternalServiceError: 503,
        EmailServiceError: 503,

        # Règles métier
        BusinessRuleViolationError: 422
    }

    return status_codes.get(type(exception), 500)