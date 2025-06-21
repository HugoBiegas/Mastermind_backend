"""
Gestionnaire WebSocket spécialisé pour le multijoueur
Communication temps réel pour les parties multijoueur
COMPLET - Version finale avec toutes les fonctionnalités
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

            # Ajouter le joueur aux métadonnées
            room["players"][connection_id] = {
                "user_id": user_data.get("user_id"),
                "username": user_data.get("username"),
                "status": PlayerStatus.WAITING,
                "joined_at": time.time(),
                "current_mastermind": 1,
                "score": 0,
                "items": []
            }

            room["current_players"] += 1

            # Notifier les autres joueurs
            await self.broadcast_to_room(game_id, {
                "type": "PLAYER_JOINED",
                "data": {
                    "username": user_data.get("username"),
                    "players_count": room["current_players"]
                }
            }, exclude_connection=connection_id)

        return True

    async def leave_multiplayer_room(
            self,
            connection_id: str,
            game_id: str
    ) -> None:
        """Fait quitter un joueur d'une room multijoueur"""

        async with self._lock:
            if game_id in self.multiplayer_rooms:
                room = self.multiplayer_rooms[game_id]

                if connection_id in room["players"]:
                    player_data = room["players"].pop(connection_id)
                    room["current_players"] -= 1

                    # Notifier les autres joueurs
                    await self.broadcast_to_room(game_id, {
                        "type": "PLAYER_LEFT",
                        "data": {
                            "username": player_data.get("username"),
                            "players_count": room["current_players"]
                        }
                    })

                # Supprimer la room si vide
                if room["current_players"] == 0:
                    del self.multiplayer_rooms[game_id]

        # Quitter la room de base
        await self.base_manager.leave_game_room(connection_id, game_id)

    # =====================================================
    # ÉVÉNEMENTS DE JEU
    # =====================================================

    async def start_multiplayer_game(self, game_id: str) -> None:
        """Démarre une partie multijoueur"""
        async with self._lock:
            if game_id in self.multiplayer_rooms:
                room = self.multiplayer_rooms[game_id]
                room["game_status"] = "active"

                # Mettre tous les joueurs en mode PLAYING
                for player_data in room["players"].values():
                    player_data["status"] = PlayerStatus.PLAYING

        await self.broadcast_to_room(game_id, {
            "type": "GAME_STARTED",
            "data": {
                "game_id": game_id,
                "current_mastermind": 1
            }
        })

    async def player_mastermind_complete(
            self,
            game_id: str,
            connection_id: str,
            mastermind_number: int,
            score: int,
            items_obtained: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Notifie qu'un joueur a terminé un mastermind"""

        async with self._lock:
            if game_id in self.multiplayer_rooms:
                room = self.multiplayer_rooms[game_id]

                if connection_id in room["players"]:
                    player_data = room["players"][connection_id]
                    player_data["current_mastermind"] = mastermind_number + 1
                    player_data["score"] += score
                    player_data["status"] = PlayerStatus.MASTERMIND_COMPLETE

                    # Ajouter les objets obtenus
                    if items_obtained:
                        player_data["items"].extend(items_obtained)

        await self.broadcast_to_room(game_id, {
            "type": "PLAYER_MASTERMIND_COMPLETE",
            "data": {
                "player_id": connection_id,
                "username": room["players"][connection_id]["username"],
                "mastermind_number": mastermind_number,
                "score": score,
                "items_obtained": items_obtained or []
            }
        })

    async def use_item(
            self,
            game_id: str,
            connection_id: str,
            item_type: ItemType,
            target_players: Optional[List[str]] = None
    ) -> None:
        """Gère l'utilisation d'un objet"""

        async with self._lock:
            if game_id not in self.multiplayer_rooms:
                return

            room = self.multiplayer_rooms[game_id]

            if connection_id not in room["players"]:
                return

            player_data = room["players"][connection_id]
            username = player_data["username"]

        # Appliquer les effets selon le type d'objet
        if item_type in [ItemType.EXTRA_HINT, ItemType.TIME_BONUS,
                        ItemType.SKIP_MASTERMIND, ItemType.DOUBLE_SCORE]:
            # Bonus pour soi
            await self._apply_bonus_effect(game_id, connection_id, item_type)

        elif item_type in [ItemType.FREEZE_TIME, ItemType.ADD_MASTERMIND,
                          ItemType.REDUCE_ATTEMPTS, ItemType.SCRAMBLE_COLORS]:
            # Malus pour les autres
            targets = target_players or [
                pid for pid in room["players"].keys() if pid != connection_id
            ]
            await self._apply_malus_effect(game_id, item_type, targets)

        # Notifier l'utilisation
        await self.broadcast_to_room(game_id, {
            "type": "ITEM_USED",
            "data": {
                "player_id": connection_id,
                "username": username,
                "item_type": item_type,
                "target_players": target_players,
                "message": self._get_item_message(item_type, username)
            }
        })

    async def apply_effect(
            self,
            game_id: str,
            effect_type: ItemType,
            target_players: List[str],
            duration: int = 30,
            message: str = ""
    ) -> None:
        """Applique un effet temporaire"""

        effect_id = f"{game_id}_{effect_type}_{int(time.time())}"

        async with self._lock:
            if game_id not in self.active_effects:
                self.active_effects[game_id] = {}

            self.active_effects[game_id][effect_id] = {
                "type": effect_type,
                "target_players": target_players,
                "start_time": time.time(),
                "duration": duration,
                "message": message
            }

        # Notifier les joueurs affectés
        for target_id in target_players:
            await self.send_to_connection(target_id, {
                "type": "EFFECT_APPLIED",
                "data": {
                    "effect_id": effect_id,
                    "effect_type": effect_type,
                    "duration": duration,
                    "message": message
                }
            })

        # Programmer la fin de l'effet
        asyncio.create_task(self._remove_effect_after_delay(game_id, effect_id, duration))

    async def update_game_progress(
            self,
            game_id: str,
            current_mastermind: int,
            is_final_mastermind: bool,
            player_progresses: List[Dict[str, Any]]
    ) -> None:
        """Met à jour la progression de la partie"""

        await self.broadcast_to_room(game_id, {
            "type": "GAME_PROGRESS_UPDATE",
            "data": {
                "current_mastermind": current_mastermind,
                "is_final_mastermind": is_final_mastermind,
                "player_progresses": player_progresses
            }
        })

    async def finish_multiplayer_game(
            self,
            game_id: str,
            final_leaderboard: List[Dict[str, Any]]
    ) -> None:
        """Termine une partie multijoueur"""

        async with self._lock:
            if game_id in self.multiplayer_rooms:
                room = self.multiplayer_rooms[game_id]
                room["game_status"] = "finished"

        await self.broadcast_to_room(game_id, {
            "type": "MULTIPLAYER_GAME_FINISHED",
            "data": {
                "final_leaderboard": final_leaderboard,
                "game_id": game_id
            }
        })

    # =====================================================
    # MÉTHODES UTILITAIRES
    # =====================================================

    async def broadcast_to_room(
            self,
            game_id: str,
            message: Dict[str, Any],
            exclude_connection: Optional[str] = None
    ) -> None:
        """Diffuse un message à tous les joueurs d'une room"""
        await self.base_manager.broadcast_to_room(game_id, message, exclude_connection)

    async def send_to_connection(
            self,
            connection_id: str,
            message: Dict[str, Any]
    ) -> None:
        """Envoie un message à une connexion spécifique"""
        await self.base_manager.send_to_connection(connection_id, message)

    async def _apply_bonus_effect(
            self,
            game_id: str,
            connection_id: str,
            item_type: ItemType
    ) -> None:
        """Applique un effet bonus sur le joueur"""

        # Les effets bonus sont principalement gérés côté frontend
        # Ici on peut ajouter de la logique métier si nécessaire

        if item_type == ItemType.TIME_BONUS:
            await self.apply_effect(
                game_id, item_type, [connection_id],
                duration=60, message="⏰ Temps bonus activé !"
            )
        elif item_type == ItemType.DOUBLE_SCORE:
            await self.apply_effect(
                game_id, item_type, [connection_id],
                duration=300, message="⭐ Score doublé pour le prochain mastermind !"
            )

    async def _apply_malus_effect(
            self,
            game_id: str,
            item_type: ItemType,
            target_players: List[str]
    ) -> None:
        """Applique un effet malus sur les joueurs cibles"""

        duration = 30
        message = ""

        if item_type == ItemType.FREEZE_TIME:
            duration = 15
            message = "🧊 Temps figé !"
        elif item_type == ItemType.SCRAMBLE_COLORS:
            duration = 45
            message = "🌈 Couleurs mélangées !"
        elif item_type == ItemType.REDUCE_ATTEMPTS:
            duration = 120
            message = "⚠️ Tentatives réduites !"

        await self.apply_effect(game_id, item_type, target_players, duration, message)

    async def _remove_effect_after_delay(
            self,
            game_id: str,
            effect_id: str,
            delay: int
    ) -> None:
        """Supprime un effet après un délai"""
        await asyncio.sleep(delay)

        async with self._lock:
            if (game_id in self.active_effects and
                effect_id in self.active_effects[game_id]):
                del self.active_effects[game_id][effect_id]

    def _get_item_message(self, item_type: ItemType, username: str) -> str:
        """Génère un message pour l'utilisation d'un objet"""

        messages = {
            ItemType.EXTRA_HINT: f"💡 {username} a utilisé un indice supplémentaire",
            ItemType.TIME_BONUS: f"⏰ {username} a gagné du temps bonus",
            ItemType.SKIP_MASTERMIND: f"⏭️ {username} a passé un mastermind",
            ItemType.DOUBLE_SCORE: f"⭐ {username} a doublé son score",
            ItemType.FREEZE_TIME: f"🧊 {username} a figé le temps des adversaires",
            ItemType.ADD_MASTERMIND: f"➕ {username} a ajouté un mastermind à tous",
            ItemType.REDUCE_ATTEMPTS: f"⚠️ {username} a réduit les tentatives des adversaires",
            ItemType.SCRAMBLE_COLORS: f"🌈 {username} a mélangé les couleurs des adversaires"
        }

        return messages.get(item_type, f"{username} a utilisé un objet")

    async def get_room_info(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les informations d'une room"""
        async with self._lock:
            return self.multiplayer_rooms.get(game_id)

    async def update_player_status(
            self,
            game_id: str,
            connection_id: str,
            status: PlayerStatus
    ) -> None:
        """Met à jour le statut d'un joueur"""

        async with self._lock:
            if (game_id in self.multiplayer_rooms and
                connection_id in self.multiplayer_rooms[game_id]["players"]):

                old_status = self.multiplayer_rooms[game_id]["players"][connection_id]["status"]
                self.multiplayer_rooms[game_id]["players"][connection_id]["status"] = status

                username = self.multiplayer_rooms[game_id]["players"][connection_id]["username"]

        # Notifier le changement de statut
        await self.broadcast_to_room(game_id, {
            "type": "PLAYER_STATUS_CHANGED",
            "data": {
                "player_id": connection_id,
                "username": username,
                "old_status": old_status,
                "new_status": status
            }
        })

    async def cleanup_room(self, game_id: str) -> None:
        """Nettoie une room et ses effets"""
        async with self._lock:
            if game_id in self.multiplayer_rooms:
                del self.multiplayer_rooms[game_id]

            if game_id in self.active_effects:
                del self.active_effects[game_id]


# Instance globale du gestionnaire multijoueur
multiplayer_ws_manager = MultiplayerWebSocketManager(None)  # Sera initialisé avec le base_manager


def initialize_multiplayer_websocket(base_manager: WebSocketManager) -> MultiplayerWebSocketManager:
    """Initialise le gestionnaire multijoueur avec le gestionnaire de base"""
    global multiplayer_ws_manager
    multiplayer_ws_manager.base_manager = base_manager
    return multiplayer_ws_manager