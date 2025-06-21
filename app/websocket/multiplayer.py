"""
Gestionnaire WebSocket pour le multijoueur - Version corrigée pour cohérence avec le frontend
Compatible avec les événements attendus par le code React.js
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
                "last_heartbeat": time.time()
            }

            # Créer la room si elle n'existe pas
            if room_code not in self.multiplayer_rooms:
                await self.create_multiplayer_room(room_code, {})

            # Notifier les autres de la connexion
            await self.broadcast_to_room(room_code, {
                "type": "USER_CONNECTED",
                "data": {
                    "user_id": str(user_id),
                    "username": username,
                    "players_count": len(self.room_connections[room_code])
                }
            }, exclude_user=str(user_id))

            # Envoyer un message de bienvenue au nouvel utilisateur
            await self.send_to_user(room_code, str(user_id), {
                "type": "CONNECTION_ESTABLISHED",
                "data": {
                    "room_code": room_code,
                    "connected_players": [
                        {
                            "user_id": conn["user_id"],
                            "username": conn["username"]
                        }
                        for conn in self.room_connections[room_code].values()
                    ]
                }
            })


    async def remove_connection_from_room(
            self,
            room_code: str,
            user_id: UUID
    ) -> None:
        """Retire une connexion d'une room"""
        async with self._lock:
            if room_code not in self.room_connections:
                return

            connection_id = str(user_id)
            if connection_id in self.room_connections[room_code]:
                connection_data = self.room_connections[room_code][connection_id]
                username = connection_data["username"]

                del self.room_connections[room_code][connection_id]

                # Notifier les autres de la déconnexion
                await self.broadcast_to_room(room_code, {
                    "type": "USER_DISCONNECTED",
                    "data": {
                        "user_id": str(user_id),
                        "username": username,
                        "players_count": len(self.room_connections[room_code])
                    }
                })

                # Nettoyer la room si vide
                if not self.room_connections[room_code]:
                    await self.cleanup_room(room_code)


    # =====================================================
    # GESTION DES ROOMS MULTIJOUEUR
    # =====================================================

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
                    "join_order": 0
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
            game_id: str,
            updated_game_state: Optional[Dict[str, Any]] = None
    ) -> None:
        """Notifie que la partie a commencé"""
        message = {
            "type": "GAME_STARTED",
            "data": {
                "game_id": game_id,
                "current_mastermind": 1,
                "updated_game_state": updated_game_state
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)


    async def notify_attempt_made(
            self,
            room_code: str,
            user_id: str,
            username: str,
            mastermind_number: int,
            result: Dict[str, Any]
    ) -> None:
        """Notifie qu'une tentative a été effectuée"""
        message = {
            "type": "ATTEMPT_MADE",
            "data": {
                "player_id": user_id,
                "username": username,
                "mastermind_number": mastermind_number,
                "result": result
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)


    async def notify_mastermind_completed(
            self,
            room_code: str,
            user_id: str,
            username: str,
            mastermind_number: int,
            score: int,
            items_obtained: List[Dict[str, Any]] = None
    ) -> None:
        """Notifie qu'un mastermind a été complété"""
        message = {
            "type": "PLAYER_MASTERMIND_COMPLETE",
            "data": {
                "player_id": user_id,
                "username": username,
                "mastermind_number": mastermind_number,
                "score": score,
                "items_obtained": items_obtained or []
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
            effects: List[Dict[str, Any]] = None
    ) -> None:
        """Notifie qu'un objet a été utilisé"""
        message = {
            "type": "ITEM_USED",
            "data": {
                "player_id": user_id,
                "username": username,
                "item_type": item_type.value,
                "target_players": target_players,
                "effects": effects or []
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)


    async def notify_effect_applied(
            self,
            room_code: str,
            effect_type: str,
            source_player: str,
            target_players: List[str],
            duration: int,
            intensity: float = 1.0
    ) -> None:
        """Notifie qu'un effet a été appliqué"""
        message = {
            "type": "EFFECT_APPLIED",
            "data": {
                "effect_type": effect_type,
                "source_player": source_player,
                "target_players": target_players,
                "duration": duration,
                "intensity": intensity
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)


    async def notify_game_finished(
            self,
            room_code: str,
            game_id: str,
            winner: Optional[str] = None,
            final_standings: List[Dict[str, Any]] = None,
            game_stats: Dict[str, Any] = None
    ) -> None:
        """Notifie que la partie est terminée"""
        message = {
            "type": "GAME_FINISHED",
            "data": {
                "game_id": game_id,
                "winner": winner,
                "final_standings": final_standings or [],
                "game_stats": game_stats or {}
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)


    async def notify_game_state_update(
            self,
            room_code: str,
            updated_game_state: Dict[str, Any]
    ) -> None:
        """Notifie d'une mise à jour de l'état de jeu"""
        message = {
            "type": "GAME_STATE_UPDATE",
            "data": {
                "updated_game_state": updated_game_state
            },
            "timestamp": time.time(),
            "game_id": room_code
        }

        await self.broadcast_to_room(room_code, message)


    # =====================================================
    # GESTION DES MESSAGES ENTRANTS
    # =====================================================

    async def handle_message(
            self,
            room_code: str,
            user_id: UUID,
            raw_message: str,
            db: AsyncSession
    ) -> None:
        """Traite un message WebSocket entrant"""
        try:
            message_data = json.loads(raw_message)
            message_type = message_data.get("type")
            data = message_data.get("data", {})

            # Dispatcher vers le bon handler
            if message_type == "HEARTBEAT":
                await self._handle_heartbeat(room_code, str(user_id))

            elif message_type == "CHAT_MESSAGE":
                await self._handle_chat_message(room_code, str(user_id), data)

            elif message_type == "GET_GAME_STATE":
                await self._handle_get_game_state(room_code, str(user_id), db)

            elif message_type == "PLAYER_STATUS_UPDATE":
                await self._handle_player_status_update(room_code, str(user_id), data)

            else:
                # Message non reconnu
                await self.send_to_user(room_code, str(user_id), {
                    "type": "ERROR",
                    "data": {
                        "message": f"Type de message non reconnu: {message_type}"
                    }
                })

        except json.JSONDecodeError:
            await self.send_to_user(room_code, str(user_id), {
                "type": "ERROR",
                "data": {
                    "message": "Format de message invalide"
                }
            })
        except Exception as e:
            await self.send_to_user(room_code, str(user_id), {
                "type": "ERROR",
                "data": {
                    "message": f"Erreur lors du traitement: {str(e)}"
                }
            })


    # =====================================================
    # HANDLERS DE MESSAGES SPÉCIFIQUES
    # =====================================================

    async def _handle_heartbeat(self, room_code: str, user_id: str) -> None:
        """Traite un heartbeat"""
        if (room_code in self.room_connections and
            user_id in self.room_connections[room_code]):
            self.room_connections[room_code][user_id]["last_heartbeat"] = time.time()

            # Répondre au heartbeat
            await self.send_to_user(room_code, user_id, {
                "type": "HEARTBEAT",
                "data": {
                    "timestamp": time.time()
                }
            })


    async def _handle_chat_message(
            self,
            room_code: str,
            user_id: str,
            data: Dict[str, Any]
    ) -> None:
        """Traite un message de chat"""
        if room_code not in self.room_connections or user_id not in self.room_connections[room_code]:
            return

        username = self.room_connections[room_code][user_id]["username"]
        message_content = data.get("message", "")

        # Diffuser le message à tous les participants
        await self.broadcast_to_room(room_code, {
            "type": "CHAT_BROADCAST",
            "data": {
                "user_id": user_id,
                "username": username,
                "message": message_content,
                "timestamp": time.time()
            }
        })


    async def _handle_get_game_state(
            self,
            room_code: str,
            user_id: str,
            db: AsyncSession
    ) -> None:
        """Envoie l'état actuel de la partie"""
        try:
            # Récupérer l'état de la partie depuis la base de données
            # Cette logique devrait être implémentée avec le service multiplayer

            await self.send_to_user(room_code, user_id, {
                "type": "GAME_STATE_UPDATE",
                "data": {
                    "updated_game_state": {
                        "room_code": room_code,
                        "status": "active",
                        "current_mastermind": 1,
                        "players": []
                    }
                }
            })

        except Exception as e:
            await self.send_to_user(room_code, user_id, {
                "type": "ERROR",
                "data": {
                    "message": f"Erreur lors de la récupération de l'état: {str(e)}"
                }
            })


    async def _handle_player_status_update(
            self,
            room_code: str,
            user_id: str,
            data: Dict[str, Any]
    ) -> None:
        """Traite une mise à jour de statut de joueur"""
        new_status = data.get("status")
        if not new_status:
            return

        username = self.room_connections[room_code][user_id]["username"]

        # Diffuser la mise à jour de statut
        await self.broadcast_to_room(room_code, {
            "type": "PLAYER_STATUS_CHANGED",
            "data": {
                "player_id": user_id,
                "username": username,
                "new_status": new_status
            }
        }, exclude_user=user_id)


    # =====================================================
    # MÉTHODES DE COMMUNICATION
    # =====================================================

    async def broadcast_to_room(
            self,
            room_code: str,
            message: Dict[str, Any],
            exclude_user: Optional[str] = None
    ) -> None:
        """Diffuse un message à tous les participants d'une room"""
        if room_code not in self.room_connections:
            return

        message_json = json.dumps(message)

        # Envoyer à tous les connectés de la room
        for user_id, connection_data in self.room_connections[room_code].items():
            if exclude_user and user_id == exclude_user:
                continue

            try:
                websocket = connection_data["websocket"]
                await websocket.send_text(message_json)
            except Exception as e:
                # Connexion fermée, la nettoyer plus tard
                print(f"Erreur envoi WebSocket pour {user_id}: {e}")


    async def send_to_user(
            self,
            room_code: str,
            user_id: str,
            message: Dict[str, Any]
    ) -> None:
        """Envoie un message à un utilisateur spécifique"""
        if (room_code not in self.room_connections or
            user_id not in self.room_connections[room_code]):
            return

        try:
            websocket = self.room_connections[room_code][user_id]["websocket"]
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            print(f"Erreur envoi WebSocket pour {user_id}: {e}")


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

        for room_code, connections in self.room_connections.items():
            users_to_remove = []

            for user_id, connection_data in connections.items():
                last_heartbeat = connection_data.get("last_heartbeat", 0)
                if current_time - last_heartbeat > timeout:
                    users_to_remove.append(user_id)

            # Nettoyer les connexions expirées
            for user_id in users_to_remove:
                await self.remove_connection_from_room(room_code, UUID(user_id))

            # Marquer les rooms vides pour nettoyage
            if not connections:
                rooms_to_cleanup.append(room_code)

        # Nettoyer les rooms vides
        for room_code in rooms_to_cleanup:
            await self.cleanup_room(room_code)


# Instance globale du gestionnaire multijoueur
multiplayer_ws_manager = MultiplayerWebSocketManager()


def initialize_multiplayer_websocket(base_manager: Optional[WebSocketManager] = None) -> MultiplayerWebSocketManager:
    """Initialise le gestionnaire multijoueur avec le gestionnaire de base"""
    global multiplayer_ws_manager
    if base_manager:
        multiplayer_ws_manager.base_manager = base_manager
    return multiplayer_ws_manager