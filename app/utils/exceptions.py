"""
Exceptions personnalisées pour Quantum Mastermind
Hiérarchie d'exceptions robuste avec codes d'erreur et détails
"""
from typing import Any, Dict, Optional, List, Union
from uuid import UUID


# === EXCEPTION DE BASE ===

class BaseQuantumMastermindError(Exception):
    """Exception de base pour toutes les erreurs de Quantum Mastermind"""

    def __init__(
            self,
            message: str,
            error_code: Optional[str] = None,
            details: Optional[Dict[str, Any]] = None,
            status_code: int = 500
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}
        self.status_code = status_code

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'exception en dictionnaire"""
        return {
            'error': self.error_code,
            'message': self.message,
            'details': self.details,
            'status_code': self.status_code
        }


# === EXCEPTIONS D'AUTHENTIFICATION ===

class AuthenticationError(BaseQuantumMastermindError):
    """Erreur d'authentification"""

    def __init__(
            self,
            message: str = "Échec de l'authentification",
            user_identifier: Optional[str] = None
    ):
        super().__init__(message, "AUTHENTICATION_FAILED", status_code=401)
        if user_identifier:
            self.details['user_identifier'] = user_identifier


class AuthorizationError(BaseQuantumMastermindError):
    """Erreur d'autorisation"""

    def __init__(
            self,
            message: str = "Accès non autorisé",
            required_permission: Optional[str] = None,
            user_id: Optional[UUID] = None
    ):
        super().__init__(message, "AUTHORIZATION_FAILED", status_code=403)
        if required_permission:
            self.details['required_permission'] = required_permission
        if user_id:
            self.details['user_id'] = str(user_id)


class TokenExpiredError(AuthenticationError):
    """Token JWT expiré"""

    def __init__(
            self,
            message: str = "Token expiré",
            token_type: Optional[str] = None
    ):
        super().__init__(message, "TOKEN_EXPIRED")
        if token_type:
            self.details['token_type'] = token_type


class InvalidTokenError(AuthenticationError):
    """Token JWT invalide"""

    def __init__(
            self,
            message: str = "Token invalide",
            reason: Optional[str] = None
    ):
        super().__init__(message, "INVALID_TOKEN")
        if reason:
            self.details['reason'] = reason


class AccountLockedError(AuthenticationError):
    """Compte utilisateur verrouillé"""

    def __init__(
            self,
            message: str = "Compte verrouillé",
            unlock_time: Optional[str] = None,
            attempts_remaining: Optional[int] = None
    ):
        super().__init__(message, "ACCOUNT_LOCKED")
        if unlock_time:
            self.details['unlock_time'] = unlock_time
        if attempts_remaining is not None:
            self.details['attempts_remaining'] = attempts_remaining


class EmailNotVerifiedError(AuthenticationError):
    """Email non vérifié"""

    def __init__(
            self,
            message: str = "Email non vérifié",
            email: Optional[str] = None
    ):
        super().__init__(message, "EMAIL_NOT_VERIFIED")
        if email:
            self.details['email'] = email


# === EXCEPTIONS DE VALIDATION ===

class ValidationError(BaseQuantumMastermindError):
    """Erreur de validation de données"""

    def __init__(
            self,
            message: str,
            field: Optional[str] = None,
            value: Optional[Any] = None,
            validation_errors: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(message, "VALIDATION_ERROR", status_code=422)
        if field:
            self.details['field'] = field
        if value is not None:
            self.details['value'] = str(value)
        if validation_errors:
            self.details['validation_errors'] = validation_errors


class InvalidInputError(ValidationError):
    """Entrée invalide"""

    def __init__(
            self,
            message: str,
            field: Optional[str] = None,
            expected_type: Optional[str] = None,
            received_type: Optional[str] = None
    ):
        super().__init__(message, "INVALID_INPUT")
        if field:
            self.details['field'] = field
        if expected_type:
            self.details['expected_type'] = expected_type
        if received_type:
            self.details['received_type'] = received_type


class ConstraintViolationError(ValidationError):
    """Violation de contrainte"""

    def __init__(
            self,
            message: str,
            constraint: Optional[str] = None,
            table: Optional[str] = None
    ):
        super().__init__(message, "CONSTRAINT_VIOLATION")
        if constraint:
            self.details['constraint'] = constraint
        if table:
            self.details['table'] = table


# === EXCEPTIONS D'ENTITÉ ===

class EntityError(BaseQuantumMastermindError):
    """Erreur liée aux entités"""
    pass


class EntityNotFoundError(EntityError):
    """Entité non trouvée"""

    def __init__(
            self,
            message: str,
            entity_type: Optional[str] = None,
            entity_id: Optional[Union[str, UUID]] = None
    ):
        super().__init__(message, "ENTITY_NOT_FOUND", status_code=404)
        if entity_type:
            self.details['entity_type'] = entity_type
        if entity_id:
            self.details['entity_id'] = str(entity_id)


class EntityAlreadyExistsError(EntityError):
    """Entité existe déjà"""

    def __init__(
            self,
            message: str,
            entity_type: Optional[str] = None,
            conflicting_field: Optional[str] = None,
            conflicting_value: Optional[str] = None
    ):
        super().__init__(message, "ENTITY_ALREADY_EXISTS", status_code=409)
        if entity_type:
            self.details['entity_type'] = entity_type
        if conflicting_field:
            self.details['conflicting_field'] = conflicting_field
        if conflicting_value:
            self.details['conflicting_value'] = conflicting_value


class EntityStateError(EntityError):
    """État d'entité invalide pour l'opération"""

    def __init__(
            self,
            message: str,
            entity_type: Optional[str] = None,
            current_state: Optional[str] = None,
            required_state: Optional[str] = None
    ):
        super().__init__(message, "INVALID_ENTITY_STATE", status_code=409)
        if entity_type:
            self.details['entity_type'] = entity_type
        if current_state:
            self.details['current_state'] = current_state
        if required_state:
            self.details['required_state'] = required_state


# === EXCEPTIONS DE JEU ===

class GameError(BaseQuantumMastermindError):
    """Erreur de jeu générale"""
    pass


class GameNotFoundError(GameError):
    """Partie non trouvée"""

    def __init__(
            self,
            message: str = "Partie non trouvée",
            game_id: Optional[UUID] = None
    ):
        super().__init__(message, "GAME_NOT_FOUND", status_code=404)
        if game_id:
            self.details['game_id'] = str(game_id)


class GameNotActiveError(GameError):
    """Partie non active"""

    def __init__(
            self,
            message: str = "Partie non active",
            game_id: Optional[UUID] = None,
            current_status: Optional[str] = None
    ):
        super().__init__(message, "GAME_NOT_ACTIVE", status_code=409)
        if game_id:
            self.details['game_id'] = str(game_id)
        if current_status:
            self.details['current_status'] = current_status


class GameFullError(GameError):
    """Partie complète"""

    def __init__(
            self,
            message: str = "Partie complète",
            game_id: Optional[UUID] = None,
            max_players: Optional[int] = None,
            current_players: Optional[int] = None
    ):
        super().__init__(message, "GAME_FULL", status_code=409)
        if game_id:
            self.details['game_id'] = str(game_id)
        if max_players is not None:
            self.details['max_players'] = max_players
        if current_players is not None:
            self.details['current_players'] = current_players


class GameConfigurationError(GameError):
    """Configuration de jeu invalide"""

    def __init__(
            self,
            message: str,
            configuration_field: Optional[str] = None,
            invalid_value: Optional[Any] = None
    ):
        super().__init__(message, "INVALID_GAME_CONFIGURATION", status_code=422)
        if configuration_field:
            self.details['configuration_field'] = configuration_field
        if invalid_value is not None:
            self.details['invalid_value'] = str(invalid_value)


class InvalidMoveError(GameError):
    """Mouvement invalide"""

    def __init__(
            self,
            message: str,
            game_id: Optional[UUID] = None,
            player_id: Optional[UUID] = None,
            move_data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, "INVALID_MOVE", status_code=422)
        if game_id:
            self.details['game_id'] = str(game_id)
        if player_id:
            self.details['player_id'] = str(player_id)
        if move_data:
            self.details['move_data'] = move_data


class TurnViolationError(GameError):
    """Violation de tour"""

    def __init__(
            self,
            message: str = "Ce n'est pas votre tour",
            game_id: Optional[UUID] = None,
            current_player: Optional[UUID] = None,
            attempting_player: Optional[UUID] = None
    ):
        super().__init__(message, "TURN_VIOLATION", status_code=409)
        if game_id:
            self.details['game_id'] = str(game_id)
        if current_player:
            self.details['current_player'] = str(current_player)
        if attempting_player:
            self.details['attempting_player'] = str(attempting_player)


# === EXCEPTIONS QUANTIQUES ===

class QuantumError(BaseQuantumMastermindError):
    """Erreur quantique générale"""
    pass


class QuantumCircuitError(QuantumError):
    """Erreur de circuit quantique"""

    def __init__(
            self,
            message: str,
            circuit_name: Optional[str] = None,
            operation: Optional[str] = None
    ):
        super().__init__(message, "QUANTUM_CIRCUIT_ERROR")
        if circuit_name:
            self.details['circuit_name'] = circuit_name
        if operation:
            self.details['operation'] = operation


class QuantumBackendError(QuantumError):
    """Erreur de backend quantique"""

    def __init__(
            self,
            message: str,
            backend_name: Optional[str] = None,
            backend_error: Optional[str] = None
    ):
        super().__init__(message, "QUANTUM_BACKEND_ERROR")
        if backend_name:
            self.details['backend_name'] = backend_name
        if backend_error:
            self.details['backend_error'] = backend_error


class QuantumSimulationError(QuantumError):
    """Erreur de simulation quantique"""

    def __init__(
            self,
            message: str,
            shots: Optional[int] = None,
            qubits: Optional[int] = None
    ):
        super().__init__(message, "QUANTUM_SIMULATION_ERROR")
        if shots is not None:
            self.details['shots'] = shots
        if qubits is not None:
            self.details['qubits'] = qubits


# === EXCEPTIONS WEBSOCKET ===

class WebSocketError(BaseQuantumMastermindError):
    """Erreur WebSocket générale"""
    pass


class WebSocketConnectionError(WebSocketError):
    """Erreur de connexion WebSocket"""

    def __init__(
            self,
            message: str,
            connection_id: Optional[str] = None
    ):
        super().__init__(message, "WEBSOCKET_CONNECTION_ERROR")
        if connection_id:
            self.details['connection_id'] = connection_id


class WebSocketAuthenticationError(WebSocketError):
    """Erreur d'authentification WebSocket"""

    def __init__(
            self,
            message: str,
            connection_id: Optional[str] = None
    ):
        super().__init__(message, "WEBSOCKET_AUTH_ERROR")
        if connection_id:
            self.details['connection_id'] = connection_id


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
        super().__init__(message, "RATE_LIMIT_EXCEEDED", status_code=429)
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
        super().__init__(message, "FILE_NOT_FOUND", status_code=404)
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
        super().__init__(message, "FILE_PERMISSION_ERROR", status_code=403)
        if filename:
            self.details['filename'] = filename
        if operation:
            self.details['operation'] = operation


class FileSizeExceededError(FileError):
    """Taille de fichier dépassée"""

    def __init__(
            self,
            message: str,
            max_size: Optional[int] = None,
            actual_size: Optional[int] = None
    ):
        super().__init__(message, "FILE_SIZE_EXCEEDED", status_code=413)
        if max_size is not None:
            self.details['max_size'] = max_size
        if actual_size is not None:
            self.details['actual_size'] = actual_size


# === HELPERS POUR FASTAPI ===

def get_http_status_code(error: Exception) -> int:
    """
    Retourne le code de statut HTTP approprié pour une exception

    Args:
        error: Exception à traiter

    Returns:
        Code de statut HTTP
    """
    if isinstance(error, BaseQuantumMastermindError):
        return error.status_code

    # Mapping pour les exceptions Python standard
    error_type = type(error).__name__
    status_mapping = {
        'ValueError': 400,
        'TypeError': 400,
        'KeyError': 400,
        'AttributeError': 400,
        'NotImplementedError': 501,
        'PermissionError': 403,
        'TimeoutError': 408,
        'ConnectionError': 503,
        'FileNotFoundError': 404,
    }

    return status_mapping.get(error_type, 500)


def get_exception_details(error: Exception) -> Dict[str, Any]:
    """
    Extrait les détails d'une exception pour la réponse API

    Args:
        error: Exception à traiter

    Returns:
        Dictionnaire avec les détails de l'erreur
    """
    if isinstance(error, BaseQuantumMastermindError):
        return error.to_dict()

    return {
        'error': type(error).__name__,
        'message': str(error),
        'details': {},
        'status_code': get_http_status_code(error)
    }


# === DECORATEURS D'EXCEPTION ===

def handle_db_exceptions(func):
    """Décorateur pour gérer les exceptions de base de données"""
    from functools import wraps

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Ici on pourrait mapper les exceptions SQLAlchemy
            # vers nos exceptions personnalisées
            if "unique constraint" in str(e).lower():
                raise EntityAlreadyExistsError("Entité existe déjà")
            elif "foreign key constraint" in str(e).lower():
                raise ConstraintViolationError("Violation de contrainte de clé étrangère")
            else:
                raise

    return wrapper


def handle_quantum_exceptions(func):
    """Décorateur pour gérer les exceptions quantiques"""
    from functools import wraps

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Mapping des exceptions Qiskit
            if "circuit" in str(e).lower():
                raise QuantumCircuitError(str(e))
            elif "backend" in str(e).lower():
                raise QuantumBackendError(str(e))
            elif "simulation" in str(e).lower():
                raise QuantumSimulationError(str(e))
            else:
                raise QuantumError(str(e))

    return wrapper