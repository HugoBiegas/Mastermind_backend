"""
Gestionnaire WebSocket spécialisé pour le multijoueur
Communication temps réel pour les parties multijoueur
"""
import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.websocket.manager import WebSocketManager, WebSocketMessage, EventType
from app.models.multijoueur import ItemType, PlayerStatus
from app.utils.exceptions import WebSocketError


class MultiplayerWebSocketManager:
    """Gestionnaire WebSocket pour le multijoueur"""

    def __init__(self, base_manager: WebSocketManager):
        self.base_manager = base_manager

        # Rooms de jeu multijoueur avec métadonnées
        self.multiplayer_rooms: Dict[str, Dict[str, Any]] = {}

        # Effets actifs par partie
        self.active_effects: Dict[str, Dict[str, Any]] = {}

        # Lock pour les opérations concurrentes
        self._lock = asyncio.Lock()

    # =====================================================
    # GESTION DES ROOMS MULTIJOUEUR
    # =====================================================

    async def create_multiplayer_room(
            self,
            game_id: str,
            room_data: Dict[str, Any]
    ) -> None:
        """Crée une room multijoueur avec métadonnées"""
        async with self._lock:
            self.multiplayer_rooms[game_id] = {
                "game_id": game_id,
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

    async def join_multiplayer_room(
            self,
            connection_id: str,
            game_id: str,
            user_data: Dict[str, Any]
    ) -> bool:
        """Fait rejoindre un joueur à une room multijoueur"""

        # Utiliser le gestionnaire de base pour la room
        success = await self.base_manager.join_game_room(connection_id, game_id)
        if not success:
            return False

        async with self._lock:
            if game_id not in self.multiplayer_rooms:
                await self.create_multiplayer_room(game_id, {})

            room = self.multiplayer_rooms[game_id]

            # Ajouter le joueur aux métadonnées de la room
            user_id = user_data.get("user_id")
            if user_id:
                room["players"][user_id] = {
                    "connection_id": connection_id,
                    "username": user_data.get("username", "Unknown"),
                    "joined_at": time.time(),
                    "status": PlayerStatus.WAITING.value,
                    "current_mastermind": 1,
                    "score": 0,
                    "items_count": 0
                }
                room["current_players"] = len(room["players"])

            # Notifier les autres joueurs
            await self._broadcast_to_room(game_id, WebSocketMessage(
                type=EventType.PLAYER_JOINED,
                data={
                    "user_id": user_id,
                    "username": user_data.get("username"),
                    "current_players": room["current_players"],
                    "max_players": room["max_players"]
                }
            ), exclude_connection=connection_id)

        return True

    async def leave_multiplayer_room(
            self,
            connection_id: str,
            game_id: str
    ) -> None:
        """Fait quitter un joueur d'une room multijoueur"""

        async with self._lock:
            if game_id not in self.multiplayer_rooms:
                return

            room = self.multiplayer_rooms[game_id]

            # Trouver et retirer le joueur
            user_to_remove = None
            for user_id, player_data in room["players"].items():
                if player_data["connection_id"] == connection_id:
                    user_to_remove = user_id
                    break

            if user_to_remove:
                username = room["players"][user_to_remove]["username"]
                del room["players"][user_to_remove]
                room["current_players"] = len(room["players"])

                # Notifier les autres joueurs
                await self._broadcast_to_room(game_id, WebSocketMessage(
                    type=EventType.PLAYER_LEFT,
                    data={
                        "user_id": user_to_remove,
                        "username": username,
                        "current_players": room["current_players"]
                    }
                ), exclude_connection=connection_id)

        # Utiliser le gestionnaire de base
        await self.base_manager.leave_game_room(connection_id, game_id)

    # =====================================================
    # ÉVÉNEMENTS DE GAMEPLAY
    # =====================================================

    async def notify_attempt_made(
            self,
            game_id: str,
            user_id: UUID,
            attempt_data: Dict[str, Any],
            mastermind_completed: bool = False
    ) -> None:
        """Notifie qu'une tentative a été effectuée"""

        message = WebSocketMessage(
            type=EventType.ATTEMPT_MADE,
            data={
                "user_id": str(user_id),
                "attempt": {
                    "attempt_number": attempt_data.get("attempt_number"),
                    "combination": attempt_data.get("combination"),
                    "exact_matches": attempt_data.get("exact_matches"),
                    "position_matches": attempt_data.get("position_matches"),
                    "is_correct": attempt_data.get("is_correct"),
                    "score": attempt_data.get("attempt_score"),
                    "time_taken": attempt_data.get("time_taken")
                },
                "mastermind_completed": mastermind_completed,
                "timestamp": time.time()
            }
        )

        await self._broadcast_to_room(game_id, message)

    async def notify_mastermind_complete(
            self,
            game_id: str,
            user_id: UUID,
            mastermind_number: int,
            score: int,
            items_obtained: List[Dict[str, Any]]
    ) -> None:
        """Notifie qu'un mastermind a été complété"""

        async with self._lock:
            if game_id in self.multiplayer_rooms:
                room = self.multiplayer_rooms[game_id]
                user_id_str = str(user_id)

                if user_id_str in room["players"]:
                    room["players"][user_id_str]["status"] = PlayerStatus.MASTERMIND_COMPLETE.value
                    room["players"][user_id_str]["current_mastermind"] = mastermind_number + 1
                    room["players"][user_id_str]["score"] += score
                    room["players"][user_id_str]["items_count"] += len(items_obtained)

        message = WebSocketMessage(
            type="PLAYER_MASTERMIND_COMPLETE",
            data={
                "user_id": str(user_id),
                "username": await self._get_username_in_room(game_id, str(user_id)),
                "mastermind_number": mastermind_number,
                "score": score,
                "total_score": await self._get_player_score(game_id, str(user_id)),
                "items_obtained": items_obtained,
                "timestamp": time.time()
            }
        )

        await self._broadcast_to_room(game_id, message)

    async def notify_player_finished(
            self,
            game_id: str,
            user_id: UUID,
            final_position: int,
            total_score: int
    ) -> None:
        """Notifie qu'un joueur a terminé tous ses masterminds"""

        async with self._lock:
            if game_id in self.multiplayer_rooms:
                room = self.multiplayer_rooms[game_id]
                user_id_str = str(user_id)

                if user_id_str in room["players"]:
                    room["players"][user_id_str]["status"] = PlayerStatus.FINISHED.value
                    room["players"][user_id_str]["final_position"] = final_position

        message = WebSocketMessage(
            type="PLAYER_FINISHED",
            data={
                "user_id": str(user_id),
                "username": await self._get_username_in_room(game_id, str(user_id)),
                "final_position": final_position,
                "total_score": total_score,
                "timestamp": time.time()
            }
        )

        await self._broadcast_to_room(game_id, message)

    async def notify_game_finished(self, game_id: str) -> None:
        """Notifie que la partie est terminée"""

        # Récupérer le classement final
        final_ranking = await self._get_final_ranking(game_id)

        message = WebSocketMessage(
            type=EventType.GAME_FINISHED,
            data={
                "game_id": game_id,
                "final_ranking": final_ranking,
                "finished_at": time.time()
            }
        )

        await self._broadcast_to_room(game_id, message)

    # =====================================================
    # SYSTÈME D'OBJETS
    # =====================================================

    async def notify_item_used(
            self,
            game_id: str,
            user_id: UUID,
            item: Dict[str, Any],
            target_players: List[UUID]
    ) -> None:
        """Notifie l'utilisation d'un objet"""

        message = WebSocketMessage(
            type="ITEM_USED",
            data={
                "user_id": str(user_id),
                "username": await self._get_username_in_room(game_id, str(user_id)),
                "item": item,
                "target_players": [str(uid) for uid in target_players],
                "timestamp": time.time()
            }
        )

        await self._broadcast_to_room(game_id, message)

    async def notify_effect_applied(
            self,
            game_id: str,
            effect_type: ItemType,
            affected_players: List[UUID],
            duration: Optional[int] = None,
            message_text: str = ""
    ) -> None:
        """Notifie l'application d'un effet"""

        # Enregistrer l'effet actif
        if duration and game_id not in self.active_effects:
            self.active_effects[game_id] = {}

        if duration:
            effect_id = f"{effect_type.value}_{time.time()}"
            self.active_effects[game_id][effect_id] = {
                "type": effect_type.value,
                "affected_players": [str(uid) for uid in affected_players],
                "end_time": time.time() + duration,
                "message": message_text
            }

            # Programmer la fin de l'effet
            asyncio.create_task(self._schedule_effect_end(game_id, effect_id, duration))

        message = WebSocketMessage(
            type="EFFECT_APPLIED",
            data={
                "effect_type": effect_type.value,
                "affected_players": [str(uid) for uid in affected_players],
                "duration": duration,
                "message": message_text,
                "timestamp": time.time()
            }
        )

        await self._broadcast_to_room(game_id, message)

    async def _schedule_effect_end(
            self,
            game_id: str,
            effect_id: str,
            duration: int
    ) -> None:
        """Programme la fin d'un effet"""
        await asyncio.sleep(duration)

        if game_id in self.active_effects and effect_id in self.active_effects[game_id]:
            effect_data = self.active_effects[game_id].pop(effect_id)

            message = WebSocketMessage(
                type="EFFECT_ENDED",
                data={
                    "effect_type": effect_data["type"],
                    "affected_players": effect_data["affected_players"],
                    "timestamp": time.time()
                }
            )

            await self._broadcast_to_room(game_id, message)

    # =====================================================
    # ÉVÉNEMENTS DE CONNEXION
    # =====================================================

    async def notify_player_joined(
            self,
            game_id: str,
            user_id: UUID,
            game_data: Dict[str, Any]
    ) -> None:
        """Notifie qu'un joueur a rejoint la partie"""

        message = WebSocketMessage(
            type=EventType.PLAYER_JOINED,
            data={
                "user_id": str(user_id),
                "game_state": game_data,
                "timestamp": time.time()
            }
        )

        await self._broadcast_to_room(game_id, message)

    async def notify_player_left(
            self,
            game_id: str,
            user_id: UUID
    ) -> None:
        """Notifie qu'un joueur a quitté la partie"""

        username = await self._get_username_in_room(game_id, str(user_id))

        message = WebSocketMessage(
            type=EventType.PLAYER_LEFT,
            data={
                "user_id": str(user_id),
                "username": username,
                "timestamp": time.time()
            }
        )

        await self._broadcast_to_room(game_id, message)

    async def notify_game_started(self, game_id: str) -> None:
        """Notifie que la partie a commencé"""

        async with self._lock:
            if game_id in self.multiplayer_rooms:
                self.multiplayer_rooms[game_id]["game_status"] = "active"

                # Mettre tous les joueurs en statut "playing"
                for player in self.multiplayer_rooms[game_id]["players"].values():
                    player["status"] = PlayerStatus.PLAYING.value

        message = WebSocketMessage(
            type=EventType.GAME_STARTED,
            data={
                "game_id": game_id,
                "started_at": time.time()
            }
        )

        await self._broadcast_to_room(game_id, message)

    # =====================================================
    # MISES À JOUR D'ÉTAT
    # =====================================================

    async def notify_player_status_changed(
            self,
            game_id: str,
            user_id: UUID,
            old_status: PlayerStatus,
            new_status: PlayerStatus,
            additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Notifie un changement de statut de joueur"""

        async with self._lock:
            if game_id in self.multiplayer_rooms:
                room = self.multiplayer_rooms[game_id]
                user_id_str = str(user_id)

                if user_id_str in room["players"]:
                    room["players"][user_id_str]["status"] = new_status.value

        message = WebSocketMessage(
            type="PLAYER_STATUS_CHANGED",
            data={
                "user_id": str(user_id),
                "username": await self._get_username_in_room(game_id, str(user_id)),
                "old_status": old_status.value,
                "new_status": new_status.value,
                "additional_data": additional_data or {},
                "timestamp": time.time()
            }
        )

        await self._broadcast_to_room(game_id, message)

    async def notify_game_state_update(
            self,
            game_id: str,
            state_update: Dict[str, Any]
    ) -> None:
        """Notifie une mise à jour de l'état de la partie"""

        message = WebSocketMessage(
            type=EventType.GAME_STATE_UPDATE,
            data={
                "game_id": game_id,
                "updates": state_update,
                "timestamp": time.time()
            }
        )

        await self._broadcast_to_room(game_id, message)

    # =====================================================
    # UTILITAIRES PRIVÉS
    # =====================================================

    async def _broadcast_to_room(
            self,
            room_id: str,
            message: WebSocketMessage,
            exclude_connection: Optional[str] = None
    ) -> None:
        """Diffuse un message à tous les participants d'une room"""
        await self.base_manager.broadcast_to_room(room_id, message, exclude_connection)

    async def _get_username_in_room(self, game_id: str, user_id: str) -> str:
        """Récupère le nom d'utilisateur dans une room"""
        if game_id in self.multiplayer_rooms:
            room = self.multiplayer_rooms[game_id]
            if user_id in room["players"]:
                return room["players"][user_id]["username"]
        return "Unknown"

    async def _get_player_score(self, game_id: str, user_id: str) -> int:
        """Récupère le score d'un joueur"""
        if game_id in self.multiplayer_rooms:
            room = self.multiplayer_rooms[game_id]
            if user_id in room["players"]:
                return room["players"][user_id]["score"]
        return 0

    async def _get_final_ranking(self, game_id: str) -> List[Dict[str, Any]]:
        """Récupère le classement final de la partie"""
        if game_id not in self.multiplayer_rooms:
            return []

        room = self.multiplayer_rooms[game_id]
        players = []

        for user_id, player_data in room["players"].items():
            players.append({
                "user_id": user_id,
                "username": player_data["username"],
                "score": player_data["score"],
                "status": player_data["status"],
                "final_position": player_data.get("final_position", 999)
            })

        # Trier par position finale puis par score
        players.sort(key=lambda x: (x["final_position"], -x["score"]))

        return players

    async def get_room_info(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les informations d'une room"""
        return self.multiplayer_rooms.get(game_id)

    async def get_active_effects(self, game_id: str) -> Dict[str, Any]:
        """Récupère les effets actifs dans une partie"""
        return self.active_effects.get(game_id, {})

    async def cleanup_finished_game(self, game_id: str) -> None:
        """Nettoie les données d'une partie terminée"""
        async with self._lock:
            self.multiplayer_rooms.pop(game_id, None)
            self.active_effects.pop(game_id, None)

    # =====================================================
    # GESTIONNAIRE D'ÉVÉNEMENTS SPÉCIALISÉS
    # =====================================================

    async def handle_multiplayer_message(
            self,
            connection_id: str,
            message_type: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère les messages spécifiques au multijoueur"""

        if message_type == "JOIN_MULTIPLAYER_ROOM":
            game_id = data.get("game_id")
            user_data = data.get("user_data", {})

            if game_id:
                await self.join_multiplayer_room(connection_id, game_id, user_data)

        elif message_type == "LEAVE_MULTIPLAYER_ROOM":
            game_id = data.get("game_id")

            if game_id:
                await self.leave_multiplayer_room(connection_id, game_id)

        elif message_type == "REQUEST_ROOM_INFO":
            game_id = data.get("game_id")

            if game_id:
                room_info = await self.get_room_info(game_id)

                response = WebSocketMessage(
                    type="ROOM_INFO_RESPONSE",
                    data={
                        "game_id": game_id,
                        "room_info": room_info
                    }
                )

                await self.base_manager.send_to_connection(connection_id, response)

        elif message_type == "REQUEST_ACTIVE_EFFECTS":
            game_id = data.get("game_id")

            if game_id:
                effects = await self.get_active_effects(game_id)

                response = WebSocketMessage(
                    type="ACTIVE_EFFECTS_RESPONSE",
                    data={
                        "game_id": game_id,
                        "active_effects": effects
                    }
                )

                await self.base_manager.send_to_connection(connection_id, response)
