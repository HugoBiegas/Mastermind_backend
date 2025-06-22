"""
Service de notification en temps réel
COMPLET: Coordination de toutes les notifications multijoueur
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

# Import conditionnel pour WebSocket
try:
    from app.websocket.multiplayer import multiplayer_ws_manager

    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

from app.schemas.multiplayer import (
    PlayerJoinedMessage, PlayerLeftMessage, GameStartedMessage,
    AttemptSubmittedMessage, ChatMessage
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Service centralisé pour les notifications temps réel"""

    def __init__(self):
        self.notification_queue: asyncio.Queue = asyncio.Queue()
        self.subscribers: Dict[str, Set[str]] = {}  # room_code -> set of user_ids
        self.user_sessions: Dict[str, Dict[str, Any]] = {}  # user_id -> session_info

        # Types de notifications supportées
        self.notification_types = {
            "player_joined", "player_left", "game_started", "game_finished",
            "attempt_submitted", "mastermind_completed", "item_used",
            "effect_applied", "effect_expired", "quantum_hint_used",
            "chat_message", "score_updated", "leaderboard_updated",
            "connection_status", "system_message"
        }

        logger.info("📢 NotificationService initialisé")

    # =====================================================
    # GESTION DES ABONNEMENTS
    # =====================================================

    async def subscribe_user_to_room(
            self,
            user_id: str,
            room_code: str,
            session_info: Optional[Dict[str, Any]] = None
    ):
        """Abonne un utilisateur aux notifications d'une room"""
        if room_code not in self.subscribers:
            self.subscribers[room_code] = set()

        self.subscribers[room_code].add(user_id)

        # Enregistrer les infos de session
        self.user_sessions[user_id] = {
            "room_code": room_code,
            "subscribed_at": datetime.now(timezone.utc),
            "session_info": session_info or {}
        }

        logger.info(f"📢 Utilisateur {user_id} abonné aux notifications de {room_code}")

    async def unsubscribe_user_from_room(self, user_id: str, room_code: str):
        """Désabonne un utilisateur des notifications d'une room"""
        if room_code in self.subscribers:
            self.subscribers[room_code].discard(user_id)

            # Nettoyer la room si vide
            if not self.subscribers[room_code]:
                del self.subscribers[room_code]

        # Supprimer les infos de session
        self.user_sessions.pop(user_id, None)

        logger.info(f"📢 Utilisateur {user_id} désabonné des notifications de {room_code}")

    async def get_room_subscribers(self, room_code: str) -> Set[str]:
        """Récupère la liste des abonnés d'une room"""
        return self.subscribers.get(room_code, set())

    # =====================================================
    # NOTIFICATIONS DE JEU
    # =====================================================

    async def notify_player_joined(
            self,
            room_code: str,
            user_id: str,
            username: str,
            is_spectator: bool = False,
            players_count: int = 1
    ):
        """Notifie qu'un joueur a rejoint la partie"""
        message = PlayerJoinedMessage(
            user_id=user_id,
            username=username,
            is_spectator=is_spectator,
            players_count=players_count
        )

        await self._broadcast_to_room(room_code, message.dict(), exclude_user=user_id)

        # Aussi envoyer un message de bienvenue au nouveau joueur
        welcome_message = {
            "type": "welcome_message",
            "message": f"Bienvenue dans la partie {room_code}, {username}!",
            "room_info": await self._get_room_summary(room_code)
        }
        await self._send_to_user(user_id, welcome_message)

    async def notify_player_left(
            self,
            room_code: str,
            user_id: str,
            username: str,
            players_count: int
    ):
        """Notifie qu'un joueur a quitté la partie"""
        message = PlayerLeftMessage(
            user_id=user_id,
            players_count=players_count
        )

        await self._broadcast_to_room(room_code, message.dict())

    async def notify_game_started(
            self,
            room_code: str,
            started_at: datetime,
            current_mastermind: int = 1
    ):
        """Notifie que la partie a commencé"""
        message = GameStartedMessage(
            started_at=started_at.isoformat(),
            current_mastermind=current_mastermind
        )

        await self._broadcast_to_room(room_code, message.dict())

    async def notify_game_finished(
            self,
            room_code: str,
            finished_at: datetime,
            final_rankings: List[Dict[str, Any]]
    ):
        """Notifie que la partie est terminée"""
        message = {
            "type": "game_finished",
            "finished_at": finished_at.isoformat(),
            "final_rankings": final_rankings,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        await self._broadcast_to_room(room_code, message)

    async def notify_attempt_submitted(
            self,
            room_code: str,
            user_id: str,
            username: str,
            mastermind_number: int,
            attempt_number: int,
            is_winning: bool,
            score: int,
            exclude_submitter: bool = True
    ):
        """Notifie qu'une tentative a été soumise"""
        message = AttemptSubmittedMessage(
            user_id=user_id,
            mastermind_number=mastermind_number,
            is_winning=is_winning,
            score=score
        )

        exclude_user = user_id if exclude_submitter else None
        await self._broadcast_to_room(room_code, message.dict(), exclude_user=exclude_user)

        # Message spécial pour une victoire
        if is_winning:
            victory_message = {
                "type": "mastermind_completed",
                "user_id": user_id,
                "username": username,
                "mastermind_number": mastermind_number,
                "attempts_used": attempt_number,
                "score": score,
                "message": f"{username} a résolu le mastermind {mastermind_number} en {attempt_number} tentatives!"
            }
            await self._broadcast_to_room(room_code, victory_message)

    async def notify_mastermind_transition(
            self,
            room_code: str,
            old_mastermind: int,
            new_mastermind: int,
            is_final: bool = False
    ):
        """Notifie du passage au mastermind suivant"""
        message = {
            "type": "mastermind_transition",
            "old_mastermind": old_mastermind,
            "new_mastermind": new_mastermind,
            "is_final_mastermind": is_final,
            "message": f"Passage au mastermind {new_mastermind}" + (" (FINAL)" if is_final else ""),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        await self._broadcast_to_room(room_code, message)

    # =====================================================
    # NOTIFICATIONS D'OBJETS ET EFFETS
    # =====================================================

    async def notify_item_used(
            self,
            room_code: str,
            source_user_id: str,
            source_username: str,
            item_type: str,
            target_user_id: Optional[str] = None,
            target_username: Optional[str] = None,
            effect_applied: bool = True
    ):
        """Notifie qu'un objet a été utilisé"""
        message = {
            "type": "item_used",
            "source_user_id": source_user_id,
            "source_username": source_username,
            "item_type": item_type,
            "target_user_id": target_user_id,
            "target_username": target_username,
            "effect_applied": effect_applied,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Message descriptif pour tous
        if target_user_id and target_username:
            message["message"] = f"{source_username} a utilisé {item_type} sur {target_username}"
        else:
            message["message"] = f"{source_username} a utilisé {item_type}"

        await self._broadcast_to_room(room_code, message)

    async def notify_effect_applied(
            self,
            room_code: str,
            target_user_id: str,
            effect_type: str,
            duration_seconds: Optional[int] = None,
            effect_value: Optional[int] = None
    ):
        """Notifie qu'un effet a été appliqué"""
        message = {
            "type": "effect_applied",
            "target_user_id": target_user_id,
            "effect_type": effect_type,
            "duration_seconds": duration_seconds,
            "effect_value": effect_value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Envoyer seulement à la cible pour ne pas spammer
        await self._send_to_user(target_user_id, message)

    async def notify_effect_expired(
            self,
            room_code: str,
            target_user_id: str,
            effect_type: str
    ):
        """Notifie qu'un effet a expiré"""
        message = {
            "type": "effect_expired",
            "target_user_id": target_user_id,
            "effect_type": effect_type,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        await self._send_to_user(target_user_id, message)

    # =====================================================
    # NOTIFICATIONS QUANTIQUES
    # =====================================================

    async def notify_quantum_hint_used(
            self,
            room_code: str,
            user_id: str,
            username: str,
            hint_type: str,
            cost: int,
            exclude_user: bool = True
    ):
        """Notifie qu'un indice quantique a été utilisé"""
        message = {
            "type": "quantum_hint_used",
            "user_id": user_id,
            "username": username,
            "hint_type": hint_type,
            "cost": cost,
            "message": f"{username} a utilisé un indice quantique: {hint_type}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        exclude_user_id = user_id if exclude_user else None
        await self._broadcast_to_room(room_code, message, exclude_user=exclude_user_id)

    # =====================================================
    # NOTIFICATIONS DE CHAT
    # =====================================================

    async def notify_chat_message(
            self,
            room_code: str,
            user_id: str,
            username: str,
            message_content: str
    ):
        """Notifie d'un message de chat"""
        message = ChatMessage(
            user_id=user_id,
            username=username,
            message=message_content,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        await self._broadcast_to_room(room_code, message.dict())

    # =====================================================
    # NOTIFICATIONS DE SCORE ET CLASSEMENT
    # =====================================================

    async def notify_score_updated(
            self,
            room_code: str,
            user_id: str,
            username: str,
            new_score: int,
            score_change: int
    ):
        """Notifie d'une mise à jour de score"""
        message = {
            "type": "score_updated",
            "user_id": user_id,
            "username": username,
            "new_score": new_score,
            "score_change": score_change,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        await self._broadcast_to_room(room_code, message)

    async def notify_leaderboard_updated(
            self,
            room_code: str,
            updated_rankings: List[Dict[str, Any]]
    ):
        """Notifie d'une mise à jour du classement"""
        message = {
            "type": "leaderboard_updated",
            "rankings": updated_rankings,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        await self._broadcast_to_room(room_code, message)

    # =====================================================
    # NOTIFICATIONS SYSTÈME
    # =====================================================

    async def notify_connection_status(
            self,
            room_code: str,
            user_id: str,
            username: str,
            status: str,  # "connected", "disconnected", "reconnected"
            connections_count: int
    ):
        """Notifie d'un changement de statut de connexion"""
        message = {
            "type": "connection_status",
            "user_id": user_id,
            "username": username,
            "status": status,
            "connections_count": connections_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        await self._broadcast_to_room(room_code, message, exclude_user=user_id)

    async def notify_system_message(
            self,
            room_code: str,
            message_content: str,
            message_type: str = "info",  # "info", "warning", "error", "success"
            target_user_id: Optional[str] = None
    ):
        """Envoie un message système"""
        message = {
            "type": "system_message",
            "message": message_content,
            "message_type": message_type,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if target_user_id:
            await self._send_to_user(target_user_id, message)
        else:
            await self._broadcast_to_room(room_code, message)

    # =====================================================
    # MÉTHODES PRIVÉES DE COMMUNICATION
    # =====================================================

    async def _broadcast_to_room(
            self,
            room_code: str,
            message: Dict[str, Any],
            exclude_user: Optional[str] = None
    ):
        """Diffuse un message à tous les abonnés d'une room"""
        if not WEBSOCKET_AVAILABLE:
            logger.warning("⚠️ WebSocket indisponible, notification ignorée")
            return

        try:
            # Ajouter des métadonnées
            enhanced_message = {
                **message,
                "room_code": room_code,
                "server_timestamp": datetime.now(timezone.utc).isoformat()
            }

            # Utiliser le gestionnaire WebSocket
            exclude_websocket = None
            if exclude_user and hasattr(multiplayer_ws_manager, '_get_user_websocket'):
                exclude_websocket = multiplayer_ws_manager._get_user_websocket(room_code, exclude_user)

            await multiplayer_ws_manager.notify_room(
                room_code, enhanced_message, exclude_websocket
            )

        except Exception as e:
            logger.error(f"❌ Erreur broadcast vers {room_code}: {e}")

    async def _send_to_user(self, user_id: str, message: Dict[str, Any]):
        """Envoie un message à un utilisateur spécifique"""
        if not WEBSOCKET_AVAILABLE:
            return

        try:
            # Trouver la room de l'utilisateur
            user_session = self.user_sessions.get(user_id)
            if not user_session:
                logger.warning(f"⚠️ Session utilisateur {user_id} introuvable")
                return

            room_code = user_session["room_code"]

            # Ajouter des métadonnées
            enhanced_message = {
                **message,
                "target_user_id": user_id,
                "server_timestamp": datetime.now(timezone.utc).isoformat()
            }

            await multiplayer_ws_manager.send_personal_message(
                room_code, user_id, enhanced_message
            )

        except Exception as e:
            logger.error(f"❌ Erreur envoi vers {user_id}: {e}")

    async def _get_room_summary(self, room_code: str) -> Dict[str, Any]:
        """Récupère un résumé de la room"""
        if not WEBSOCKET_AVAILABLE:
            return {}

        try:
            return multiplayer_ws_manager.get_room_stats(room_code)
        except Exception as e:
            logger.error(f"❌ Erreur récupération résumé room {room_code}: {e}")
            return {}

    # =====================================================
    # STATISTIQUES ET MONITORING
    # =====================================================

    def get_service_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques du service"""
        total_subscribers = sum(len(subs) for subs in self.subscribers.values())

        return {
            "total_rooms": len(self.subscribers),
            "total_subscribers": total_subscribers,
            "active_sessions": len(self.user_sessions),
            "notification_types": list(self.notification_types),
            "websocket_available": WEBSOCKET_AVAILABLE,
            "rooms_with_subscribers": {
                room: len(subs) for room, subs in self.subscribers.items()
            }
        }

    async def cleanup_inactive_sessions(self, timeout_minutes: int = 30):
        """Nettoie les sessions inactives"""
        now = datetime.now(timezone.utc)
        timeout_delta = timezone.timedelta(minutes=timeout_minutes)

        inactive_users = []

        for user_id, session_info in self.user_sessions.items():
            subscribed_at = session_info.get("subscribed_at", now)
            if now - subscribed_at > timeout_delta:
                inactive_users.append(user_id)

        for user_id in inactive_users:
            session_info = self.user_sessions[user_id]
            room_code = session_info["room_code"]
            await self.unsubscribe_user_from_room(user_id, room_code)

        if inactive_users:
            logger.info(f"🧹 {len(inactive_users)} sessions inactives nettoyées")

    async def broadcast_server_maintenance(
            self,
            message: str,
            countdown_seconds: int = 300
    ):
        """Diffuse un message de maintenance à toutes les rooms"""
        maintenance_message = {
            "type": "server_maintenance",
            "message": message,
            "countdown_seconds": countdown_seconds,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        for room_code in self.subscribers.keys():
            await self._broadcast_to_room(room_code, maintenance_message)


# =====================================================
# INSTANCE GLOBALE ET TÂCHES
# =====================================================

# Instance globale du service
notification_service = NotificationService()


async def start_notification_cleanup_task():
    """Démarre la tâche de nettoyage des notifications"""
    while True:
        try:
            await asyncio.sleep(300)  # Nettoyer toutes les 5 minutes
            await notification_service.cleanup_inactive_sessions()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Erreur lors du nettoyage des notifications: {e}")


# Log de l'état du service
logger.info(f"📢 NotificationService initialisé - WebSocket: {'✅' if WEBSOCKET_AVAILABLE else '❌'}")