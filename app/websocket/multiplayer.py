"""
Gestionnaire WebSocket pour le multijoueur - Version complète pour cohérence avec le frontend
Compatible avec les événements attendus par le code React.js décrit dans le document
"""
import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.websocket.manager import WebSocketManager, WebSocketMessage, EventType
from app.models.multijoueur import ItemType, PlayerStatus
from app.utils.exceptions import WebSocketError


class MultiplayerWebSocketManager:
    """Gestionnaire WebSocket pour le multijoueur avec événements cohérents avec le frontend"""

    def __init__(self, base_manager: Optional[WebSocketManager] = None):
        self.base_manager = base_manager

        # Rooms de jeu multijoueur avec métadonnées
        self.multiplayer_rooms: Dict[str, Dict[str, Any]] = {}

        # Connexions par room
        self.room_connections: Dict[str, Dict[str, Dict[str, Any]]] = {}

        # Effets actifs par partie
        self.active_effects: Dict[str, Dict[str, Any]] = {}

        # Lock pour les opérations concurrentes
        self._lock = asyncio.Lock()

        # Configuration WebSocket conforme au frontend
        self.config = {
            "HEARTBEAT_INTERVAL": 30000,
            "MAX_RECONNECT_ATTEMPTS": 5,
            "RECONNECT_DELAY": 1000,
            "MESSAGE_TIMEOUT": 10000,
            "PING_INTERVAL": 25000
        }

    # =====================================================
    # GESTION DES CONNEXIONS
    # =====================================================

    async def add_connection_to_room(
            self,
            room_code: str,
            websocket: WebSocket,
            user_id: UUID,
            username: str
    ) -> None:
        """Ajoute une connexion à une room"""
        async with self._lock:
            if room_code not in self.room_connections:
                self.room_connections[room_code] = {}

            connection_id = str(user_id)
            self.room_connections[room_code][connection_id] = {
                "websocket": websocket,
                "user_id": str(user_id),
                "username": username,
                "connected_at": time.time(),
                "last_heartbeat": time.time(),
                "last_ping": time.time()
            }

            # Créer la room si elle n'existe pas
            if room_code not in self.multiplayer_rooms:
                await self.create_multiplayer_room(room_code, {})

            # Notifier les autres de la connexion
            await self.notify_player_joined(room_code, str(user_id), username)

            # Envoyer un message de connexion confirmée
            await self.send_to_user(room_code, str(user_id), {
                "type": "CONNECT",
                "data": {
                    "room_code": room_code,
                    "user_id": str(user_id),
                    "username": username,
                    "connected_at": time.time()
                },
                "timestamp": time.time()
            })

    async def remove_connection_from_room(
            self,
            room_code: str,
            user_id: UUID,
            reason: Optional[str] = None
    ) -> None:
        """Retire une connexion d'une room"""
        async with self._lock:
            user_id_str = str(user_id)

            if room_code in self.room_connections and user_id_str in self.room_connections[room_code]:
                connection_data = self.room_connections[room_code][user_id_str]
                username = connection_data.get("username", "Inconnu")

                # Fermer la connexion WebSocket
                try:
                    websocket = connection_data["websocket"]
                    await websocket.close()
                except:
                    pass

                # Retirer de la liste des connexions
                del self.room_connections[room_code][user_id_str]

                # Notifier les autres du départ
                await self.notify_player_left(room_code, user_id_str, username, reason)

                # Nettoyer la room si vide
                if not self.room_connections[room_code]:
                    await self.cleanup_room(room_code)

    async def create_multiplayer_room(
            self,
            room_code: str,
            room_data: Dict[str, Any]
    ) -> None:
        """Crée une room multijoueur avec métadonnées"""
        async with self._lock:
            self.multiplayer_rooms[room_code] = {
                "room_code": room_code,
                "created_at": time.time(),
                "max_players": room_data.get("max_players", 12),
                "current_players": 0,
                "game_status": "waiting",
                "current_mastermind": 1,
                "total_masterminds": room_data.get("total_masterminds", 3),
                "items_enabled": room_data.get("items_enabled", True),
                "players": {},
                "spectators": set(),
                "active_effects": {}
            }

            if room_code not in self.active_effects:
                self.active_effects[room_code] = {}

    # =====================================================
    # ÉVÉNEMENTS MULTIJOUEUR (COHÉRENTS AVEC LE FRONTEND)
    # =====================================================

    async def notify_player_joined(
            self,
            room_code: str,
            user_id: str,
            username: str,
            player_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Notifie qu'un joueur a rejoint la partie"""
        message = {
            "type": "PLAYER_JOINED",
            "data": {
                "username": username,
                "players_count": len(self.room_connections.get(room_code, {})),
                "player_data": player_data or {
                    "user_id": user_id,
                    "username": username,
                    "status": "waiting",
                    "score": 0,
                    "current_mastermind": 1,
                    "attempts_count": 0,
                    "items": [],
                    "active_effects": [],
                    "is_host": False,
                    "join_order": len(self.room_connections.get(room_code, {}))
                }
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)

    async def notify_player_left(
            self,
            room_code: str,
            user_id: str,
            username: str,
            reason: Optional[str] = None
    ) -> None:
        """Notifie qu'un joueur a quitté la partie"""
        message = {
            "type": "PLAYER_LEFT",
            "data": {
                "user_id": user_id,
                "username": username,
                "players_count": len(self.room_connections.get(room_code, {})),
                "reason": reason
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)

    async def notify_game_started(
            self,
            room_code: str,
            game_data: Any
    ) -> None:
        """Notifie que la partie a démarré"""
        message = {
            "type": "GAME_STARTED",
            "data": {
                "game_id": room_code,
                "current_mastermind": getattr(game_data, 'current_mastermind', 1),
                "total_masterminds": getattr(game_data, 'total_masterminds', 3),
                "status": "in_progress",
                "started_at": time.time()
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)

        # Mettre à jour le statut de la room
        if room_code in self.multiplayer_rooms:
            self.multiplayer_rooms[room_code]["game_status"] = "in_progress"

    async def notify_game_finished(
            self,
            room_code: str,
            winner: Optional[str] = None,
            final_standings: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Notifie que la partie est terminée"""
        message = {
            "type": "GAME_FINISHED",
            "data": {
                "game_id": room_code,
                "winner": winner,
                "final_standings": final_standings or [],
                "finished_at": time.time()
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)

        # Mettre à jour le statut de la room
        if room_code in self.multiplayer_rooms:
            self.multiplayer_rooms[room_code]["game_status"] = "finished"

    async def notify_attempt_made(
            self,
            room_code: str,
            user_id: str,
            username: str,
            attempt_result: Dict[str, Any]
    ) -> None:
        """Notifie qu'une tentative a été effectuée"""
        message = {
            "type": "PLAYER_MASTERMIND_COMPLETE" if attempt_result.get("is_winning") else "GAME_PROGRESS_UPDATE",
            "data": {
                "player_id": user_id,
                "username": username,
                "mastermind_number": attempt_result.get("mastermind_number"),
                "attempt_result": attempt_result,
                "is_winning": attempt_result.get("is_winning", False)
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)

    async def notify_player_status_changed(
            self,
            room_code: str,
            user_id: str,
            username: str,
            old_status: str,
            new_status: str,
            additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Notifie qu'un statut de joueur a changé"""
        message = {
            "type": "PLAYER_STATUS_CHANGED",
            "data": {
                "player_id": user_id,
                "username": username,
                "old_status": old_status,
                "new_status": new_status,
                "additional_data": additional_data or {}
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)

    async def notify_item_used(
            self,
            room_code: str,
            user_id: str,
            username: str,
            item_type: ItemType,
            target_players: Optional[List[str]] = None,
            effects: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Notifie qu'un objet a été utilisé"""
        message = {
            "type": "ITEM_USED",
            "data": {
                "player_id": user_id,
                "username": username,
                "item_type": item_type.value,
                "target_players": target_players or [],
                "effects": effects or []
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)

    async def notify_effect_applied(
            self,
            room_code: str,
            effect_data: Dict[str, Any]
    ) -> None:
        """Notifie qu'un effet a été appliqué"""
        message = {
            "type": "EFFECT_APPLIED",
            "data": effect_data,
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)

    async def send_chat_message(
            self,
            room_code: str,
            user_id: str,
            username: str,
            content: str,
            message_type: str = "text"
    ) -> None:
        """Envoie un message de chat"""
        message = {
            "type": "CHAT_MESSAGE",
            "data": {
                "message_id": f"{user_id}_{int(time.time())}",
                "player_id": user_id,
                "username": username,
                "content": content,
                "message_type": message_type,
                "sent_at": time.time()
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)

    async def send_error(
            self,
            room_code: str,
            user_id: str,
            error_message: str,
            error_code: Optional[str] = None
    ) -> None:
        """Envoie un message d'erreur à un utilisateur spécifique"""
        message = {
            "type": "ERROR",
            "data": {
                "message": error_message,
                "code": error_code,
                "user_id": user_id
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.send_to_user(room_code, user_id, message)

    # =====================================================
    # GESTION DES MESSAGES
    # =====================================================

    async def handle_message(
            self,
            room_code: str,
            user_id: str,
            message: str
    ) -> None:
        """Traite un message reçu d'un client"""
        try:
            data = json.loads(message)
            message_type = data.get("type")

            if message_type == "HEARTBEAT":
                await self.handle_heartbeat(room_code, user_id)
            elif message_type == "CHAT_MESSAGE":
                await self.handle_chat_message(room_code, user_id, data)
            elif message_type == "PING":
                await self.handle_ping(room_code, user_id)
            else:
                # Messages personnalisés de l'application
                await self.handle_custom_message(room_code, user_id, data)

        except json.JSONDecodeError:
            await self.send_error(room_code, user_id, "Message malformé")
        except Exception as e:
            await self.send_error(room_code, user_id, f"Erreur de traitement: {str(e)}")

    async def handle_heartbeat(self, room_code: str, user_id: str) -> None:
        """Traite un heartbeat"""
        if room_code in self.room_connections and user_id in self.room_connections[room_code]:
            self.room_connections[room_code][user_id]["last_heartbeat"] = time.time()

            # Répondre avec un heartbeat
            await self.send_to_user(room_code, user_id, {
                "type": "HEARTBEAT",
                "data": {"timestamp": time.time()},
                "timestamp": time.time()
            })

    async def handle_ping(self, room_code: str, user_id: str) -> None:
        """Traite un ping"""
        if room_code in self.room_connections and user_id in self.room_connections[room_code]:
            self.room_connections[room_code][user_id]["last_ping"] = time.time()

            # Répondre avec un pong
            await self.send_to_user(room_code, user_id, {
                "type": "PONG",
                "data": {"timestamp": time.time()},
                "timestamp": time.time()
            })

    async def handle_chat_message(
            self,
            room_code: str,
            user_id: str,
            data: Dict[str, Any]
    ) -> None:
        """Traite un message de chat"""
        content = data.get("data", {}).get("content", "")
        if content.strip():
            username = self.room_connections[room_code][user_id]["username"]
            await self.send_chat_message(room_code, user_id, username, content)

    async def handle_custom_message(
            self,
            room_code: str,
            user_id: str,
            data: Dict[str, Any]
    ) -> None:
        """Traite les messages personnalisés de l'application"""
        # Cette méthode peut être étendue pour gérer des messages spécifiques
        # comme les demandes de statut, les actions de jeu, etc.
        pass

    # =====================================================
    # DIFFUSION DE MESSAGES
    # =====================================================

    async def broadcast_to_room(
            self,
            room_code: str,
            message: Dict[str, Any],
            exclude_users: Optional[List[str]] = None
    ) -> None:
        """Diffuse un message à tous les utilisateurs d'une room"""
        if room_code not in self.room_connections:
            return

        exclude_users = exclude_users or []

        for user_id, connection_data in self.room_connections[room_code].items():
            if user_id not in exclude_users:
                await self.send_to_user(room_code, user_id, message)

    async def send_to_user(
            self,
            room_code: str,
            user_id: str,
            message: Dict[str, Any]
    ) -> None:
        """Envoie un message à un utilisateur spécifique"""
        if room_code not in self.room_connections:
            return

        if user_id not in self.room_connections[room_code]:
            return

        try:
            websocket = self.room_connections[room_code][user_id]["websocket"]
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            print(f"Erreur envoi WebSocket pour {user_id}: {e}")
            # Retirer la connexion défaillante
            await self.remove_connection_from_room(room_code, UUID(user_id), "Connection error")

    async def send_to_users(
            self,
            room_code: str,
            user_ids: List[str],
            message: Dict[str, Any]
    ) -> None:
        """Envoie un message à une liste d'utilisateurs spécifiques"""
        for user_id in user_ids:
            await self.send_to_user(room_code, user_id, message)

    # =====================================================
    # GESTION DES EFFETS ACTIFS
    # =====================================================

    async def add_active_effect(
            self,
            room_code: str,
            effect_id: str,
            effect_data: Dict[str, Any]
    ) -> None:
        """Ajoute un effet actif à une room"""
        if room_code not in self.active_effects:
            self.active_effects[room_code] = {}

        self.active_effects[room_code][effect_id] = {
            **effect_data,
            "created_at": time.time(),
            "is_active": True
        }

        await self.notify_effect_applied(room_code, {
            "effect_id": effect_id,
            "effect_data": effect_data,
            "action": "added"
        })

    async def remove_active_effect(
            self,
            room_code: str,
            effect_id: str
    ) -> None:
        """Retire un effet actif d'une room"""
        if room_code in self.active_effects and effect_id in self.active_effects[room_code]:
            del self.active_effects[room_code][effect_id]

            await self.notify_effect_applied(room_code, {
                "effect_id": effect_id,
                "action": "removed"
            })

    async def get_active_effects(self, room_code: str) -> Dict[str, Any]:
        """Récupère les effets actifs d'une room"""
        return self.active_effects.get(room_code, {})

    # =====================================================
    # NETTOYAGE ET MAINTENANCE
    # =====================================================

    async def cleanup_room(self, room_code: str) -> None:
        """Nettoie une room et ses effets"""
        async with self._lock:
            if room_code in self.multiplayer_rooms:
                del self.multiplayer_rooms[room_code]

            if room_code in self.room_connections:
                del self.room_connections[room_code]

            if room_code in self.active_effects:
                del self.active_effects[room_code]

    async def cleanup_inactive_connections(self) -> None:
        """Nettoie les connexions inactives (heartbeat timeout)"""
        current_time = time.time()
        timeout = 300  # 5 minutes

        rooms_to_cleanup = []

        for room_code, connections in list(self.room_connections.items()):
            users_to_remove = []

            for user_id, connection_data in connections.items():
                last_heartbeat = connection_data.get("last_heartbeat", 0)
                if current_time - last_heartbeat > timeout:
                    users_to_remove.append(user_id)

            # Nettoyer les connexions expirées
            for user_id in users_to_remove:
                await self.remove_connection_from_room(room_code, UUID(user_id), "Timeout")

            # Marquer les rooms vides pour nettoyage
            if not connections:
                rooms_to_cleanup.append(room_code)

        # Nettoyer les rooms vides
        for room_code in rooms_to_cleanup:
            await self.cleanup_room(room_code)

    async def get_room_stats(self, room_code: str) -> Dict[str, Any]:
        """Récupère les statistiques d'une room"""
        room_data = self.multiplayer_rooms.get(room_code, {})
        connections = self.room_connections.get(room_code, {})
        effects = self.active_effects.get(room_code, {})

        return {
            "room_code": room_code,
            "connected_players": len(connections),
            "room_status": room_data.get("game_status", "unknown"),
            "active_effects_count": len(effects),
            "created_at": room_data.get("created_at"),
            "players": [
                {
                    "user_id": user_id,
                    "username": conn_data["username"],
                    "connected_at": conn_data["connected_at"],
                    "last_heartbeat": conn_data["last_heartbeat"]
                }
                for user_id, conn_data in connections.items()
            ]
        }

    # =====================================================
    # MÉTHODES D'INFORMATION
    # =====================================================

    def get_connected_users_count(self, room_code: str) -> int:
        """Récupère le nombre d'utilisateurs connectés dans une room"""
        return len(self.room_connections.get(room_code, {}))

    def is_user_connected(self, room_code: str, user_id: str) -> bool:
        """Vérifie si un utilisateur est connecté à une room"""
        return (room_code in self.room_connections and
                user_id in self.room_connections[room_code])

    async def get_all_rooms_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques de toutes les rooms"""
        stats = {
            "total_rooms": len(self.multiplayer_rooms),
            "total_connections": sum(len(conns) for conns in self.room_connections.values()),
            "rooms": []
        }

        for room_code in self.multiplayer_rooms.keys():
            room_stats = await self.get_room_stats(room_code)
            stats["rooms"].append(room_stats)

        return stats


# Instance globale du gestionnaire multijoueur
multiplayer_ws_manager = MultiplayerWebSocketManager()


def initialize_multiplayer_websocket(base_manager: Optional[WebSocketManager] = None) -> MultiplayerWebSocketManager:
    """Initialise le gestionnaire multijoueur avec le gestionnaire de base"""
    global multiplayer_ws_manager
    if base_manager:
        multiplayer_ws_manager.base_manager = base_manager
    return multiplayer_ws_manager


# Tâche de nettoyage automatique (à exécuter périodiquement)
async def cleanup_task():
    """Tâche de nettoyage à exécuter périodiquement"""
    while True:
        try:
            await multiplayer_ws_manager.cleanup_inactive_connections()
            await asyncio.sleep(60)  # Nettoyer chaque minute
        except Exception as e:
            print(f"Erreur lors du nettoyage WebSocket: {e}")
            await asyncio.sleep(60)