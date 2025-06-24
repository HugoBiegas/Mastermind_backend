"""
Gestionnaire WebSocket pour le multijoueur en temps réel
COMPLET: Communication temps réel pour toutes les fonctionnalités multijoueur
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class MultiplayerWebSocketManager:
    """Gestionnaire WebSocket pour les parties multijoueur"""

    def __init__(self):
        # Connexions actives par room
        self.room_connections: Dict[str, Set[WebSocket]] = {}

        # Mapping connexion -> room_code
        self.connection_rooms: Dict[WebSocket, str] = {}

        # Mapping connexion -> user_id
        self.connection_users: Dict[WebSocket, str] = {}

        # CORRECTION: Mapping user_id -> room_code pour éviter les doublons
        self.user_room_mapping: Dict[str, str] = {}

        # Informations des rooms actives
        self.multiplayer_rooms: Dict[str, Dict[str, Any]] = {}

        # Effets actifs par room
        self.active_effects: Dict[str, List[Dict[str, Any]]] = {}

        # Tâches en arrière-plan
        self.background_tasks: Set[asyncio.Task] = set()

        logger.info("🌐 MultiplayerWebSocketManager initialisé")


    # =====================================================
    # GESTION DES CONNEXIONS
    # =====================================================

    async def connect(self, websocket: WebSocket, room_code: str, user_id: str):
        """Connecte un client WebSocket à une room"""
        try:
            await websocket.accept()

            # Vérifier si l'utilisateur est déjà connecté ailleurs
            if user_id in self.user_room_mapping:
                existing_room = self.user_room_mapping[user_id]
                if existing_room != room_code:
                    await self._disconnect_user_from_room(user_id, existing_room)
                    logger.info(f"🔄 Utilisateur {user_id} déplacé de {existing_room} vers {room_code}")
                elif existing_room == room_code:
                    await self._cleanup_duplicate_connection(user_id, room_code)

            # Ajouter la connexion à la room
            if room_code not in self.room_connections:
                self.room_connections[room_code] = set()

            self.room_connections[room_code].add(websocket)
            self.connection_rooms[websocket] = room_code
            self.connection_users[websocket] = user_id
            self.user_room_mapping[user_id] = room_code

            # Initialiser la room si nécessaire
            if room_code not in self.multiplayer_rooms:
                self.multiplayer_rooms[room_code] = {
                    "created_at": datetime.now(timezone.utc),
                    "players": {},
                    "status": "waiting",
                    "current_mastermind": 1
                }

            # Ajouter le joueur à la room
            self.multiplayer_rooms[room_code]["players"][user_id] = {
                "connected_at": datetime.now(timezone.utc),
                "last_activity": datetime.now(timezone.utc),
                "websocket": websocket,
                "ready": False
            }

            logger.info(f"🔌 Utilisateur {user_id} connecté à la room {room_code}")

            # CORRECTION: Utiliser la nouvelle méthode de notification
            await self.notify_player_joined(room_code, user_id)

            # Envoyer l'état actuel au nouveau client
            await self.send_room_state(websocket, room_code)

        except Exception as e:
            logger.error(f"❌ Erreur lors de la connexion WebSocket: {e}")
            try:
                await websocket.close()
            except:
                pass

    async def _disconnect_user_from_room(self, user_id: str, room_code: str):
        """Déconnecte un utilisateur d'une room spécifique"""
        try:
            if room_code in self.room_connections:
                # Trouver et fermer les connexions de cet utilisateur dans cette room
                connections_to_remove = []
                for websocket in self.room_connections[room_code]:
                    if self.connection_users.get(websocket) == user_id:
                        connections_to_remove.append(websocket)

                for websocket in connections_to_remove:
                    await self.disconnect(websocket, room_code)

        except Exception as e:
            logger.error(f"❌ Erreur déconnexion utilisateur {user_id} de {room_code}: {e}")

    async def _cleanup_duplicate_connection(self, user_id: str, room_code: str):
        """Nettoie les connexions dupliquées d'un utilisateur"""
        try:
            if room_code in self.room_connections:
                connections_to_close = []
                for websocket in self.room_connections[room_code]:
                    if self.connection_users.get(websocket) == user_id:
                        connections_to_close.append(websocket)

                # Fermer toutes les connexions existantes sauf la plus récente
                for websocket in connections_to_close[:-1]:  # Garder la dernière
                    try:
                        await websocket.close(1000, "Duplicate connection")
                    except:
                        pass
                    self._cleanup_connection_mappings(websocket, room_code)

        except Exception as e:
            logger.error(f"❌ Erreur nettoyage connexions dupliquées: {e}")

    def _cleanup_connection_mappings(self, websocket: WebSocket, room_code: str):
        """Nettoie les mappings pour une connexion"""
        try:
            # Supprimer de la room
            if room_code in self.room_connections:
                self.room_connections[room_code].discard(websocket)

            # Nettoyer les mappings
            user_id = self.connection_users.get(websocket)
            self.connection_rooms.pop(websocket, None)
            self.connection_users.pop(websocket, None)

            # Nettoyer le mapping utilisateur si c'était sa seule connexion
            if user_id and self.user_room_mapping.get(user_id) == room_code:
                # Vérifier qu'il n'y a plus d'autres connexions pour cet utilisateur
                has_other_connections = any(
                    self.connection_users.get(ws) == user_id
                    for ws in self.room_connections.get(room_code, set())
                )
                if not has_other_connections:
                    self.user_room_mapping.pop(user_id, None)

        except Exception as e:
            logger.error(f"❌ Erreur nettoyage mappings: {e}")

    async def disconnect(self, websocket: WebSocket, room_code: str):
        """Déconnecte un client WebSocket"""
        try:
            user_id = self.connection_users.get(websocket)

            # Nettoyer les mappings
            self._cleanup_connection_mappings(websocket, room_code)

            # Supprimer la room si vide
            if room_code in self.room_connections and not self.room_connections[room_code]:
                del self.room_connections[room_code]
                if room_code in self.multiplayer_rooms:
                    del self.multiplayer_rooms[room_code]
                if room_code in self.active_effects:
                    del self.active_effects[room_code]

            # Supprimer le joueur de la room
            if room_code in self.multiplayer_rooms and user_id:
                self.multiplayer_rooms[room_code]["players"].pop(user_id, None)

            logger.info(f"🔌 Utilisateur {user_id} déconnecté de la room {room_code}")

            # Notifier les autres clients
            if room_code in self.room_connections and user_id:
                await self.notify_room(room_code, {
                    "type": "player_disconnected",
                    "user_id": user_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "connections_count": len(self.room_connections[room_code])
                })

        except Exception as e:
            logger.error(f"❌ Erreur lors de la déconnexion WebSocket: {e}")

    # =====================================================
    # COMMUNICATION BROADCAST
    # =====================================================

    async def notify_room(
            self,
            room_code: str,
            message: Dict[str, Any],
            exclude_websocket: Optional[WebSocket] = None
    ):
        """Envoie un message à tous les clients d'une room"""
        if room_code not in self.room_connections:
            logger.warning(f"⚠️ No connections found for room {room_code}")
            return

        # CORRECTION: Structure standardisée du message
        message_type = message.get("type", "notification")
        message_data = {k: v for k, v in message.items() if k != "type"}

        # Ajouter metadata
        message_data.update({
            "room_code": room_code,
            "server_timestamp": datetime.now(timezone.utc).isoformat()
        })

        # NOUVEAU: Message avec structure standardisée
        standardized_message = {
            "type": message_type,
            "data": message_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "room_code": room_code
        }

        message_json = json.dumps(standardized_message)
        logger.debug(f"📤 Broadcasting message type '{message_type}' to room {room_code}")

        # Liste des connexions à supprimer (fermées)
        dead_connections = set()

        for websocket in self.room_connections[room_code]:
            if websocket == exclude_websocket:
                continue

            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.warning(f"⚠️ Impossible d'envoyer à une connexion: {e}")
                dead_connections.add(websocket)

        # Nettoyer les connexions mortes
        for websocket in dead_connections:
            await self.disconnect(websocket, room_code)

        logger.debug(
            f"✅ Message broadcasted to {len(self.room_connections[room_code]) - len(dead_connections)} clients")

    async def send_personal_message(
            self,
            room_code: str,
            user_id: str,
            message: Dict[str, Any]
    ):
        """Envoie un message personnel à un utilisateur spécifique"""
        if room_code not in self.multiplayer_rooms:
            logger.warning(f"⚠️ Room {room_code} not found for personal message")
            return

        room_data = self.multiplayer_rooms[room_code]
        if user_id not in room_data["players"]:
            logger.warning(f"⚠️ User {user_id} not found in room {room_code}")
            return

        websocket = room_data["players"][user_id].get("websocket")
        if not websocket:
            logger.warning(f"⚠️ No websocket found for user {user_id}")
            return

        # CORRECTION: Structure standardisée du message personnel
        message_type = message.get("type", "personal_message")
        message_data = {k: v for k, v in message.items() if k != "type"}

        message_data.update({
            "target_user_id": user_id,
            "room_code": room_code,
            "server_timestamp": datetime.now(timezone.utc).isoformat()
        })

        # NOUVEAU: Message avec structure standardisée
        standardized_message = {
            "type": message_type,
            "data": message_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "room_code": room_code
        }

        try:
            await websocket.send_text(json.dumps(standardized_message))
            logger.debug(f"✅ Personal message sent to user {user_id}")
        except Exception as e:
            logger.warning(f"⚠️ Impossible d'envoyer message personnel: {e}")

    # =====================================================
    # GESTION DES MESSAGES
    # =====================================================

    async def handle_message(self, room_code: str, message: Dict[str, Any]):
        """Traite un message reçu d'un client"""
        try:
            message_type = message.get("type")
            user_id = message.get("user_id")

            if not message_type or not user_id:
                return

            # Mettre à jour l'activité du joueur
            if room_code in self.multiplayer_rooms and user_id in self.multiplayer_rooms[room_code]["players"]:
                self.multiplayer_rooms[room_code]["players"][user_id]["last_activity"] = datetime.now(timezone.utc)

            # Router selon le type de message
            if message_type == "chat_message":
                await self.handle_chat_message(room_code, user_id, message)
            elif message_type == "player_ready":
                await self.handle_player_ready(room_code, user_id, message)
            elif message_type == "attempt_submitted":
                await self.handle_attempt_submitted(room_code, user_id, message)
            elif message_type == "item_used":
                await self.handle_item_used(room_code, user_id, message)
            elif message_type == "quantum_hint_used":
                await self.handle_quantum_hint_used(room_code, user_id, message)
            elif message_type == "heartbeat":
                await self.handle_heartbeat(room_code, user_id, message)
            else:
                logger.warning(f"⚠️ Type de message inconnu: {message_type}")

        except Exception as e:
            logger.error(f"❌ Erreur traitement message: {e}")

    async def handle_chat_message(self, room_code: str, user_id: str, message: Dict[str, Any]):
        """Traite un message de chat"""
        chat_content = message.get("message", "").strip()
        if not chat_content or len(chat_content) > 500:
            return

        # CORRECTION: Structure standardisée pour les messages de chat
        await self.notify_room(room_code, {
            "type": "chat_message",
            "user_id": user_id,
            "username": message.get("username", "Anonyme"),
            "message": chat_content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    async def notify_player_joined(self, room_code: str, user_id: str, username: str = None):
        """Notifie qu'un joueur a rejoint la room"""
        await self.notify_room(room_code, {
            "type": "player_connected",
            "user_id": user_id,
            "username": username or f"Joueur-{user_id[:8]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "connections_count": len(self.room_connections.get(room_code, []))
        })

    # NOUVEAU: Méthode pour notifier le départ d'un joueur
    async def notify_player_left(self, room_code: str, user_id: str, username: str = None):
        """Notifie qu'un joueur a quitté la room"""
        await self.notify_room(room_code, {
            "type": "player_disconnected",
            "user_id": user_id,
            "username": username or f"Joueur-{user_id[:8]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "connections_count": len(self.room_connections.get(room_code, []))
        })

    async def handle_player_ready(self, room_code: str, user_id: str, message: Dict[str, Any]):
        """Traite l'état de préparation d'un joueur"""
        is_ready = message.get("ready", False)

        # Mettre à jour l'état du joueur
        if room_code in self.multiplayer_rooms:
            if user_id not in self.multiplayer_rooms[room_code]["players"]:
                self.multiplayer_rooms[room_code]["players"][user_id] = {}

            self.multiplayer_rooms[room_code]["players"][user_id]["ready"] = is_ready

        # Notifier les autres joueurs
        await self.notify_room(room_code, {
            "type": "player_ready_changed",
            "user_id": user_id,
            "ready": is_ready,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    async def handle_attempt_submitted(self, room_code: str, user_id: str, message: Dict[str, Any]):
        """Traite une tentative soumise"""
        attempt_data = message.get("attempt_data", {})

        # Notifier les autres joueurs (sans révéler la combinaison)
        await self.notify_room(room_code, {
            "type": "attempt_submitted",
            "user_id": user_id,
            "mastermind_number": attempt_data.get("mastermind_number", 1),
            "attempt_number": attempt_data.get("attempt_number", 1),
            "is_winning": attempt_data.get("is_winning", False),
            "score": attempt_data.get("score", 0),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, exclude_websocket=self._get_user_websocket(room_code, user_id))

    async def handle_item_used(self, room_code: str, user_id: str, message: Dict[str, Any]):
        """Traite l'utilisation d'un objet"""
        item_data = message.get("item_data", {})
        item_type = item_data.get("item_type")
        target_user_id = item_data.get("target_user_id")

        # Appliquer l'effet s'il y a une cible
        if target_user_id and item_type:
            await self.apply_item_effect(room_code, user_id, target_user_id, item_type, item_data)

        # Notifier tous les joueurs
        await self.notify_room(room_code, {
            "type": "item_used",
            "user_id": user_id,
            "item_type": item_type,
            "target_user_id": target_user_id,
            "effect_applied": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    async def handle_quantum_hint_used(self, room_code: str, user_id: str, message: Dict[str, Any]):
        """Traite l'utilisation d'un indice quantique"""
        hint_data = message.get("hint_data", {})
        hint_type = hint_data.get("hint_type")
        cost = hint_data.get("cost", 0)

        # Notifier les autres joueurs
        await self.notify_room(room_code, {
            "type": "quantum_hint_used",
            "user_id": user_id,
            "hint_type": hint_type,
            "cost": cost,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, exclude_websocket=self._get_user_websocket(room_code, user_id))

    async def handle_heartbeat(self, room_code: str, user_id: str, message: Dict[str, Any]):
        """Traite un heartbeat pour maintenir la connexion"""
        # Mettre à jour le timestamp d'activité
        if room_code in self.multiplayer_rooms and user_id in self.multiplayer_rooms[room_code]["players"]:
            self.multiplayer_rooms[room_code]["players"][user_id]["last_heartbeat"] = datetime.now(timezone.utc)

    # =====================================================
    # GESTION DES EFFETS
    # =====================================================

    async def apply_item_effect(
        self,
        room_code: str,
        source_user_id: str,
        target_user_id: str,
        item_type: str,
        item_data: Dict[str, Any]
    ):
        """Applique l'effet d'un objet sur un joueur cible"""
        try:
            if room_code not in self.active_effects:
                self.active_effects[room_code] = []

            effect = {
                "effect_id": f"{source_user_id}_{target_user_id}_{datetime.now().timestamp()}",
                "source_user_id": source_user_id,
                "target_user_id": target_user_id,
                "item_type": item_type,
                "applied_at": datetime.now(timezone.utc),
                "duration_seconds": item_data.get("duration_seconds"),
                "effect_value": item_data.get("effect_value"),
                "parameters": item_data.get("parameters", {})
            }

            self.active_effects[room_code].append(effect)

            # Programmer la suppression de l'effet si durée limitée
            if effect["duration_seconds"]:
                task = asyncio.create_task(
                    self._remove_effect_after_delay(room_code, effect["effect_id"], effect["duration_seconds"])
                )
                self.background_tasks.add(task)
                task.add_done_callback(self.background_tasks.discard)

            # Notifier la cible de l'effet appliqué
            await self.send_personal_message(target_user_id, room_code, {
                "type": "effect_applied",
                "effect": effect
            })

            logger.info(f"🎁 Effet {item_type} appliqué de {source_user_id} vers {target_user_id}")

        except Exception as e:
            logger.error(f"❌ Erreur application effet: {e}")

    async def _remove_effect_after_delay(self, room_code: str, effect_id: str, delay_seconds: int):
        """Supprime un effet après un délai"""
        await asyncio.sleep(delay_seconds)

        if room_code not in self.active_effects:
            return

        # Trouver et supprimer l'effet
        for i, effect in enumerate(self.active_effects[room_code]):
            if effect["effect_id"] == effect_id:
                removed_effect = self.active_effects[room_code].pop(i)

                # Notifier la fin de l'effet
                await self.send_personal_message(room_code, removed_effect["target_user_id"], {
                    "type": "effect_expired",
                    "effect_id": effect_id,
                    "item_type": removed_effect["item_type"]
                })

                break

    # =====================================================
    # MÉTHODES UTILITAIRES
    # =====================================================

    async def send_room_state(self, websocket: WebSocket, room_code: str):
        """Envoie l'état actuel de la room à un client"""
        if room_code not in self.multiplayer_rooms:
            logger.warning(f"⚠️ Room {room_code} not found for room state")
            return

        room_data = self.multiplayer_rooms[room_code]

        # Construire l'état de la room
        players_info = []
        for user_id, player_data in room_data["players"].items():
            players_info.append({
                "user_id": user_id,
                "connected_at": player_data.get("connected_at", datetime.now(timezone.utc)).isoformat(),
                "ready": player_data.get("ready", False),
                "is_ready": player_data.get("ready", False),  # CORRECTION: Alias pour compatibilité
                "last_activity": player_data.get("last_activity", datetime.now(timezone.utc)).isoformat()
            })

        # CORRECTION: Structure standardisée du message WebSocket
        state_data = {
            "room_code": room_code,
            "status": room_data.get("status", "waiting"),
            "current_mastermind": room_data.get("current_mastermind", 1),
            "players": players_info,
            "connections_count": len(self.room_connections.get(room_code, [])),
            "active_effects": self.active_effects.get(room_code, []),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # NOUVEAU: Message avec structure standardisée
        message = {
            "type": "room_state",
            "data": state_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "room_code": room_code
        }

        try:
            await websocket.send_text(json.dumps(message))
            logger.debug(f"✅ Room state sent to client in room {room_code}")
        except Exception as e:
            logger.warning(f"⚠️ Impossible d'envoyer l'état de la room: {e}")

    def _get_user_websocket(self, room_code: str, user_id: str) -> Optional[WebSocket]:
        """Récupère la connexion WebSocket d'un utilisateur"""
        if room_code not in self.multiplayer_rooms:
            return None

        room_data = self.multiplayer_rooms[room_code]
        if user_id not in room_data["players"]:
            return None

        return room_data["players"][user_id].get("websocket")

    def get_room_stats(self, room_code: str) -> Dict[str, Any]:
        """Récupère les statistiques d'une room"""
        if room_code not in self.multiplayer_rooms:
            return {}

        room_data = self.multiplayer_rooms[room_code]
        connections = self.room_connections.get(room_code, set())

        return {
            "room_code": room_code,
            "total_players": len(room_data["players"]),
            "active_connections": len(connections),
            "status": room_data.get("status", "unknown"),
            "created_at": room_data.get("created_at", datetime.now(timezone.utc)).isoformat(),
            "active_effects_count": len(self.active_effects.get(room_code, [])),
            "background_tasks_count": len(self.background_tasks)
        }

    async def cleanup_inactive_connections(self):
        """Nettoie les connexions inactives (tâche périodique)"""
        now = datetime.now(timezone.utc)
        timeout_seconds = 300  # 5 minutes

        rooms_to_cleanup = []

        for room_code, room_data in self.multiplayer_rooms.items():
            inactive_users = []

            for user_id, player_data in room_data["players"].items():
                last_activity = player_data.get("last_activity", now)
                if (now - last_activity).total_seconds() > timeout_seconds:
                    inactive_users.append(user_id)

            # Supprimer les utilisateurs inactifs
            for user_id in inactive_users:
                websocket = player_data.get("websocket")
                if websocket:
                    try:
                        await self.disconnect(websocket, room_code)
                    except:
                        pass

            # Marquer les rooms vides pour suppression
            if not room_data["players"]:
                rooms_to_cleanup.append(room_code)

        # Nettoyer les rooms vides
        for room_code in rooms_to_cleanup:
            self.multiplayer_rooms.pop(room_code, None)
            self.room_connections.pop(room_code, None)
            self.active_effects.pop(room_code, None)

    async def shutdown(self):
        """Ferme proprement le gestionnaire WebSocket"""
        logger.info("🔌 Arrêt du gestionnaire WebSocket multijoueur...")

        # Fermer toutes les connexions
        for room_code, connections in self.room_connections.items():
            for websocket in connections.copy():
                try:
                    await websocket.close(code=1001, reason="Arrêt du serveur")
                except:
                    pass

        # Annuler toutes les tâches en arrière-plan
        for task in self.background_tasks:
            task.cancel()

        # Attendre que toutes les tâches se terminent
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)

        # Nettoyer les données
        self.room_connections.clear()
        self.connection_rooms.clear()
        self.connection_users.clear()
        self.multiplayer_rooms.clear()
        self.active_effects.clear()

        logger.info("✅ Gestionnaire WebSocket fermé proprement")


# =====================================================
# INSTANCE GLOBALE ET FONCTIONS D'INITIALISATION
# =====================================================

# Instance globale du gestionnaire
multiplayer_ws_manager = MultiplayerWebSocketManager()

async def initialize_multiplayer_websocket():
    """Initialise le gestionnaire WebSocket multijoueur"""
    logger.info("🚀 Initialisation du système WebSocket multijoueur...")

    # Démarrer la tâche de nettoyage périodique
    cleanup_task = asyncio.create_task(periodic_cleanup())
    multiplayer_ws_manager.background_tasks.add(cleanup_task)

    logger.info("✅ Système WebSocket multijoueur initialisé")

async def periodic_cleanup():
    """Tâche de nettoyage périodique"""
    while True:
        try:
            await asyncio.sleep(60)  # Nettoyer toutes les minutes
            await multiplayer_ws_manager.cleanup_inactive_connections()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Erreur lors du nettoyage périodique: {e}")

async def cleanup_task():
    """Nettoie les ressources WebSocket au shutdown"""
    await multiplayer_ws_manager.shutdown()

# Export des fonctions pour l'intégration
__all__ = [
    "multiplayer_ws_manager",
    "initialize_multiplayer_websocket",
    "cleanup_task",
    "MultiplayerWebSocketManager"
]