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

                # Message de confirmation d'authentification
                auth_success_message = WebSocketMessage(
                    type=EventType.AUTHENTICATION_SUCCESS,
                    data={
                        "user_id": str(user.id),
                        "username": user.username,
                        "authenticated_at": time.time()
                    }
                )

                await self._send_to_connection(connection_id, auth_success_message)

                return True

        except Exception as e:
            # Envoi d'un message d'erreur d'authentification
            auth_error_message = WebSocketMessage(
                type=EventType.AUTHENTICATION_FAILED,
                data={
                    "error": "Invalid token",
                    "reason": str(e)
                }
            )
            await self._send_to_connection(connection_id, auth_error_message)
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
        async with self._lock:
            connection = self.connections.get(connection_id)
            if not connection or not connection.is_authenticated:
                return False

            # Ajout à la room
            if room_id not in self.game_rooms:
                self.game_rooms[room_id] = set()

            self.game_rooms[room_id].add(connection_id)
            connection.game_rooms.add(room_id)

            # Notification aux autres membres de la room
            join_message = WebSocketMessage(
                type=EventType.PLAYER_JOINED,
                data={
                    "user_id": str(connection.user_id),
                    "username": connection.username,
                    "room_id": room_id,
                    "joined_at": time.time()
                }
            )

            await self._broadcast_to_room(room_id, join_message, exclude_connection=connection_id)
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

        # Retrait de la room
        if room_id in self.game_rooms:
            self.game_rooms[room_id].discard(connection_id)
            if not self.game_rooms[room_id]:
                del self.game_rooms[room_id]

        connection.game_rooms.discard(room_id)

        # Notification aux autres membres de la room
        if connection.is_authenticated:
            leave_message = WebSocketMessage(
                type=EventType.PLAYER_LEFT,
                data={
                    "user_id": str(connection.user_id),
                    "username": connection.username,
                    "room_id": room_id,
                    "left_at": time.time()
                }
            )

            await self._broadcast_to_room(room_id, leave_message, exclude_connection=connection_id)

        return True

    # === ENVOI DE MESSAGES ===

    async def send_to_connection(self, connection_id: str, message: WebSocketMessage) -> bool:
        """
        Envoie un message à une connexion spécifique

        Args:
            connection_id: ID de la connexion
            message: Message à envoyer

        Returns:
            True si succès
        """
        return await self._send_to_connection(connection_id, message)

    async def _send_to_connection(self, connection_id: str, message: WebSocketMessage) -> bool:
        """Implémentation interne pour envoyer un message"""
        connection = self.connections.get(connection_id)
        if not connection:
            return False

        try:
            await connection.websocket.send_text(message.to_json())
            return True
        except Exception as e:
            # Connexion fermée, nettoyer
            await self.disconnect(connection_id)
            return False

    async def send_to_user(self, user_id: UUID, message: WebSocketMessage) -> int:
        """
        Envoie un message à toutes les connexions d'un utilisateur

        Args:
            user_id: ID de l'utilisateur
            message: Message à envoyer

        Returns:
            Nombre de connexions qui ont reçu le message
        """
        user_connections = self.user_connections.get(user_id, set())
        sent_count = 0

        for connection_id in user_connections.copy():
            if await self._send_to_connection(connection_id, message):
                sent_count += 1

        return sent_count

    async def broadcast_to_room(self, room_id: str, message: WebSocketMessage,
                              exclude_connection: Optional[str] = None) -> int:
        """
        Diffuse un message à tous les membres d'une room

        Args:
            room_id: ID de la room
            message: Message à diffuser
            exclude_connection: ID de connexion à exclure (optionnel)

        Returns:
            Nombre de connexions qui ont reçu le message
        """
        return await self._broadcast_to_room(room_id, message, exclude_connection)

    async def _broadcast_to_room(self, room_id: str, message: WebSocketMessage,
                               exclude_connection: Optional[str] = None) -> int:
        """Implémentation interne pour broadcaster à une room"""
        room_connections = self.game_rooms.get(room_id, set())
        sent_count = 0

        for connection_id in room_connections.copy():
            if connection_id == exclude_connection:
                continue

            if await self._send_to_connection(connection_id, message):
                sent_count += 1

        return sent_count

    async def broadcast_to_all(self, message: WebSocketMessage) -> int:
        """
        Diffuse un message à toutes les connexions actives

        Args:
            message: Message à diffuser

        Returns:
            Nombre de connexions qui ont reçu le message
        """
        sent_count = 0

        for connection_id in list(self.connections.keys()):
            if await self._send_to_connection(connection_id, message):
                sent_count += 1

        return sent_count

    async def _broadcast_to_user_rooms(self, connection: WebSocketConnection,
                                     message: WebSocketMessage) -> None:
        """Diffuse un message à toutes les rooms où l'utilisateur est présent"""
        for room_id in connection.game_rooms:
            await self._broadcast_to_room(room_id, message, exclude_connection=connection.connection_id)

    # === MAINTENANCE ET NETTOYAGE ===

    async def update_heartbeat(self, connection_id: str) -> bool:
        """
        Met à jour le heartbeat d'une connexion

        Args:
            connection_id: ID de la connexion

        Returns:
            True si succès
        """
        connection = self.connections.get(connection_id)
        if connection:
            connection.last_heartbeat = time.time()
            return True
        return False

    async def cleanup_inactive_connections(self) -> int:
        """
        Nettoie les connexions inactives

        Returns:
            Nombre de connexions nettoyées
        """
        current_time = time.time()
        inactive_connections = []

        # Identifier les connexions inactives
        for connection_id, connection in self.connections.items():
            if current_time - connection.last_heartbeat > 60:  # 1 minute timeout
                inactive_connections.append(connection_id)

        # Nettoyer les connexions inactives
        for connection_id in inactive_connections:
            await self.disconnect(connection_id)

        return len(inactive_connections)

    async def get_room_info(self, room_id: str) -> Dict[str, Any]:
        """
        Récupère les informations d'une room

        Args:
            room_id: ID de la room

        Returns:
            Informations de la room
        """
        room_connections = self.game_rooms.get(room_id, set())
        players = []

        for connection_id in room_connections:
            connection = self.connections.get(connection_id)
            if connection and connection.is_authenticated:
                players.append({
                    "user_id": str(connection.user_id),
                    "username": connection.username,
                    "connected_at": connection.connected_at
                })

        return {
            "room_id": room_id,
            "player_count": len(players),
            "players": players,
            "created_at": time.time()  # À améliorer avec la vraie date de création
        }

    # === MÉTHODES D'INFORMATION ===

    def get_connection_count(self) -> int:
        """Retourne le nombre de connexions actives"""
        return len(self.connections)

    def get_authenticated_count(self) -> int:
        """Retourne le nombre de connexions authentifiées"""
        return sum(1 for conn in self.connections.values() if conn.is_authenticated)

    def get_room_count(self) -> int:
        """Retourne le nombre de rooms actives"""
        return len(self.game_rooms)

    def get_user_connection_count(self, user_id: UUID) -> int:
        """Retourne le nombre de connexions pour un utilisateur"""
        return len(self.user_connections.get(user_id, set()))

    def is_user_connected(self, user_id: UUID) -> bool:
        """Vérifie si un utilisateur est connecté"""
        return user_id in self.user_connections and len(self.user_connections[user_id]) > 0

    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les informations d'une connexion"""
        connection = self.connections.get(connection_id)
        if not connection:
            return None

        return {
            "connection_id": connection.connection_id,
            "user_id": str(connection.user_id) if connection.user_id else None,
            "username": connection.username,
            "is_authenticated": connection.is_authenticated,
            "game_rooms": list(connection.game_rooms),
            "connected_at": connection.connected_at,
            "last_heartbeat": connection.last_heartbeat,
            "is_alive": connection.is_alive
        }

    async def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques globales du gestionnaire WebSocket"""
        return {
            "total_connections": self.get_connection_count(),
            "authenticated_connections": self.get_authenticated_count(),
            "active_rooms": self.get_room_count(),
            "unique_users": len(self.user_connections),
            "rooms_info": {
                room_id: len(connections)
                for room_id, connections in self.game_rooms.items()
            },
            "timestamp": time.time()
        }


# Instance globale du gestionnaire WebSocket
websocket_manager = WebSocketManager()