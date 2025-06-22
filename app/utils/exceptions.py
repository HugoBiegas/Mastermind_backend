"""
Exceptions personnalisées pour Quantum Mastermind
COMPLET: Toutes les exceptions utilisées dans le projet avec gestion d'erreurs robuste
"""
from typing import Any, Dict, Optional, List
from uuid import UUID
from fastapi import HTTPException


# =====================================================
# EXCEPTION DE BASE
# =====================================================

class BaseQuantumMastermindError(Exception):
    """Exception de base pour Quantum Mastermind"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class GameNotActiveError(BaseQuantumMastermindError):
    """Erreur lorsque le jeu n'est pas actif"""

    def __init__(self, game_id: UUID):
        super().__init__(
            f"Le jeu {game_id} n'est pas actif",
            error_code="GAME_NOT_ACTIVE",
            details={"game_id": str(game_id)}
        )
# =====================================================
# EXCEPTIONS GÉNÉRALES
# =====================================================

class ValidationError(BaseQuantumMastermindError):
    """Erreur de validation des données"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        validation_errors: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(
            message,
            error_code="VALIDATION_ERROR",
            details={
                "field": field,
                "value": str(value) if value is not None else None,
                "validation_errors": validation_errors
            }
        )


class AuthenticationError(BaseQuantumMastermindError):
    """Erreur d'authentification"""

    def __init__(self, message: str = "Erreur d'authentification", user_identifier: Optional[str] = None):
        super().__init__(
            message,
            error_code="AUTHENTICATION_ERROR",
            details={"user_identifier": user_identifier} if user_identifier else {}
        )


class AuthorizationError(BaseQuantumMastermindError):
    """Erreur d'autorisation"""

    def __init__(self, message: str = "Accès non autorisé", required_permission: Optional[str] = None):
        super().__init__(
            message,
            error_code="AUTHORIZATION_ERROR",
            details={"required_permission": required_permission} if required_permission else {}
        )


class EntityNotFoundError(BaseQuantumMastermindError):
    """Entité non trouvée"""

    def __init__(self, message: str, entity_type: Optional[str] = None, entity_id: Optional[str] = None):
        super().__init__(
            message,
            error_code="ENTITY_NOT_FOUND",
            details={"entity_type": entity_type, "entity_id": entity_id}
        )


class EntityAlreadyExistsError(BaseQuantumMastermindError):
    """Entité déjà existante"""

    def __init__(
        self,
        message: str,
        entity_type: Optional[str] = None,
        conflicting_field: Optional[str] = None,
        conflicting_value: Optional[str] = None
    ):
        super().__init__(
            message,
            error_code="ENTITY_ALREADY_EXISTS",
            details={
                "entity_type": entity_type,
                "conflicting_field": conflicting_field,
                "conflicting_value": conflicting_value
            }
        )


class DatabaseError(BaseQuantumMastermindError):
    """Erreur de base de données"""

    def __init__(self, message: str, operation: Optional[str] = None):
        super().__init__(
            message,
            error_code="DATABASE_ERROR",
            details={"operation": operation} if operation else {}
        )


class ServiceUnavailableError(BaseQuantumMastermindError):
    """Service indisponible"""

    def __init__(self, message: str = "Service temporairement indisponible", service_name: Optional[str] = None):
        super().__init__(
            message,
            error_code="SERVICE_UNAVAILABLE",
            details={"service_name": service_name} if service_name else {}
        )


class ConstraintViolationError(BaseQuantumMastermindError):
    """Violation de contrainte"""

    def __init__(self, message: str, constraint: Optional[str] = None, table: Optional[str] = None):
        super().__init__(
            message,
            error_code="CONSTRAINT_VIOLATION",
            details={"constraint": constraint, "table": table}
        )


# =====================================================
# EXCEPTIONS D'AUTHENTIFICATION SPÉCIFIQUES
# =====================================================

class AccountLockedError(AuthenticationError):
    """Compte verrouillé"""

    def __init__(self, message: str = "Compte verrouillé", unlock_time: Optional[str] = None, attempts_remaining: Optional[int] = None):
        super().__init__(message)
        self.error_code = "ACCOUNT_LOCKED"
        if unlock_time:
            self.details["unlock_time"] = unlock_time
        if attempts_remaining is not None:
            self.details["attempts_remaining"] = attempts_remaining


class EmailNotVerifiedError(AuthenticationError):
    """Email non vérifié"""

    def __init__(self, message: str = "Email non vérifié", email: Optional[str] = None):
        super().__init__(message)
        self.error_code = "EMAIL_NOT_VERIFIED"
        if email:
            self.details["email"] = email


class InvalidCredentialsError(AuthenticationError):
    """Identifiants invalides"""

    def __init__(self, message: str = "Identifiants invalides"):
        super().__init__(message)
        self.error_code = "INVALID_CREDENTIALS"


class TokenExpiredError(AuthenticationError):
    """Token expiré"""

    def __init__(self, message: str = "Token expiré", token_type: str = "access_token"):
        super().__init__(message)
        self.error_code = "TOKEN_EXPIRED"
        self.details["token_type"] = token_type


class InvalidTokenError(AuthenticationError):
    """Token invalide"""

    def __init__(self, message: str = "Token invalide", token_type: str = "access_token"):
        super().__init__(message)
        self.error_code = "INVALID_TOKEN"
        self.details["token_type"] = token_type


# =====================================================
# EXCEPTIONS SPÉCIFIQUES AU JEU
# =====================================================

class GameError(BaseQuantumMastermindError):
    """Erreur générale de jeu"""

    def __init__(self, message: str, game_id: Optional[str] = None):
        super().__init__(
            message,
            error_code="GAME_ERROR",
            details={"game_id": game_id} if game_id else {}
        )


class GameNotFoundError(GameError):
    """Partie non trouvée"""

    def __init__(self, game_id: str):
        super().__init__(f"Partie {game_id} introuvable", game_id)
        self.error_code = "GAME_NOT_FOUND"


class GameFullError(GameError):
    """Partie complète"""

    def __init__(self, room_code: str, max_players: int):
        super().__init__(f"La partie {room_code} est complète ({max_players} joueurs max)")
        self.error_code = "GAME_FULL"
        self.details.update({"room_code": room_code, "max_players": max_players})


class GameAlreadyStartedError(GameError):
    """Partie déjà commencée"""

    def __init__(self, room_code: str):
        super().__init__(f"La partie {room_code} a déjà commencé")
        self.error_code = "GAME_ALREADY_STARTED"
        self.details["room_code"] = room_code


class GameNotStartedError(GameError):
    """Partie pas encore commencée"""

    def __init__(self, room_code: str):
        super().__init__(f"La partie {room_code} n'a pas encore commencé")
        self.error_code = "GAME_NOT_STARTED"
        self.details["room_code"] = room_code


class GameFinishedError(GameError):
    """Partie terminée"""

    def __init__(self, room_code: str):
        super().__init__(f"La partie {room_code} est terminée")
        self.error_code = "GAME_FINISHED"
        self.details["room_code"] = room_code


class InvalidGameStateError(GameError):
    """État de jeu invalide"""

    def __init__(self, current_state: str, expected_state: str):
        super().__init__(f"État de jeu invalide: {current_state}, attendu: {expected_state}")
        self.error_code = "INVALID_GAME_STATE"
        self.details.update({"current_state": current_state, "expected_state": expected_state})


class InvalidMoveError(GameError):
    """Mouvement invalide"""

    def __init__(self, reason: str):
        super().__init__(f"Mouvement invalide: {reason}")
        self.error_code = "INVALID_MOVE"
        self.details["reason"] = reason


class MaxAttemptsReachedError(GameError):
    """Nombre maximum de tentatives atteint"""

    def __init__(self, max_attempts: int):
        super().__init__(f"Nombre maximum de tentatives atteint ({max_attempts})")
        self.error_code = "MAX_ATTEMPTS_REACHED"
        self.details["max_attempts"] = max_attempts


# =====================================================
# EXCEPTIONS MULTIJOUEUR
# =====================================================

class MultiplayerError(BaseQuantumMastermindError):
    """Erreur générale multijoueur"""

    def __init__(self, message: str, room_code: Optional[str] = None):
        super().__init__(
            message,
            error_code="MULTIPLAYER_ERROR",
            details={"room_code": room_code} if room_code else {}
        )


class RoomNotFoundError(MultiplayerError):
    """Room non trouvée"""

    def __init__(self, room_code: str):
        super().__init__(f"Room {room_code} introuvable", room_code)
        self.error_code = "ROOM_NOT_FOUND"


class RoomCodeAlreadyExistsError(MultiplayerError):
    """Code de room déjà existant"""

    def __init__(self, room_code: str):
        super().__init__(f"Le code de room {room_code} existe déjà", room_code)
        self.error_code = "ROOM_CODE_EXISTS"


class PlayerNotInRoomError(MultiplayerError):
    """Joueur pas dans la room"""

    def __init__(self, user_id: str, room_code: str):
        super().__init__(f"Le joueur {user_id} n'est pas dans la room {room_code}", room_code)
        self.error_code = "PLAYER_NOT_IN_ROOM"
        self.details["user_id"] = user_id


class PlayerAlreadyInRoomError(MultiplayerError):
    """Joueur déjà dans la room"""

    def __init__(self, user_id: str, room_code: str):
        super().__init__(f"Le joueur {user_id} est déjà dans la room {room_code}", room_code)
        self.error_code = "PLAYER_ALREADY_IN_ROOM"
        self.details["user_id"] = user_id


class NotRoomHostError(MultiplayerError):
    """N'est pas l'hôte de la room"""

    def __init__(self, user_id: str, room_code: str):
        super().__init__(f"Le joueur {user_id} n'est pas l'hôte de la room {room_code}", room_code)
        self.error_code = "NOT_ROOM_HOST"
        self.details["user_id"] = user_id


class InsufficientPlayersError(MultiplayerError):
    """Pas assez de joueurs"""

    def __init__(self, current_players: int, min_players: int):
        super().__init__(f"Pas assez de joueurs ({current_players}/{min_players} minimum)")
        self.error_code = "INSUFFICIENT_PLAYERS"
        self.details.update({"current_players": current_players, "min_players": min_players})


class PlayerNotReadyError(MultiplayerError):
    """Joueur pas prêt"""

    def __init__(self, user_id: str):
        super().__init__(f"Le joueur {user_id} n'est pas prêt")
        self.error_code = "PLAYER_NOT_READY"
        self.details["user_id"] = user_id


class MastermindNotActiveError(MultiplayerError):
    """Mastermind pas actif"""

    def __init__(self, mastermind_number: int):
        super().__init__(f"Le mastermind {mastermind_number} n'est pas actif")
        self.error_code = "MASTERMIND_NOT_ACTIVE"
        self.details["mastermind_number"] = mastermind_number


class MastermindCompletedError(MultiplayerError):
    """Mastermind déjà complété"""

    def __init__(self, mastermind_number: int):
        super().__init__(f"Le mastermind {mastermind_number} est déjà complété")
        self.error_code = "MASTERMIND_COMPLETED"
        self.details["mastermind_number"] = mastermind_number


# =====================================================
# EXCEPTIONS WEBSOCKET
# =====================================================

class WebSocketError(BaseQuantumMastermindError):
    """Erreur WebSocket"""

    def __init__(self, message: str, connection_id: Optional[str] = None):
        super().__init__(
            message,
            error_code="WEBSOCKET_ERROR",
            details={"connection_id": connection_id} if connection_id else {}
        )


class WebSocketConnectionError(WebSocketError):
    """Erreur de connexion WebSocket"""

    def __init__(self, reason: str):
        super().__init__(f"Erreur de connexion WebSocket: {reason}")
        self.error_code = "WEBSOCKET_CONNECTION_ERROR"
        self.details["reason"] = reason


class WebSocketMessageError(WebSocketError):
    """Erreur de message WebSocket"""

    def __init__(self, message_type: str, reason: str):
        super().__init__(f"Erreur message WebSocket {message_type}: {reason}")
        self.error_code = "WEBSOCKET_MESSAGE_ERROR"
        self.details.update({"message_type": message_type, "reason": reason})


# =====================================================
# EXCEPTIONS QUANTIQUES
# =====================================================

class QuantumError(BaseQuantumMastermindError):
    """Erreur quantique générale"""

    def __init__(self, message: str, backend: Optional[str] = None):
        super().__init__(
            message,
            error_code="QUANTUM_ERROR",
            details={"backend": backend} if backend else {}
        )


class QuantumServiceUnavailableError(QuantumError):
    """Service quantique indisponible"""

    def __init__(self):
        super().__init__("Le service quantique n'est pas disponible")
        self.error_code = "QUANTUM_SERVICE_UNAVAILABLE"


class QuantumSimulationError(QuantumError):
    """Erreur de simulation quantique"""

    def __init__(self, backend: str, reason: str):
        super().__init__(f"Erreur simulation quantique sur {backend}: {reason}", backend)
        self.error_code = "QUANTUM_SIMULATION_ERROR"
        self.details["reason"] = reason


class QuantumHintError(QuantumError):
    """Erreur d'indice quantique"""

    def __init__(self, hint_type: str, reason: str):
        super().__init__(f"Erreur indice quantique {hint_type}: {reason}")
        self.error_code = "QUANTUM_HINT_ERROR"
        self.details.update({"hint_type": hint_type, "reason": reason})


class InsufficientQuantumResourcesError(QuantumError):
    """Ressources quantiques insuffisantes"""

    def __init__(self, required_qubits: int, available_qubits: int):
        super().__init__(f"Ressources quantiques insuffisantes: {required_qubits} qubits requis, {available_qubits} disponibles")
        self.error_code = "INSUFFICIENT_QUANTUM_RESOURCES"
        self.details.update({"required_qubits": required_qubits, "available_qubits": available_qubits})


# =====================================================
# EXCEPTIONS D'OBJETS ET EFFETS
# =====================================================

class ItemError(BaseQuantumMastermindError):
    """Erreur d'objet de jeu"""

    def __init__(self, message: str, item_type: Optional[str] = None):
        super().__init__(
            message,
            error_code="ITEM_ERROR",
            details={"item_type": item_type} if item_type else {}
        )


class ItemNotFoundError(ItemError):
    """Objet non trouvé"""

    def __init__(self, item_type: str):
        super().__init__(f"Objet {item_type} introuvable", item_type)
        self.error_code = "ITEM_NOT_FOUND"


class ItemNotAvailableError(ItemError):
    """Objet non disponible"""

    def __init__(self, item_type: str, reason: str):
        super().__init__(f"Objet {item_type} non disponible: {reason}", item_type)
        self.error_code = "ITEM_NOT_AVAILABLE"
        self.details["reason"] = reason


class ItemAlreadyUsedError(ItemError):
    """Objet déjà utilisé"""

    def __init__(self, item_type: str):
        super().__init__(f"Objet {item_type} déjà utilisé", item_type)
        self.error_code = "ITEM_ALREADY_USED"


class InvalidItemTargetError(ItemError):
    """Cible d'objet invalide"""

    def __init__(self, item_type: str, target_user_id: str):
        super().__init__(f"Cible invalide pour l'objet {item_type}: {target_user_id}", item_type)
        self.error_code = "INVALID_ITEM_TARGET"
        self.details["target_user_id"] = target_user_id


class EffectError(BaseQuantumMastermindError):
    """Erreur d'effet de jeu"""

    def __init__(self, message: str, effect_id: Optional[str] = None):
        super().__init__(
            message,
            error_code="EFFECT_ERROR",
            details={"effect_id": effect_id} if effect_id else {}
        )


class EffectNotFoundError(EffectError):
    """Effet non trouvé"""

    def __init__(self, effect_id: str):
        super().__init__(f"Effet {effect_id} introuvable", effect_id)
        self.error_code = "EFFECT_NOT_FOUND"


class EffectExpiredError(EffectError):
    """Effet expiré"""

    def __init__(self, effect_id: str):
        super().__init__(f"Effet {effect_id} expiré", effect_id)
        self.error_code = "EFFECT_EXPIRED"


# =====================================================
# UTILITAIRES POUR LA GESTION D'ERREURS
# =====================================================

def get_http_status_code(exception: BaseQuantumMastermindError) -> int:
    """Retourne le code de statut HTTP approprié pour une exception"""

    # Erreurs 400 - Bad Request
    if isinstance(exception, (
        ValidationError, InvalidMoveError, MaxAttemptsReachedError,
        GameAlreadyStartedError, GameNotStartedError, GameFinishedError,
        InvalidGameStateError, PlayerAlreadyInRoomError, InsufficientPlayersError,
        PlayerNotReadyError, MastermindNotActiveError, MastermindCompletedError,
        ItemNotAvailableError, ItemAlreadyUsedError, InvalidItemTargetError
    )):
        return 400

    # Erreurs 401 - Unauthorized
    if isinstance(exception, (
        AuthenticationError, InvalidCredentialsError,
        TokenExpiredError, InvalidTokenError
    )):
        return 401

    # Erreurs 403 - Forbidden
    if isinstance(exception, (AuthorizationError, NotRoomHostError, AccountLockedError)):
        return 403

    # Erreurs 404 - Not Found
    if isinstance(exception, (
        EntityNotFoundError, GameNotFoundError, RoomNotFoundError,
        PlayerNotInRoomError, ItemNotFoundError, EffectNotFoundError
    )):
        return 404

    # Erreurs 409 - Conflict
    if isinstance(exception, (GameFullError, RoomCodeAlreadyExistsError, EntityAlreadyExistsError)):
        return 409

    # Erreurs 422 - Unprocessable Entity
    if isinstance(exception, (ConstraintViolationError,)):
        return 422

    # Erreurs 503 - Service Unavailable
    if isinstance(exception, (ServiceUnavailableError, QuantumServiceUnavailableError)):
        return 503

    # Par défaut: 500 - Internal Server Error
    return 500


def get_exception_details(exception: BaseQuantumMastermindError) -> Dict[str, Any]:
    """Retourne les détails structurés d'une exception"""

    return {
        "error_type": exception.__class__.__name__,
        "message": exception.message,
        "error_code": exception.error_code,
        "details": exception.details,
        "http_status": get_http_status_code(exception)
    }


def create_error_response(exception: BaseQuantumMastermindError) -> Dict[str, Any]:
    """Crée une réponse d'erreur standardisée"""

    details = get_exception_details(exception)

    return {
        "success": False,
        "error": {
            "type": details["error_type"],
            "message": details["message"],
            "code": details["error_code"],
            "details": details["details"]
        },
        "data": None,
        "timestamp": None  # À définir par l'appelant
    }


def create_http_exception_from_error(error: BaseQuantumMastermindError) -> HTTPException:
    """Crée une HTTPException à partir d'une exception métier"""

    return HTTPException(
        status_code=get_http_status_code(error),
        detail={
            "error_code": error.error_code,
            "message": error.message,
            "details": error.details
        }
    )


# =====================================================
# DECORATEURS POUR LA GESTION D'ERREURS
# =====================================================

from functools import wraps
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)

def handle_multiplayer_errors(func: Callable) -> Callable:
    """Décorateur pour gérer les erreurs multijoueur"""

    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except BaseQuantumMastermindError:
            # Relancer les erreurs connues
            raise
        except Exception as e:
            # Convertir les erreurs inconnues en erreurs génériques
            logger.error(f"Erreur inattendue dans {func.__name__}: {e}")
            raise MultiplayerError(
                f"Erreur inattendue: {str(e)}",
            )

    return wrapper


def handle_quantum_errors(func: Callable) -> Callable:
    """Décorateur pour gérer les erreurs quantiques"""

    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except BaseQuantumMastermindError:
            raise
        except Exception as e:
            logger.error(f"Erreur quantique dans {func.__name__}: {e}")
            raise QuantumError(f"Erreur quantique: {str(e)}")

    return wrapper


# =====================================================
# EXPORTS
# =====================================================

__all__ = [
    # Exceptions de base
    "BaseQuantumMastermindError",
    "GameNotActiveError",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "EntityNotFoundError",
    "EntityAlreadyExistsError",
    "DatabaseError",
    "ServiceUnavailableError",
    "ConstraintViolationError",

    # Exceptions d'authentification spécifiques
    "AccountLockedError",
    "EmailNotVerifiedError",
    "InvalidCredentialsError",
    "TokenExpiredError",
    "InvalidTokenError",

    # Exceptions de jeu
    "GameError",
    "GameNotFoundError",
    "GameFullError",
    "GameAlreadyStartedError",
    "GameNotStartedError",
    "GameFinishedError",
    "InvalidGameStateError",
    "InvalidMoveError",
    "MaxAttemptsReachedError",

    # Exceptions multijoueur
    "MultiplayerError",
    "RoomNotFoundError",
    "RoomCodeAlreadyExistsError",
    "PlayerNotInRoomError",
    "PlayerAlreadyInRoomError",
    "NotRoomHostError",
    "InsufficientPlayersError",
    "PlayerNotReadyError",
    "MastermindNotActiveError",
    "MastermindCompletedError",

    # Exceptions WebSocket
    "WebSocketError",
    "WebSocketConnectionError",
    "WebSocketMessageError",

    # Exceptions quantiques
    "QuantumError",
    "QuantumServiceUnavailableError",
    "QuantumSimulationError",
    "QuantumHintError",
    "InsufficientQuantumResourcesError",

    # Exceptions objets/effets
    "ItemError",
    "ItemNotFoundError",
    "ItemNotAvailableError",
    "ItemAlreadyUsedError",
    "InvalidItemTargetError",
    "EffectError",
    "EffectNotFoundError",
    "EffectExpiredError",

    # Utilitaires
    "get_http_status_code",
    "get_exception_details",
    "create_error_response",
    "create_http_exception_from_error",
    "handle_multiplayer_errors",
    "handle_quantum_errors"
]