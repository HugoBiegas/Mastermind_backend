"""
Gestionnaire WebSocket pour Quantum Mastermind
Gestion des connexions temps réel, rooms, et événements de jeu
"""
import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Set
from uuid import UUID, uuid4
from dataclasses import dataclass, asdict
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import jwt_manager
from app.models.user import User
from app.models.game import Game, GameStatus
from app.services.auth import auth_service
from app.utils.exceptions import (
    WebSocketError, WebSocketAuthenticationError,
    WebSocketConnectionError, WebSocketMessageError
)


# === TYPES D'ÉVÉNEMENTS ===

class EventType(str, Enum):
    # Connexion
    CONNECTION_ESTABLISHED = "connection_established"
    USER_CONNECTED = "user_connected"
    USER_DISCONNECTED = "user_disconnected"

    # Authentification
    AUTHENTICATE = "authenticate"
    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILED = "authentication_failed"

    # Jeu
    JOIN_GAME_ROOM = "join_game_room"
    LEAVE_GAME_ROOM = "leave_game_room"
    GAME_STATE_UPDATE = "game_state_update"
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"
    GAME_STARTED = "game_started"
    GAME_FINISHED = "game_finished"

    # Gameplay
    ATTEMPT_MADE = "attempt_made"
    ATTEMPT_RESULT = "attempt_result"
    QUANTUM_HINT_USED = "quantum_hint_used"
    TURN_CHANGE = "turn_change"

    # Chat
    CHAT_MESSAGE = "chat_message"
    CHAT_BROADCAST = "chat_broadcast"

    # Système
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    NOTIFICATION = "notification"


# === STRUCTURES DE DONNÉES ===

@dataclass
class WebSocketMessage:
    """Message WebSocket standardisé"""
    type: str
    data: Dict[str, Any]
    timestamp: float = None
    message_id: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.message_id is None:
            self.message_id = str(uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class WebSocketConnection:
    """Représente une connexion WebSocket"""
    connection_id: str
    websocket: WebSocket
    user_id: Optional[UUID] = None
    username: Optional[str] = None
    game_rooms: Set[str] = None
    last_heartbeat: float = None
    connected_at: float = None

    def __post_init__(self):
        if self.game_rooms is None:
            self.game_rooms = set()
        if self.last_heartbeat is None:
            self.last_heartbeat = time.time()
        if self.connected_at is None:
            self.connected_at = time.time()

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

    @property
    def is_alive(self) -> bool:
        """Vérifie si la connexion est toujours vivante"""
        return time.time() - self.last_heartbeat < 60  # 1 minute timeout


class WebSocketManager:
    """Gestionnaire principal des connexions WebSocket"""

    def __init__(self):
        # Connexions actives par ID de connexion
        self.connections: Dict[str, WebSocketConnection] = {}

        # Connexions par utilisateur (un utilisateur peut avoir plusieurs connexions)
        self.user_connections: Dict[UUID, Set[str]] = {}

        # Rooms de jeu avec leurs connexions
        self.game_rooms: Dict[str, Set[str]] = {}

        # Lock pour les opérations concurrentes
        self._lock = asyncio.Lock()

    # === GESTION DES CONNEXIONS ===

    async def connect(self, websocket: WebSocket) -> str:
        """
        Établit une nouvelle connexion WebSocket

        Args:
            websocket: Instance WebSocket

        Returns:
            ID de connexion unique
        """
        await websocket.accept()

        async with self._lock:
            connection_id = str(uuid4())
            connection = WebSocketConnection(
                connection_id=connection_id,
                websocket=websocket
            )

            self.connections[connection_id] = connection

            # Message de bienvenue
            welcome_message = WebSocketMessage(
                type=EventType.CONNECTION_ESTABLISHED,
                data={
                    "connection_id": connection_id,
                    "timestamp": time.time(),
                    "server_info": {
                        "name": "Quantum Mastermind WebSocket Server",
                        "version": "1.0.0"
                    }
                }
            )

            await self._send_to_connection(connection_id, welcome_message)

            return connection_id

    async def disconnect(self, connection_id: str) -> None:
        """
        Ferme une connexion WebSocket

        Args:
            connection_id: ID de la connexion à fermer
        """
        async with self._lock:
            connection = self.connections.get(connection_id)
            if not connection:
                return

            # Nettoyage des associations utilisateur
            if connection.user_id and connection.user_id in self.user_connections:
                self.user_connections[connection.user_id].discard(connection_id)
                if not self.user_connections[connection.user_id]:
                    del self.user_connections[connection.user_id]

            # Nettoyage des rooms de jeu
            for room_id in connection.game_rooms.copy():
                await self._leave_game_room(connection_id, room_id)

            # Suppression de la connexion
            del self.connections[connection_id]

            # Notification de déconnexion
            if connection.is_authenticated:
                disconnect_message = WebSocketMessage(
                    type=EventType.USER_DISCONNECTED,
                    data={
                        "user_id": str(connection.user_id),
                        "username": connection.username,
                        "connection_id": connection_id
                    }
                )
                await self._broadcast_to_user_rooms(connection, disconnect_message)

    async def authenticate_connection(
            self,
            connection_id: str,
            token: str,
            db: AsyncSession
    ) -> bool:
        """
        Authentifie une connexion WebSocket

        Args:
            connection_id: ID de la connexion
            token: Token JWT
            db: Session de base de données

        Returns:
            True si authentification réussie
        """
        connection = self.connections.get(connection_id)
        if not connection:
            return False

        try:
            # Vérification du token et récupération de l'utilisateur
            user = await auth_service.get_current_user(db, token)

            async with self._lock:
                # Mise à jour de la connexion avec les infos utilisateur
                connection.user_id = user.id
                connection.username = user.username

                # Ajout à la map des connexions utilisateur
                if user.id not in self.user_connections:
                    self.user_connections[user.id] = set()
                self.user_connections[user.id].add(connection_id)

            # Message de succès
            success_message = WebSocketMessage(
                type=EventType.AUTHENTICATION_SUCCESS,
                data={
                    "user_id": str(user.id),
                    "username": user.username,
                    "authenticated_at": time.time()
                }
            )
            await self._send_to_connection(connection_id, success_message)

            # Notification aux autres connexions
            connect_message = WebSocketMessage(
                type=EventType.USER_CONNECTED,
                data={
                    "user_id": str(user.id),
                    "username": user.username,
                    "connection_id": connection_id
                }
            )
            await self._broadcast_to_user_rooms(connection, connect_message)

            return True

        except Exception as e:
            # Message d'échec
            error_message = WebSocketMessage(
                type=EventType.AUTHENTICATION_FAILED,
                data={
                    "error": "Token invalide",
                    "details": str(e)
                }
            )
            await self._send_to_connection(connection_id, error_message)
            return False

    # === GESTION DES ROOMS ===

    async def join_game_room(self, connection_id: str, room_id: str) -> bool:
        """
        Fait rejoindre une connexion à une room de jeu

        Args:
            connection_id: ID de la connexion
            room_id: ID de la room de jeu

        Returns:
            True si succès
        """
        connection = self.connections.get(connection_id)
        if not connection or not connection.is_authenticated:
            return False

        async with self._lock:
            # Ajout à la room
            if room_id not in self.game_rooms:
                self.game_rooms[room_id] = set()

            self.game_rooms[room_id].add(connection_id)
            connection.game_rooms.add(room_id)

        # Notification de rejoindre la room
        join_message = WebSocketMessage(
            type=EventType.JOIN_GAME_ROOM,
            data={
                "room_id": room_id,
                "user_id": str(connection.user_id),
                "username": connection.username,
                "players_in_room": len(self.game_rooms[room_id])
            }
        )

        await self._send_to_connection(connection_id, join_message)
        await self._broadcast_to_room(room_id, join_message, exclude=connection_id)

        return True

    async def leave_game_room(self, connection_id: str, room_id: str) -> bool:
        """
        Fait quitter une connexion d'une room de jeu

        Args:
            connection_id: ID de la connexion
            room_id: ID de la room de jeu

        Returns:
            True si succès
        """
        return await self._leave_game_room(connection_id, room_id)

    async def _leave_game_room(self, connection_id: str, room_id: str) -> bool:
        """Implémentation interne pour quitter une room"""
        connection = self.connections.get(connection_id)
        if not connection:
            return False

        async with self._lock:
            # Suppression de la room
            if room_id in self.game_rooms:
                self.game_rooms[room_id].discard(connection_id)
                if not self.game_rooms[room_id]:
                    del self.game_rooms[room_id]

            connection.game_rooms.discard(room_id)

        # Notification de quitter la room
        if connection.is_authenticated:
            leave_message = WebSocketMessage(
                type=EventType.LEAVE_GAME_ROOM,
                data={
                    "room_id": room_id,
                    "user_id": str(connection.user_id),
                    "username": connection.username,
                    "players_in_room": len(self.game_rooms.get(room_id, set()))
                }
            )

            await self._broadcast_to_room(room_id, leave_message)

        return True

    # === ENVOI DE MESSAGES ===

    async def send_to_user(
            self,
            user_id: UUID,
            message: WebSocketMessage
    ) -> bool:
        """
        Envoie un message à toutes les connexions d'un utilisateur

        Args:
            user_id: ID de l'utilisateur
            message: Message à envoyer

        Returns:
            True si au moins une connexion a reçu le message
        """
        connection_ids = self.user_connections.get(user_id, set())
        if not connection_ids:
            return False

        success_count = 0
        for connection_id in connection_ids.copy():
            if await self._send_to_connection(connection_id, message):
                success_count += 1

        return success_count > 0

    async def send_to_room(
            self,
            room_id: str,
            message: WebSocketMessage,
            exclude_user_id: Optional[UUID] = None
    ) -> int:
        """
        Envoie un message à toutes les connexions d'une room

        Args:
            room_id: ID de la room
            message: Message à envoyer
            exclude_user_id: Utilisateur à exclure (optionnel)

        Returns:
            Nombre de connexions qui ont reçu le message
        """
        return await self._broadcast_to_room(room_id, message, exclude_user_id=exclude_user_id)

    async def broadcast_to_all(
            self,
            message: WebSocketMessage,
            authenticated_only: bool = True
    ) -> int:
        """
        Diffuse un message à toutes les connexions

        Args:
            message: Message à diffuser
            authenticated_only: Seulement aux utilisateurs authentifiés

        Returns:
            Nombre de connexions qui ont reçu le message
        """
        success_count = 0

        for connection_id, connection in self.connections.items():
            if authenticated_only and not connection.is_authenticated:
                continue

            if await self._send_to_connection(connection_id, message):
                success_count += 1

        return success_count

    # === MÉTHODES PRIVÉES ===

    async def _send_to_connection(
            self,
            connection_id: str,
            message: WebSocketMessage
    ) -> bool:
        """
        Envoie un message à une connexion spécifique

        Args:
            connection_id: ID de la connexion
            message: Message à envoyer

        Returns:
            True si envoyé avec succès
        """
        connection = self.connections.get(connection_id)
        if not connection:
            return False

        try:
            await connection.websocket.send_text(message.to_json())
            return True
        except Exception:
            # Connexion fermée, on la nettoie
            await self.disconnect(connection_id)
            return False

    async def _broadcast_to_room(
            self,
            room_id: str,
            message: WebSocketMessage,
            exclude: Optional[str] = None,
            exclude_user_id: Optional[UUID] = None
    ) -> int:
        """
        Diffuse un message à toutes les connexions d'une room

        Args:
            room_id: ID de la room
            message: Message à diffuser
            exclude: ID de connexion à exclure
            exclude_user_id: ID utilisateur à exclure

        Returns:
            Nombre de connexions qui ont reçu le message
        """
        connection_ids = self.game_rooms.get(room_id, set())
        if not connection_ids:
            return 0

        success_count = 0

        for connection_id in connection_ids.copy():
            if connection_id == exclude:
                continue

            connection = self.connections.get(connection_id)
            if connection and exclude_user_id and connection.user_id == exclude_user_id:
                continue

            if await self._send_to_connection(connection_id, message):
                success_count += 1

        return success_count

    async def _broadcast_to_user_rooms(
            self,
            connection: WebSocketConnection,
            message: WebSocketMessage
    ) -> int:
        """
        Diffuse un message à toutes les rooms d'un utilisateur

        Args:
            connection: Connexion de l'utilisateur
            message: Message à diffuser

        Returns:
            Nombre total de connexions touchées
        """
        total_sent = 0

        for room_id in connection.game_rooms:
            sent = await self._broadcast_to_room(room_id, message, exclude=connection.connection_id)
            total_sent += sent

        return total_sent

    # === GESTION DES ÉVÉNEMENTS DE JEU ===

    async def handle_game_event(
            self,
            game_id: UUID,
            event_type: str,
            event_data: Dict[str, Any],
            exclude_user_id: Optional[UUID] = None
    ) -> None:
        """
        Gère un événement de jeu et le diffuse aux connexions appropriées

        Args:
            game_id: ID de la partie
            event_type: Type d'événement
            event_data: Données de l'événement
            exclude_user_id: Utilisateur à exclure de la diffusion
        """
        room_id = str(game_id)

        message = WebSocketMessage(
            type=event_type,
            data={
                "game_id": str(game_id),
                **event_data
            }
        )

        await self.send_to_room(room_id, message, exclude_user_id=exclude_user_id)

    # === MÉTHODES UTILITAIRES ===

    async def heartbeat_check(self) -> None:
        """
        Vérifie les connexions inactives et les nettoie
        Doit être appelé périodiquement
        """
        current_time = time.time()
        inactive_connections = []

        for connection_id, connection in self.connections.items():
            if current_time - connection.last_heartbeat > 60:  # 1 minute timeout
                inactive_connections.append(connection_id)

        for connection_id in inactive_connections:
            await self.disconnect(connection_id)

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques des connexions

        Returns:
            Statistiques des connexions
        """
        authenticated_count = sum(
            1 for conn in self.connections.values()
            if conn.is_authenticated
        )

        return {
            "total_connections": len(self.connections),
            "authenticated_connections": authenticated_count,
            "anonymous_connections": len(self.connections) - authenticated_count,
            "active_game_rooms": len(self.game_rooms),
            "unique_users": len(self.user_connections)
        }

    def get_room_info(self, room_id: str) -> Optional[Dict[str, Any]]:
        """
        Retourne les informations d'une room

        Args:
            room_id: ID de la room

        Returns:
            Informations de la room ou None
        """
        if room_id not in self.game_rooms:
            return None

        connection_ids = self.game_rooms[room_id]
        users = []

        for connection_id in connection_ids:
            connection = self.connections.get(connection_id)
            if connection and connection.is_authenticated:
                users.append({
                    "user_id": str(connection.user_id),
                    "username": connection.username,
                    "connection_id": connection_id,
                    "connected_at": connection.connected_at
                })

        return {
            "room_id": room_id,
            "connection_count": len(connection_ids),
            "authenticated_users": users,
            "created_at": min(
                self.connections[conn_id].connected_at
                for conn_id in connection_ids
                if conn_id in self.connections
            ) if connection_ids else None
        }


# Instance globale du gestionnaire WebSocket
websocket_manager = WebSocketManager()