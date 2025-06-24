"""
Gestionnaire WebSocket pour le multijoueur en temps réel - VERSION CORRIGÉE COMPLÈTE
Résout tous les problèmes de connexion, chat et synchronisation
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Set, Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class MultiplayerWebSocketManager:
    """Gestionnaire WebSocket pour les parties multijoueur - VERSION CORRIGÉE COMPLÈTE"""

    def __init__(self):
        # Connexions actives par room : room_code -> Set[WebSocket]
        self.room_connections: Dict[str, Set[WebSocket]] = {}

        # Mapping connexion -> room_code
        self.connection_rooms: Dict[WebSocket, str] = {}

        # Mapping connexion -> user_id
        self.connection_users: Dict[WebSocket, str] = {}

        # Mapping connexion -> username pour l'affichage
        self.connection_usernames: Dict[WebSocket, str] = {}

        # CORRECTION: Mapping user_id -> room_code (UN SEUL par user)
        self.user_room_mapping: Dict[str, str] = {}

        # CORRECTION: Mapping user_id -> websocket (UNE SEULE connexion par user)
        self.user_websockets: Dict[str, WebSocket] = {}

        # Informations des rooms actives
        self.multiplayer_rooms: Dict[str, Dict[str, Any]] = {}

        # Lock pour éviter les races conditions
        self.connection_lock = asyncio.Lock()

        # Statistiques
        self.stats = {
            "total_connections": 0,
            "active_rooms": 0,
            "messages_sent": 0
        }

        logger.info("🌐 MultiplayerWebSocketManager initialisé (VERSION CORRIGÉE COMPLÈTE)")

    async def connect(self, websocket: WebSocket, room_code: str, user_id: str, username: str = None):
        """Connecte un client WebSocket - VERSION CORRIGÉE COMPLÈTE"""
        async with self.connection_lock:
            try:
                await websocket.accept()
                logger.info(f"🔌 Tentative connexion {user_id} à {room_code}")

                # CORRECTION: Nettoyer les anciennes connexions de cet utilisateur
                await self._cleanup_old_user_connections(user_id)

                # Ajouter la nouvelle connexion
                if room_code not in self.room_connections:
                    self.room_connections[room_code] = set()
                    self.stats["active_rooms"] = len(self.room_connections)

                self.room_connections[room_code].add(websocket)
                self.connection_rooms[websocket] = room_code
                self.connection_users[websocket] = user_id
                self.connection_usernames[websocket] = username or f"User {user_id}"
                self.user_room_mapping[user_id] = room_code
                self.user_websockets[user_id] = websocket

                self.stats["total_connections"] += 1

                logger.info(f"✅ User {username or user_id} connecté à {room_code} ({len(self.room_connections[room_code])} joueurs)")

                # Confirmer la connexion
                await self._send_to_connection(websocket, {
                    "type": "connection_established",
                    "data": {
                        "room_code": room_code,
                        "user_id": user_id,
                        "username": username,
                        "connected_players": len(self.room_connections[room_code]),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "status": "connected"
                    }
                })

                # Notifier les autres dans la room
                await self.broadcast_to_room(room_code, {
                    "type": "player_joined",
                    "data": {
                        "user_id": user_id,
                        "username": username or f"User {user_id}",
                        "room_code": room_code,
                        "connected_players": len(self.room_connections[room_code]),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }, exclude_websocket=websocket)

                return True

            except Exception as e:
                logger.error(f"❌ Erreur connexion {user_id} à {room_code}: {e}")
                try:
                    await websocket.close(code=1011, reason="Connection error")
                except:
                    pass
                return False

    async def _cleanup_old_user_connections(self, user_id: str):
        """Nettoie les anciennes connexions d'un utilisateur - CORRECTION COMPLÈTE"""
        try:
            # Si l'utilisateur a déjà une connexion active
            if user_id in self.user_websockets:
                old_websocket = self.user_websockets[user_id]
                old_room = self.connection_rooms.get(old_websocket)

                if old_websocket:
                    logger.info(f"🧹 Nettoyage ancienne connexion {user_id} (room: {old_room})")

                    # Fermer l'ancienne connexion
                    try:
                        if not old_websocket.client_state.disconnected:
                            await old_websocket.close(code=1001, reason="New connection")
                    except Exception as close_error:
                        logger.warning(f"⚠️ Erreur fermeture ancienne connexion: {close_error}")

                    # Nettoyer les mappings
                    await self._remove_connection_mappings(old_websocket)

        except Exception as e:
            logger.warning(f"⚠️ Erreur nettoyage {user_id}: {e}")

    async def disconnect(self, websocket: WebSocket):
        """Déconnecte un client WebSocket - VERSION CORRIGÉE COMPLÈTE"""
        async with self.connection_lock:
            try:
                room_code = self.connection_rooms.get(websocket)
                user_id = self.connection_users.get(websocket)
                username = self.connection_usernames.get(websocket, "Joueur inconnu")

                if room_code and user_id:
                    logger.info(f"🔌 Déconnexion {username} ({user_id}) de {room_code}")

                    # Notifier les autres AVANT de nettoyer
                    await self.broadcast_to_room(room_code, {
                        "type": "player_left",
                        "data": {
                            "user_id": user_id,
                            "username": username,
                            "room_code": room_code,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    }, exclude_websocket=websocket)

                # Nettoyer les mappings
                await self._remove_connection_mappings(websocket)

            except Exception as e:
                logger.error(f"❌ Erreur déconnexion: {e}")

    async def _remove_connection_mappings(self, websocket: WebSocket):
        """Supprime tous les mappings pour une connexion - COMPLET"""
        try:
            room_code = self.connection_rooms.get(websocket)
            user_id = self.connection_users.get(websocket)

            # Supprimer de la room
            if room_code and room_code in self.room_connections:
                self.room_connections[room_code].discard(websocket)

                # Supprimer la room si vide
                if not self.room_connections[room_code]:
                    del self.room_connections[room_code]
                    logger.info(f"🗑️ Room {room_code} supprimée (vide)")

                self.stats["active_rooms"] = len(self.room_connections)

            # Supprimer les mappings
            self.connection_rooms.pop(websocket, None)
            self.connection_users.pop(websocket, None)
            self.connection_usernames.pop(websocket, None)

            if user_id:
                # CORRECTION: Seulement si c'est la bonne connexion
                if self.user_websockets.get(user_id) == websocket:
                    self.user_websockets.pop(user_id, None)
                    self.user_room_mapping.pop(user_id, None)
                    logger.debug(f"🧹 Mappings utilisateur {user_id} supprimés")

        except Exception as e:
            logger.warning(f"⚠️ Erreur suppression mappings: {e}")

    async def broadcast_to_room(self, room_code: str, message: dict, exclude_websocket: Optional[WebSocket] = None):
        """Diffuse un message à tous les clients d'une room - VERSION CORRIGÉE COMPLÈTE"""
        if room_code not in self.room_connections:
            logger.warning(f"⚠️ Room {room_code} non trouvée pour broadcast")
            return

        connections = self.room_connections[room_code].copy()  # Copie pour éviter les modifications concurrentes
        disconnected_connections = []
        sent_count = 0

        for websocket in connections:
            if websocket == exclude_websocket:
                continue

            try:
                # Vérifier que la connexion est toujours active
                if websocket.client_state.disconnected:
                    disconnected_connections.append(websocket)
                    continue

                await self._send_to_connection(websocket, message)
                sent_count += 1

            except Exception as e:
                logger.warning(f"⚠️ Erreur envoi à connexion dans {room_code}: {e}")
                disconnected_connections.append(websocket)

        # Nettoyer les connexions mortes
        for dead_connection in disconnected_connections:
            await self._remove_connection_mappings(dead_connection)

        self.stats["messages_sent"] += sent_count
        logger.debug(f"📡 Message diffusé à {sent_count} joueurs dans {room_code}")

    async def _send_to_connection(self, websocket: WebSocket, message: dict):
        """Envoie un message à une connexion spécifique - COMPLET"""
        try:
            message_json = json.dumps(message)
            await websocket.send_text(message_json)
        except Exception as e:
            logger.warning(f"⚠️ Impossible d'envoyer à connexion: {e}")
            raise

    async def handle_message(self, websocket: WebSocket, message_data: dict):
        """Traite un message reçu d'un client - VERSION CORRIGÉE COMPLÈTE"""
        try:
            message_type = message_data.get("type")
            data = message_data.get("data", {})

            user_id = self.connection_users.get(websocket)
            username = self.connection_usernames.get(websocket, "Joueur inconnu")
            room_code = self.connection_rooms.get(websocket)

            if not user_id or not room_code:
                logger.warning("⚠️ Message sans user_id ou room_code")
                await self._send_to_connection(websocket, {
                    "type": "error",
                    "data": {"message": "Session invalide, reconnectez-vous"}
                })
                return

            logger.debug(f"📨 Message {message_type} de {username} dans {room_code}")

            if message_type == "chat_message":
                # CORRECTION: Diffuser le message de chat à TOUS dans la room
                chat_message = {
                    "type": "chat_broadcast",
                    "data": {
                        "message_id": f"msg_{datetime.now().timestamp()}_{user_id}",
                        "user_id": user_id,
                        "username": username,
                        "message": data.get("message", "").strip()[:500],  # Limite 500 caractères
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "type": "user",
                        "room_code": room_code,
                        "is_creator": data.get("is_creator", False)
                    }
                }

                await self.broadcast_to_room(room_code, chat_message)
                logger.info(f"💬 Message chat diffusé par {username} dans {room_code}")

            elif message_type == "heartbeat":
                # Répondre au heartbeat
                await self._send_to_connection(websocket, {
                    "type": "heartbeat_ack",
                    "data": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "user_id": user_id,
                        "room_code": room_code
                    }
                })

            elif message_type == "join_game_room":
                # Déjà géré dans connect(), mais confirmer
                await self._send_to_connection(websocket, {
                    "type": "room_joined",
                    "data": {
                        "room_code": room_code,
                        "status": "joined",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                })

            elif message_type == "leave_game_room":
                await self.disconnect(websocket)

            elif message_type == "ping":
                # Répondre au ping pour mesurer la latence
                await self._send_to_connection(websocket, {
                    "type": "pong",
                    "data": {
                        "timestamp": data.get("timestamp", datetime.now().timestamp()),
                        "server_timestamp": datetime.now().timestamp()
                    }
                })

            else:
                logger.info(f"📝 Message type non géré: {message_type}")

        except Exception as e:
            logger.error(f"❌ Erreur traitement message: {e}")
            try:
                await self._send_to_connection(websocket, {
                    "type": "error",
                    "data": {"message": f"Erreur traitement: {str(e)}"}
                })
            except:
                pass

    # NOUVELLES MÉTHODES: Pour diffuser les événements de jeu

    async def broadcast_attempt(self, room_code: str, attempt_data: dict):
        """Diffuse une tentative à tous les joueurs de la room - NOUVEAU"""
        await self.broadcast_to_room(room_code, {
            "type": "attempt_submitted",
            "data": {
                **attempt_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        })
        logger.info(f"🎯 Tentative diffusée dans {room_code}: {attempt_data.get('username', 'Joueur')}")

    async def broadcast_game_state(self, room_code: str, game_state: dict):
        """Diffuse l'état du jeu mis à jour - NOUVEAU"""
        await self.broadcast_to_room(room_code, {
            "type": "game_state_update",
            "data": {
                **game_state,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        })
        logger.info(f"🔄 État de jeu diffusé dans {room_code}")

    async def broadcast_game_started(self, room_code: str, game_data: dict):
        """Diffuse le démarrage d'une partie - NOUVEAU"""
        await self.broadcast_to_room(room_code, {
            "type": "game_started",
            "data": {
                **game_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        })
        logger.info(f"🚀 Démarrage de partie diffusé dans {room_code}")

    async def broadcast_game_finished(self, room_code: str, result_data: dict):
        """Diffuse la fin d'une partie - NOUVEAU"""
        await self.broadcast_to_room(room_code, {
            "type": "game_finished",
            "data": {
                **result_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        })
        logger.info(f"🏁 Fin de partie diffusée dans {room_code}")

    async def broadcast_mastermind_regenerated(self, room_code: str, regen_data: dict):
        """Diffuse la régénération d'un mastermind - NOUVEAU"""
        await self.broadcast_to_room(room_code, {
            "type": "mastermind_regenerated",
            "data": {
                **regen_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        })
        logger.info(f"🔄 Régénération mastermind diffusée dans {room_code}")

    # MÉTHODES UTILITAIRES

    def get_room_stats(self, room_code: str) -> dict:
        """Statistiques d'une room - COMPLET"""
        connections = self.room_connections.get(room_code, set())
        users = [self.connection_users.get(ws, "unknown") for ws in connections]
        usernames = [self.connection_usernames.get(ws, "Joueur") for ws in connections]

        return {
            "room_code": room_code,
            "connected_players": len(connections),
            "users": users,
            "usernames": usernames,
            "is_active": len(connections) > 0
        }

    def get_global_stats(self) -> dict:
        """Statistiques globales - NOUVEAU"""
        return {
            **self.stats,
            "active_rooms": len(self.room_connections),
            "total_active_connections": sum(len(conns) for conns in self.room_connections.values()),
            "rooms": {room: len(conns) for room, conns in self.room_connections.items()}
        }

    async def send_system_message(self, room_code: str, message: str):
        """Envoie un message système à une room - NOUVEAU"""
        await self.broadcast_to_room(room_code, {
            "type": "chat_broadcast",
            "data": {
                "message_id": f"system_{datetime.now().timestamp()}",
                "user_id": "system",
                "username": "🤖 Système",
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "system",
                "room_code": room_code
            }
        })

# Instance globale
multiplayer_ws_manager = MultiplayerWebSocketManager()


# FONCTION D'INITIALISATION POUR main.py
async def initialize_multiplayer_websocket():
    """Initialise le gestionnaire WebSocket multijoueur"""
    logger.info("🌐 Initialisation du gestionnaire WebSocket multijoueur")
    # Toute initialisation spéciale si nécessaire
    return multiplayer_ws_manager


# FONCTION DE NETTOYAGE POUR main.py
async def cleanup_multiplayer_websocket():
    """Nettoie le gestionnaire WebSocket multijoueur"""
    logger.info("🧹 Nettoyage du gestionnaire WebSocket multijoueur")

    # Fermer toutes les connexions actives
    for room_code, connections in multiplayer_ws_manager.room_connections.items():
        for websocket in connections.copy():
            try:
                await websocket.close(code=1001, reason="Server shutdown")
            except:
                pass

    # Vider tous les mappings
    multiplayer_ws_manager.room_connections.clear()
    multiplayer_ws_manager.connection_rooms.clear()
    multiplayer_ws_manager.connection_users.clear()
    multiplayer_ws_manager.connection_usernames.clear()
    multiplayer_ws_manager.user_room_mapping.clear()
    multiplayer_ws_manager.user_websockets.clear()

    logger.info("✅ Nettoyage WebSocket multijoueur terminé")