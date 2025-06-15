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
from app.services.auth import auth_service
from app.services.game import game_service
from app.services.quantum import quantum_service
from app.websocket.manager import (
    websocket_manager, WebSocketMessage, EventType
)
from app.utils.exceptions import (
    WebSocketMessageError, GameError, EntityNotFoundError,
    AuthenticationError
)


class WebSocketMessageHandler:
    """Gestionnaire des messages WebSocket entrants"""

    def __init__(self):
        self.handlers = {
            # Authentification
            EventType.AUTHENTICATE: self._handle_authenticate,

            # Gestion des rooms
            EventType.JOIN_GAME_ROOM: self._handle_join_game_room,
            EventType.LEAVE_GAME_ROOM: self._handle_leave_game_room,

            # Chat
            EventType.CHAT_MESSAGE: self._handle_chat_message,

            # Système
            EventType.HEARTBEAT: self._handle_heartbeat,

            # Gameplay (handlers personnalisés)
            "make_attempt": self._handle_make_attempt,
            "get_quantum_hint": self._handle_get_quantum_hint,
            "start_game": self._handle_start_game,
            "get_game_state": self._handle_get_game_state,
            "pause_game": self._handle_pause_game,
            "resume_game": self._handle_resume_game,
            "surrender_game": self._handle_surrender_game,

            # Invitations et social
            "invite_player": self._handle_invite_player,
            "accept_invitation": self._handle_accept_invitation,
            "decline_invitation": self._handle_decline_invitation,

            # Spectateur
            "watch_game": self._handle_watch_game,
            "unwatch_game": self._handle_unwatch_game,
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

            # Mise à jour du heartbeat
            await websocket_manager.update_heartbeat(connection_id)

            # Recherche du handler approprié
            handler = self.handlers.get(message_type)
            if not handler:
                await self._handle_unknown_message(connection_id, message_type)
                return

            # Exécution du handler
            await handler(connection_id, message_payload, db)

        except json.JSONDecodeError:
            await self._send_error(connection_id, "Message JSON invalide")
        except WebSocketMessageError as e:
            await self._send_error(connection_id, str(e))
        except Exception as e:
            await self._send_error(connection_id, f"Erreur de traitement: {str(e)}")

    # === HANDLERS DE SYSTÈME ===

    async def _handle_authenticate(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère l'authentification d'une connexion WebSocket"""
        token = data.get("token")
        if not token:
            await self._send_error(connection_id, "Token manquant")
            return

        success = await websocket_manager.authenticate_connection(
            connection_id, token, db
        )

        if success:
            # Récupérer les informations de connexion
            connection_info = websocket_manager.get_connection_info(connection_id)

            success_message = WebSocketMessage(
                type=EventType.AUTHENTICATION_SUCCESS,
                data={
                    "user_id": connection_info.get("user_id"),
                    "username": connection_info.get("username"),
                    "authenticated_at": connection_info.get("connected_at")
                }
            )
            await websocket_manager.send_to_connection(connection_id, success_message)
        else:
            await self._send_error(connection_id, "Authentification échouée")

    async def _handle_heartbeat(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère les pings de heartbeat"""
        response = WebSocketMessage(
            type=EventType.HEARTBEAT,
            data={
                "pong": True,
                "timestamp": data.get("timestamp"),
                "server_timestamp": time.time()
            }
        )
        await websocket_manager.send_to_connection(connection_id, response)

    # === HANDLERS DE GAME ROOM ===

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

        # Vérifier que la connexion est authentifiée
        if not await self._require_authentication(connection_id):
            return

        # Rejoindre la room
        success = await websocket_manager.join_game_room(connection_id, room_id)

        if success:
            # Envoyer les informations de la room
            room_info = await websocket_manager.get_room_info(room_id)

            response = WebSocketMessage(
                type=EventType.JOIN_GAME_ROOM,
                data={
                    "room_id": room_id,
                    "success": True,
                    "room_info": room_info
                }
            )
            await websocket_manager.send_to_connection(connection_id, response)

            # Charger l'état du jeu si il existe
            try:
                game_state = await game_service.get_game_state(db, UUID(room_id))
                if game_state:
                    state_message = WebSocketMessage(
                        type=EventType.GAME_STATE_UPDATE,
                        data=game_state
                    )
                    await websocket_manager.send_to_connection(connection_id, state_message)
            except:
                pass  # Pas grave si le jeu n'existe pas encore
        else:
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

        success = await websocket_manager.leave_game_room(connection_id, room_id)

        response = WebSocketMessage(
            type=EventType.LEAVE_GAME_ROOM,
            data={
                "room_id": room_id,
                "success": success
            }
        )
        await websocket_manager.send_to_connection(connection_id, response)

    # === HANDLERS DE GAMEPLAY ===

    async def _handle_make_attempt(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère une tentative de jeu"""
        if not await self._require_authentication(connection_id):
            return

        game_id = data.get("game_id")
        combination = data.get("combination")

        if not game_id or not combination:
            await self._send_error(connection_id, "Données de tentative manquantes")
            return

        try:
            # Récupérer l'utilisateur
            user_id = await self._get_user_id(connection_id)
            if not user_id:
                await self._send_error(connection_id, "Utilisateur non trouvé")
                return

            # Traiter la tentative
            result = await game_service.make_attempt_websocket(
                db, UUID(game_id), user_id, combination
            )

            # Envoyer le résultat au joueur
            response = WebSocketMessage(
                type=EventType.ATTEMPT_RESULT,
                data=result
            )
            await websocket_manager.send_to_connection(connection_id, response)

            # Broadcaster la tentative aux autres joueurs de la room
            attempt_broadcast = WebSocketMessage(
                type=EventType.ATTEMPT_MADE,
                data={
                    "game_id": game_id,
                    "player_id": str(user_id),
                    "attempt_number": result.get("attempt_number"),
                    "black_pegs": result.get("black_pegs"),
                    "white_pegs": result.get("white_pegs"),
                    "is_solution": result.get("is_solution", False)
                }
            )
            await websocket_manager.broadcast_to_room(
                game_id, attempt_broadcast, exclude_connection=connection_id
            )

            # Si la partie est terminée, envoyer l'état final
            if result.get("game_finished"):
                final_state = await game_service.get_game_state(db, UUID(game_id))
                final_message = WebSocketMessage(
                    type=EventType.GAME_FINISHED,
                    data=final_state
                )
                await websocket_manager.broadcast_to_room(game_id, final_message)

        except (GameError, EntityNotFoundError) as e:
            await self._send_error(connection_id, str(e))
        except Exception as e:
            await self._send_error(connection_id, f"Erreur lors de la tentative: {str(e)}")

    async def _handle_get_quantum_hint(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère une demande de hint quantique"""
        if not await self._require_authentication(connection_id):
            return

        game_id = data.get("game_id")
        hint_type = data.get("hint_type", "grover")

        if not game_id:
            await self._send_error(connection_id, "ID de jeu manquant")
            return

        try:
            user_id = await self._get_user_id(connection_id)
            if not user_id:
                await self._send_error(connection_id, "Utilisateur non trouvé")
                return

            # Générer le hint quantique
            hint = await quantum_service.generate_quantum_hint(
                db, UUID(game_id), user_id, hint_type
            )

            response = WebSocketMessage(
                type=EventType.QUANTUM_HINT_USED,
                data={
                    "game_id": game_id,
                    "hint": hint.model_dump(),
                    "cost": hint.cost_points
                }
            )
            await websocket_manager.send_to_connection(connection_id, response)

            # Broadcaster l'utilisation du hint (sans révéler le contenu)
            hint_broadcast = WebSocketMessage(
                type=EventType.QUANTUM_HINT_USED,
                data={
                    "game_id": game_id,
                    "player_id": str(user_id),
                    "hint_type": hint_type,
                    "points_spent": hint.cost_points
                }
            )
            await websocket_manager.broadcast_to_room(
                game_id, hint_broadcast, exclude_connection=connection_id
            )

        except Exception as e:
            await self._send_error(connection_id, f"Erreur lors du hint quantique: {str(e)}")

    async def _handle_start_game(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère le démarrage d'une partie"""
        if not await self._require_authentication(connection_id):
            return

        game_id = data.get("game_id")
        if not game_id:
            await self._send_error(connection_id, "ID de jeu manquant")
            return

        try:
            user_id = await self._get_user_id(connection_id)
            if not user_id:
                return

            # Démarrer le jeu
            result = await game_service.start_game(db, UUID(game_id), user_id)

            # Broadcaster le démarrage à tous les joueurs
            start_message = WebSocketMessage(
                type=EventType.GAME_STARTED,
                data={
                    "game_id": game_id,
                    "started_by": str(user_id),
                    "game_state": result
                }
            )
            await websocket_manager.broadcast_to_room(game_id, start_message)

        except Exception as e:
            await self._send_error(connection_id, f"Erreur lors du démarrage: {str(e)}")

    async def _handle_get_game_state(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère la demande d'état de jeu"""
        game_id = data.get("game_id")
        if not game_id:
            await self._send_error(connection_id, "ID de jeu manquant")
            return

        try:
            game_state = await game_service.get_game_state(db, UUID(game_id))

            response = WebSocketMessage(
                type=EventType.GAME_STATE_UPDATE,
                data=game_state
            )
            await websocket_manager.send_to_connection(connection_id, response)

        except Exception as e:
            await self._send_error(connection_id, f"Erreur lors de la récupération de l'état: {str(e)}")

    async def _handle_pause_game(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère la pause d'une partie"""
        if not await self._require_authentication(connection_id):
            return

        game_id = data.get("game_id")
        if not game_id:
            await self._send_error(connection_id, "ID de jeu manquant")
            return

        try:
            user_id = await self._get_user_id(connection_id)
            await game_service.pause_game(db, UUID(game_id), user_id)

            # Broadcaster la pause
            pause_message = WebSocketMessage(
                type="game_paused",
                data={
                    "game_id": game_id,
                    "paused_by": str(user_id)
                }
            )
            await websocket_manager.broadcast_to_room(game_id, pause_message)

        except Exception as e:
            await self._send_error(connection_id, f"Erreur lors de la pause: {str(e)}")

    # === HANDLERS DE CHAT ===

    async def _handle_chat_message(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère un message de chat"""
        if not await self._require_authentication(connection_id):
            return

        room_id = data.get("room_id")
        message = data.get("message", "").strip()

        if not room_id or not message:
            await self._send_error(connection_id, "Données de message manquantes")
            return

        if len(message) > 500:
            await self._send_error(connection_id, "Message trop long (max 500 caractères)")
            return

        try:
            connection_info = websocket_manager.get_connection_info(connection_id)

            chat_message = WebSocketMessage(
                type=EventType.CHAT_BROADCAST,
                data={
                    "room_id": room_id,
                    "user_id": connection_info.get("user_id"),
                    "username": connection_info.get("username"),
                    "message": message,
                    "timestamp": time.time()
                }
            )

            # Broadcaster le message à tous les membres de la room
            await websocket_manager.broadcast_to_room(room_id, chat_message)

            # TODO: Sauvegarder le message en base de données si nécessaire

        except Exception as e:
            await self._send_error(connection_id, f"Erreur lors de l'envoi du message: {str(e)}")

    # === HANDLERS D'INVITATION ===

    async def _handle_invite_player(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère l'invitation d'un joueur"""
        if not await self._require_authentication(connection_id):
            return

        target_username = data.get("username")
        game_id = data.get("game_id")

        if not target_username or not game_id:
            await self._send_error(connection_id, "Données d'invitation manquantes")
            return

        try:
            from app.repositories.user import UserRepository
            user_repo = UserRepository()

            # Trouver l'utilisateur cible
            target_user = await user_repo.get_by_username(db, target_username)
            if not target_user:
                await self._send_error(connection_id, "Utilisateur non trouvé")
                return

            # Vérifier si l'utilisateur cible est connecté
            if not websocket_manager.is_user_connected(target_user.id):
                await self._send_error(connection_id, "Utilisateur non connecté")
                return

            inviter_info = websocket_manager.get_connection_info(connection_id)

            # Envoyer l'invitation
            invitation = WebSocketMessage(
                type="game_invitation",
                data={
                    "game_id": game_id,
                    "inviter_id": inviter_info.get("user_id"),
                    "inviter_username": inviter_info.get("username"),
                    "message": data.get("message", "Vous invite à rejoindre une partie")
                }
            )

            await websocket_manager.send_to_user(target_user.id, invitation)

            # Confirmer l'envoi
            response = WebSocketMessage(
                type="invitation_sent",
                data={
                    "target_username": target_username,
                    "game_id": game_id
                }
            )
            await websocket_manager.send_to_connection(connection_id, response)

        except Exception as e:
            await self._send_error(connection_id, f"Erreur lors de l'invitation: {str(e)}")

    # === HANDLERS DE SPECTATEUR ===

    async def _handle_watch_game(
            self,
            connection_id: str,
            data: Dict[str, Any],
            db: AsyncSession
    ) -> None:
        """Gère le mode spectateur"""
        game_id = data.get("game_id")
        if not game_id:
            await self._send_error(connection_id, "ID de jeu manquant")
            return

        try:
            # Rejoindre comme spectateur
            success = await websocket_manager.join_game_room(connection_id, f"watch_{game_id}")

            if success:
                # Envoyer l'état actuel du jeu
                game_state = await game_service.get_spectator_view(db, UUID(game_id))

                response = WebSocketMessage(
                    type="watching_game",
                    data={
                        "game_id": game_id,
                        "game_state": game_state
                    }
                )
                await websocket_manager.send_to_connection(connection_id, response)

        except Exception as e:
            await self._send_error(connection_id, f"Erreur en mode spectateur: {str(e)}")

    # === HANDLERS D'ERREUR ===

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

    async def _send_error(
            self,
            connection_id: str,
            error_message: str
    ) -> None:
        """Envoie un message d'erreur à une connexion"""
        error_response = WebSocketMessage(
            type=EventType.ERROR,
            data={
                "error": error_message,
                "timestamp": time.time()
            }
        )
        await websocket_manager.send_to_connection(connection_id, error_response)

    # === MÉTHODES UTILITAIRES ===

    async def _require_authentication(self, connection_id: str) -> bool:
        """Vérifie qu'une connexion est authentifiée"""
        connection_info = websocket_manager.get_connection_info(connection_id)

        if not connection_info or not connection_info.get("is_authenticated"):
            await self._send_error(connection_id, "Authentification requise")
            return False

        return True

    async def _get_user_id(self, connection_id: str) -> Optional[UUID]:
        """Récupère l'ID utilisateur d'une connexion"""
        connection_info = websocket_manager.get_connection_info(connection_id)
        if not connection_info:
            return None

        user_id_str = connection_info.get("user_id")
        if user_id_str:
            try:
                return UUID(user_id_str)
            except ValueError:
                return None

        return None


# Instance globale du gestionnaire de messages
message_handler = WebSocketMessageHandler()