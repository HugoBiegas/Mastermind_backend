"""
Handlers WebSocket pour Quantum Mastermind
Traitement des messages et événements WebSocket
"""
import json
import asyncio
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.game import game_service
from app.services.quantum import quantum_service
from app.websocket.manager import (
    websocket_manager, WebSocketMessage, EventType
)
from app.utils.exceptions import (
    WebSocketMessageError, GameError, EntityNotFoundError
)


class WebSocketMessageHandler:
    """Gestionnaire des messages WebSocket entrants"""

    def __init__(self):
        self.handlers = {
            EventType.AUTHENTICATE: self._handle_authenticate,
            EventType.JOIN_GAME_ROOM: self._handle_join_game_room,
            EventType.LEAVE_GAME_ROOM: self._handle_leave_game_room,
            EventType.CHAT_MESSAGE: self._handle_chat_message,
            EventType.HEARTBEAT: self._handle_heartbeat,
            "make_attempt": self._handle_make_attempt,
            "get_quantum_hint": self._handle_get_quantum_hint,
            "start_game": self._handle_start_game,
            "get_game_state": self._handle_get_game_state,
        }

    async def handle_message(
            self,
            connection_id: str,
            raw_message: str,
            db: AsyncSession
    ) -> None:
        """
        Traite un message WebSocket entrant

        Args:
            connection_id: ID de la connexion
            raw_message: Message brut reçu
            db: Session de base de données
        """
        try:
            # Parse du message JSON
            message_data = json.loads(raw_message)
            message_type = message_data.get("type")
            message_payload = message_data.get("data", {})

            if not message_type:
                raise WebSocketMessageError("Type de message manquant")

            # Recherche du handler approprié
            handler = self.handlers.get(message_type)
            if not handler:
                await self._handle_unknown_message(connection_id, message_type)
                return

            # Exécution du handler
            await handler(connection_id, message_payload, db)

        except json.JSONDecodeError:
            await self._send_error(connection_id, "Message JSON invalide")
        except Exception as e:
            await self._send_error(connection_id, f"Erreur de traitement: {str(e)}")

    # === HANDLERS DE MESSAGES ===

    async def _handle_authenticate(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère l'authentification d'une connexion"""
        token = data.get("token")
        if not token:
            await self._send_error(connection_id, "Token manquant")
            return

        success = await websocket_manager.authenticate_connection(
            connection_id, token, db
        )

        if not success:
            await self._send_error(connection_id, "Authentification échouée")

    async def _handle_join_game_room(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère l'entrée dans une room de jeu"""
        room_id = data.get("room_id")
        if not room_id:
            await self._send_error(connection_id, "ID de room manquant")
            return

        # Vérification que la partie existe
        try:
            if room_id.startswith("game_"):
                game_id = UUID(room_id.replace("game_", ""))
                game_state = await game_service.get_game_state(db, game_id)
                if not game_state:
                    await self._send_error(connection_id, "Partie non trouvée")
                    return
        except (ValueError, EntityNotFoundError):
            await self._send_error(connection_id, "Partie invalide")
            return

        success = await websocket_manager.join_game_room(connection_id, room_id)
        if not success:
            await self._send_error(connection_id, "Impossible de rejoindre la room")

    async def _handle_leave_game_room(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère la sortie d'une room de jeu"""
        room_id = data.get("room_id")
        if not room_id:
            await self._send_error(connection_id, "ID de room manquant")
            return

        await websocket_manager.leave_game_room(connection_id, room_id)

    async def _handle_chat_message(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère les messages de chat"""
        connection = websocket_manager.connections.get(connection_id)
        if not connection or not connection.is_authenticated:
            await self._send_error(connection_id, "Non authentifié")
            return

        message_text = data.get("message", "").strip()
        room_id = data.get("room_id")

        if not message_text or not room_id:
            await self._send_error(connection_id, "Message ou room_id manquant")
            return

        # Validation de la longueur du message
        if len(message_text) > 500:
            await self._send_error(connection_id, "Message trop long")
            return

        # Filtrage basique des messages
        if self._is_message_inappropriate(message_text):
            await self._send_error(connection_id, "Message inapproprié")
            return

        # Diffusion du message dans la room
        chat_message = WebSocketMessage(
            type=EventType.CHAT_BROADCAST,
            data={
                "room_id": room_id,
                "user_id": str(connection.user_id),
                "username": connection.username,
                "message": message_text,
                "timestamp": data.get("timestamp")
            }
        )

        await websocket_manager.send_to_room(room_id, chat_message, exclude_user_id=connection.user_id)

    async def _handle_heartbeat(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère les heartbeats de connexion"""
        connection = websocket_manager.connections.get(connection_id)
        if connection:
            import time
            connection.last_heartbeat = time.time()

        # Réponse heartbeat
        response = WebSocketMessage(
            type=EventType.HEARTBEAT,
            data={"status": "alive", "server_time": time.time()}
        )

        await websocket_manager._send_to_connection(connection_id, response)

    async def _handle_make_attempt(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère les tentatives de jeu"""
        connection = websocket_manager.connections.get(connection_id)
        if not connection or not connection.is_authenticated:
            await self._send_error(connection_id, "Non authentifié")
            return

        try:
            game_id = UUID(data.get("game_id"))
            guess = data.get("guess")
            use_quantum = data.get("use_quantum_measurement", False)
            measured_position = data.get("measured_position")

            if not guess or len(guess) != 4:
                await self._send_error(connection_id, "Tentative invalide")
                return

            # Création de l'objet tentative
            from app.schemas.game import AttemptCreate
            attempt_data = AttemptCreate(
                guess=guess,
                use_quantum_measurement=use_quantum,
                measured_position=measured_position
            )

            # Exécution de la tentative
            result = await game_service.make_attempt(
                db, game_id, connection.user_id, attempt_data
            )

            # Envoi du résultat au joueur
            attempt_result = WebSocketMessage(
                type=EventType.ATTEMPT_RESULT,
                data={
                    "game_id": str(game_id),
                    "player_id": str(connection.user_id),
                    **result
                }
            )

            await websocket_manager._send_to_connection(connection_id, attempt_result)

            # Notification aux autres joueurs
            attempt_notification = WebSocketMessage(
                type=EventType.ATTEMPT_MADE,
                data={
                    "game_id": str(game_id),
                    "player_id": str(connection.user_id),
                    "username": connection.username,
                    "attempt_number": result["attempt_number"],
                    "is_correct": result["is_correct"]
                }
            )

            room_id = f"game_{game_id}"
            await websocket_manager.send_to_room(
                room_id, attempt_notification, exclude_user_id=connection.user_id
            )

            # Si la partie est terminée, diffuser l'événement
            if result["is_correct"] or result["remaining_attempts"] == 0:
                await self._handle_game_end(db, game_id, connection.user_id, result["is_correct"])

        except (ValueError, EntityNotFoundError, GameError) as e:
            await self._send_error(connection_id, str(e))
        except Exception as e:
            await self._send_error(connection_id, f"Erreur lors de la tentative: {str(e)}")

    async def _handle_get_quantum_hint(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère les demandes d'indices quantiques"""
        connection = websocket_manager.connections.get(connection_id)
        if not connection or not connection.is_authenticated:
            await self._send_error(connection_id, "Non authentifié")
            return

        try:
            game_id = UUID(data.get("game_id"))
            hint_type = data.get("hint_type")
            position = data.get("position")

            if not hint_type:
                await self._send_error(connection_id, "Type d'indice manquant")
                return

            # Obtention de l'indice
            hint = await game_service.get_quantum_hint(
                db, game_id, connection.user_id, hint_type, position
            )

            # Envoi de l'indice
            hint_message = WebSocketMessage(
                type=EventType.QUANTUM_HINT_USED,
                data={
                    "game_id": str(game_id),
                    "hint": {
                        "type": hint.hint_type,
                        "position": hint.position,
                        "revealed_info": hint.revealed_info,
                        "confidence": hint.confidence,
                        "quantum_cost": hint.quantum_cost
                    }
                }
            )

            await websocket_manager._send_to_connection(connection_id, hint_message)

        except (ValueError, EntityNotFoundError, GameError) as e:
            await self._send_error(connection_id, str(e))
        except Exception as e:
            await self._send_error(connection_id, f"Erreur lors de l'indice: {str(e)}")

    async def _handle_start_game(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère le démarrage d'une partie"""
        connection = websocket_manager.connections.get(connection_id)
        if not connection or not connection.is_authenticated:
            await self._send_error(connection_id, "Non authentifié")
            return

        try:
            game_id = UUID(data.get("game_id"))

            # Démarrage de la partie
            result = await game_service.start_game(
                db, game_id, user_id=connection.user_id
            )

            # Notification de démarrage à tous les joueurs
            start_message = WebSocketMessage(
                type=EventType.GAME_STARTED,
                data={
                    "game_id": str(game_id),
                    "started_by": str(connection.user_id),
                    "started_at": result.get("started_at"),
                    "message": result.get("message")
                }
            )

            room_id = f"game_{game_id}"
            await websocket_manager.send_to_room(room_id, start_message)

        except (ValueError, EntityNotFoundError, GameError) as e:
            await self._send_error(connection_id, str(e))
        except Exception as e:
            await self._send_error(connection_id, f"Erreur lors du démarrage: {str(e)}")

    async def _handle_get_game_state(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère les demandes d'état de partie"""
        connection = websocket_manager.connections.get(connection_id)
        if not connection or not connection.is_authenticated:
            await self._send_error(connection_id, "Non authentifié")
            return

        try:
            game_id = UUID(data.get("game_id"))

            # Récupération de l'état
            game_state = await game_service.get_game_state(
                db, game_id, user_id=connection.user_id
            )

            # Envoi de l'état
            state_message = WebSocketMessage(
                type=EventType.GAME_STATE_UPDATE,
                data={
                    "game_id": str(game_id),
                    "state": game_state
                }
            )

            await websocket_manager._send_to_connection(connection_id, state_message)

        except (ValueError, EntityNotFoundError) as e:
            await self._send_error(connection_id, str(e))
        except Exception as e:
            await self._send_error(connection_id, f"Erreur lors de la récupération: {str(e)}")

    async def _handle_unknown_message(
            self,
            connection_id: str,
            message_type: str
    ) -> None:
        """Gère les messages de type inconnu"""
        await self._send_error(
            connection_id,
            f"Type de message non supporté: {message_type}"
        )

    # === MÉTHODES UTILITAIRES ===

    async def _send_error(
            self,
            connection_id: str,
            error_message: str
    ) -> None:
        """Envoie un message d'erreur à une connexion"""
        error_msg = WebSocketMessage(
            type=EventType.ERROR,
            data={
                "error": error_message,
                "connection_id": connection_id
            }
        )

        await websocket_manager._send_to_connection(connection_id, error_msg)

    def _is_message_inappropriate(self, message: str) -> bool:
        """Filtrage basique des messages inappropriés"""
        # Liste basique de mots interdits
        forbidden_words = [
            "spam", "hack", "cheat", "bot", "script"
        ]

        message_lower = message.lower()
        return any(word in message_lower for word in forbidden_words)

    async def _handle_game_end(
            self,
            db: AsyncSession,
            game_id: UUID,
            player_id: UUID,
            won: bool
    ) -> None:
        """Gère la fin d'une partie"""
        try:
            # Récupération de l'état final de la partie
            final_state = await game_service.get_game_state(db, game_id)

            # Notification de fin de partie
            end_message = WebSocketMessage(
                type=EventType.GAME_FINISHED,
                data={
                    "game_id": str(game_id),
                    "winner_id": str(player_id) if won else None,
                    "final_state": final_state
                }
            )

            room_id = f"game_{game_id}"
            await websocket_manager.send_to_room(room_id, end_message)

        except Exception as e:
            print(f"Erreur lors de la gestion de fin de partie: {e}")


class WebSocketEventEmitter:
    """Émetteur d'événements WebSocket pour les services"""

    @staticmethod
    async def emit_player_joined(game_id: UUID, player_data: Dict[str, Any]) -> None:
        """Émet un événement de joueur qui rejoint"""
        await websocket_manager.handle_game_event(
            game_id,
            EventType.PLAYER_JOINED,
            player_data
        )

    @staticmethod
    async def emit_player_left(game_id: UUID, player_data: Dict[str, Any]) -> None:
        """Émet un événement de joueur qui quitte"""
        await websocket_manager.handle_game_event(
            game_id,
            EventType.PLAYER_LEFT,
            player_data
        )

    @staticmethod
    async def emit_game_state_update(game_id: UUID, state_data: Dict[str, Any]) -> None:
        """Émet une mise à jour d'état de partie"""
        await websocket_manager.handle_game_event(
            game_id,
            EventType.GAME_STATE_UPDATE,
            state_data
        )

    @staticmethod
    async def emit_turn_change(game_id: UUID, turn_data: Dict[str, Any]) -> None:
        """Émet un changement de tour"""
        await websocket_manager.handle_game_event(
            game_id,
            EventType.TURN_CHANGE,
            turn_data
        )

    @staticmethod
    async def notify_user(user_id: UUID, notification: Dict[str, Any]) -> None:
        """Envoie une notification à un utilisateur"""
        message = WebSocketMessage(
            type=EventType.NOTIFICATION,
            data=notification
        )

        await websocket_manager.send_to_user(user_id, message)


# Instances globales
message_handler = WebSocketMessageHandler()
event_emitter = WebSocketEventEmitter()