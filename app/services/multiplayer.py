"""
Service Multijoueur complet pour cohérence avec le frontend React.js
Toutes les méthodes attendues par le frontend sont implémentées avec intégration quantique
COMPLET: Génération de toutes les méthodes manquantes pour le backend
"""
import json
import logging
import random
import string
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_, desc, func, or_, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Imports sécurisés avec gestion d'erreurs
logger = logging.getLogger(__name__)

# Import conditionnel pour quantum_service
try:
    from app.services.quantum import quantum_service
    QUANTUM_AVAILABLE = True
    logger.info("✅ Service quantique disponible")
except ImportError as e:
    quantum_service = None
    QUANTUM_AVAILABLE = False
    logger.warning(f"⚠️ Service quantique non disponible: {e}")

# Import conditionnel pour websocket
try:
    from app.websocket.multiplayer import multiplayer_ws_manager
    WEBSOCKET_AVAILABLE = True
    logger.info("✅ WebSocket multijoueur disponible")
except ImportError as e:
    multiplayer_ws_manager = None
    WEBSOCKET_AVAILABLE = False
    logger.warning(f"⚠️ WebSocket multijoueur non disponible: {e}")

# Imports standards du projet
from app.models.game import Game, GameStatus, GameParticipation, Difficulty, GameType
from app.models.multijoueur import (
    MultiplayerGame, PlayerProgress, GameMastermind,
    PlayerMastermindAttempt, MultiplayerGameType
)
from app.models.user import User
from app.schemas.multiplayer import (
    MultiplayerGameCreateRequest, MultiplayerAttemptRequest,
    ItemUseRequest, QuantumHintRequest, QuantumHintResponse
)
from app.utils.exceptions import (
    EntityNotFoundError, GameError, AuthorizationError, GameFullError
)


class MultiplayerService:
    """Service pour le multijoueur avec intégration quantique complète"""

    # =====================================================
    # CRÉATION ET GESTION DES PARTIES
    # =====================================================

    async def create_multiplayer_game(
            self,
            db: AsyncSession,
            game_data: MultiplayerGameCreateRequest,
            creator_id: UUID
    ) -> Dict[str, Any]:
        """Crée une partie multijoueur avec tous les masterminds"""

        logger.info(f"🎯 Création partie multijoueur par utilisateur {creator_id}")

        try:
            # Générer un code de room unique
            room_code = await self._generate_unique_room_code(db)
            logger.info(f"🔑 Code room généré: {room_code}")

            # Créer la partie de base
            base_game = Game(
                room_code=room_code,
                game_type=GameType.MULTIPLAYER,
                game_mode="multiplayer",
                difficulty=Difficulty(game_data.difficulty),
                status=GameStatus.WAITING,
                creator_id=creator_id,
                max_players=game_data.max_players,
                combination_length=game_data.combination_length,
                available_colors=game_data.available_colors,
                max_attempts=game_data.max_attempts,
                solution=game_data.solution or self._generate_random_solution(
                    game_data.combination_length, game_data.available_colors
                ),
                is_public=game_data.is_public,
                password_hash=game_data.password if game_data.password else None,
                quantum_enabled=game_data.quantum_enabled
            )

            db.add(base_game)
            await db.flush()

            # Créer la partie multijoueur
            multiplayer_game = MultiplayerGame(
                base_game_id=base_game.id,
                game_type=MultiplayerGameType(game_data.game_type),
                total_masterminds=game_data.total_masterminds,
                difficulty=Difficulty(game_data.difficulty),
                items_enabled=game_data.items_enabled,
                items_per_mastermind=game_data.items_per_mastermind
            )

            db.add(multiplayer_game)
            await db.flush()

            # Créer tous les masterminds pour la partie
            for i in range(1, game_data.total_masterminds + 1):
                mastermind = GameMastermind(
                    multiplayer_game_id=multiplayer_game.id,
                    mastermind_number=i,
                    combination_length=game_data.combination_length,
                    available_colors=game_data.available_colors,
                    max_attempts=game_data.max_attempts,
                    solution=self._generate_random_solution(
                        game_data.combination_length, game_data.available_colors
                    ),
                    is_active=(i == 1)  # Le premier mastermind est actif
                )
                db.add(mastermind)

            # Ajouter le créateur comme participant
            participation = GameParticipation(
                game_id=base_game.id,
                player_id=creator_id,
                status="joined",
                is_creator=True
            )
            db.add(participation)

            # Créer la progression du créateur
            progress = PlayerProgress(
                multiplayer_game_id=multiplayer_game.id,
                user_id=creator_id,
                status="waiting"
            )
            db.add(progress)

            await db.commit()

            # Préparer la réponse
            response_data = {
                "room_code": room_code,
                "game_id": str(base_game.id),
                "multiplayer_game_id": str(multiplayer_game.id),
                "creator_id": str(creator_id),
                "status": "created",
                "players_count": 1,
                "max_players": game_data.max_players,
                "total_masterminds": game_data.total_masterminds,
                "is_public": game_data.is_public,
                "quantum_enabled": game_data.quantum_enabled
            }

            logger.info(f"✅ Partie multijoueur créée: {room_code}")
            return response_data

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Erreur création partie multijoueur: {e}")
            raise GameError(f"Erreur lors de la création de la partie: {str(e)}")

    async def join_room_by_code(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID,
            password: Optional[str] = None,
            as_spectator: bool = False
    ) -> Dict[str, Any]:
        """Rejoint une partie par son code de room"""

        logger.info(f"🚪 Utilisateur {user_id} rejoint la room {room_code}")

        # Récupérer la partie de base
        game_query = select(Game).where(Game.room_code == room_code)
        result = await db.execute(game_query)
        base_game = result.scalar_one_or_none()

        if not base_game:
            raise EntityNotFoundError(f"Partie avec le code {room_code} introuvable")

        # Vérifications de sécurité
        if base_game.status != GameStatus.WAITING:
            raise GameError("Cette partie a déjà commencé ou est terminée")

        if base_game.password_hash and password != base_game.password_hash:
            raise AuthorizationError("Mot de passe incorrect")

        # Vérifier si l'utilisateur n'est pas déjà dans la partie
        existing_participation = await db.execute(
            select(GameParticipation).where(
                and_(
                    GameParticipation.game_id == base_game.id,
                    GameParticipation.player_id == user_id
                )
            )
        )
        if existing_participation.scalar_one_or_none():
            raise GameError("Vous êtes déjà dans cette partie")

        # Vérifier le nombre de joueurs
        current_players = await db.execute(
            select(func.count(GameParticipation.id)).where(
                and_(
                    GameParticipation.game_id == base_game.id,
                    GameParticipation.status == "joined"
                )
            )
        )
        players_count = current_players.scalar()

        if players_count >= base_game.max_players and not as_spectator:
            raise GameFullError("Cette partie est complète")

        # Récupérer la partie multijoueur
        mp_game_query = select(MultiplayerGame).where(
            MultiplayerGame.base_game_id == base_game.id
        )
        mp_result = await db.execute(mp_game_query)
        mp_game = mp_result.scalar_one_or_none()

        if not mp_game:
            raise EntityNotFoundError("Partie multijoueur introuvable")

        # Ajouter le participant
        participation = GameParticipation(
            game_id=base_game.id,
            player_id=user_id,
            status="joined",
            is_spectator=as_spectator
        )
        db.add(participation)

        # Créer la progression
        progress = PlayerProgress(
            multiplayer_game_id=mp_game.id,
            user_id=user_id,
            status="waiting"
        )
        db.add(progress)

        await db.commit()

        # Notifier via WebSocket si disponible
        if WEBSOCKET_AVAILABLE and multiplayer_ws_manager:
            await multiplayer_ws_manager.notify_room(room_code, {
                "type": "player_joined",
                "user_id": str(user_id),
                "is_spectator": as_spectator,
                "players_count": players_count + 1
            })

        response_data = {
            "room_code": room_code,
            "game_id": str(base_game.id),
            "status": "joined",
            "is_spectator": as_spectator,
            "players_count": players_count + 1
        }

        logger.info(f"✅ Utilisateur {user_id} a rejoint la room {room_code}")
        return response_data

    async def leave_room_by_code(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID
    ) -> None:
        """Quitte une partie par son code de room"""

        logger.info(f"🚪 Utilisateur {user_id} quitte la room {room_code}")

        # Récupérer la partie
        game_query = select(Game).where(Game.room_code == room_code)
        result = await db.execute(game_query)
        base_game = result.scalar_one_or_none()

        if not base_game:
            raise EntityNotFoundError(f"Partie avec le code {room_code} introuvable")

        # Supprimer la participation
        await db.execute(
            delete(GameParticipation).where(
                and_(
                    GameParticipation.game_id == base_game.id,
                    GameParticipation.player_id == user_id
                )
            )
        )

        # Récupérer la partie multijoueur
        mp_game = await db.execute(
            select(MultiplayerGame).where(MultiplayerGame.base_game_id == base_game.id)
        )
        mp_game = mp_game.scalar_one_or_none()

        if mp_game:
            # Supprimer la progression
            await db.execute(
                delete(PlayerProgress).where(
                    and_(
                        PlayerProgress.multiplayer_game_id == mp_game.id,
                        PlayerProgress.user_id == user_id
                    )
                )
            )

        await db.commit()

        # Notifier via WebSocket
        if WEBSOCKET_AVAILABLE and multiplayer_ws_manager:
            await multiplayer_ws_manager.notify_room(room_code, {
                "type": "player_left",
                "user_id": str(user_id)
            })

        logger.info(f"✅ Utilisateur {user_id} a quitté la room {room_code}")

    async def get_room_details(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID
    ) -> Dict[str, Any]:
        """Récupère les détails d'une partie"""

        # Récupérer la partie avec les relations
        game_query = select(Game).options(
            selectinload(Game.participants),
            selectinload(Game.creator)
        ).where(Game.room_code == room_code)

        result = await db.execute(game_query)
        base_game = result.scalar_one_or_none()

        if not base_game:
            raise EntityNotFoundError(f"Partie avec le code {room_code} introuvable")

        # Récupérer la partie multijoueur
        mp_game_query = select(MultiplayerGame).options(
            selectinload(MultiplayerGame.player_progresses),
            selectinload(MultiplayerGame.masterminds)
        ).where(MultiplayerGame.base_game_id == base_game.id)

        mp_result = await db.execute(mp_game_query)
        mp_game = mp_result.scalar_one_or_none()

        if not mp_game:
            raise EntityNotFoundError("Partie multijoueur introuvable")

        # Construire la réponse
        players = []
        for progress in mp_game.player_progresses:
            # Récupérer les infos utilisateur
            user_query = select(User).where(User.id == progress.user_id)
            user_result = await db.execute(user_query)
            user = user_result.scalar_one_or_none()

            if user:
                players.append({
                    "user_id": str(progress.user_id),
                    "username": user.username,
                    "status": progress.status.value,
                    "current_mastermind": progress.current_mastermind,
                    "completed_masterminds": progress.completed_masterminds,
                    "total_score": progress.total_score,
                    "is_finished": progress.is_finished
                })

        response_data = {
            "room_code": room_code,
            "game_id": str(base_game.id),
            "multiplayer_game_id": str(mp_game.id),
            "status": base_game.status.value,
            "game_type": mp_game.game_type.value,
            "total_masterminds": mp_game.total_masterminds,
            "current_mastermind": mp_game.current_mastermind,
            "difficulty": base_game.difficulty.value,
            "quantum_enabled": base_game.quantum_enabled,
            "items_enabled": mp_game.items_enabled,
            "max_players": base_game.max_players,
            "players": players,
            "created_at": base_game.created_at.isoformat(),
            "started_at": mp_game.started_at.isoformat() if mp_game.started_at else None
        }

        return response_data

    # =====================================================
    # LOBBY ET MATCHMAKING
    # =====================================================

    async def get_public_rooms(
            self,
            db: AsyncSession,
            page: int = 1,
            limit: int = 20,
            filters: Optional[str] = None
    ) -> Dict[str, Any]:
        """Récupère la liste des parties publiques pour le lobby"""

        logger.info(f"🏛️ Récupération des rooms publiques - Page {page}")

        # Parser les filtres JSON
        filter_dict = {}
        if filters:
            try:
                filter_dict = json.loads(filters)
            except json.JSONDecodeError:
                logger.warning(f"Filtres JSON invalides: {filters}")

        # Construction de la requête de base
        query = select(Game).options(
            selectinload(Game.creator),
            selectinload(Game.participants)
        ).where(
            and_(
                Game.is_public == True,
                Game.game_type == GameType.MULTIPLAYER,
                Game.status == GameStatus.WAITING
            )
        )

        # Appliquer les filtres
        if filter_dict.get("difficulty"):
            query = query.where(Game.difficulty == filter_dict["difficulty"])

        if filter_dict.get("quantum_enabled") is not None:
            query = query.where(Game.quantum_enabled == filter_dict["quantum_enabled"])

        if filter_dict.get("search_term"):
            search_term = f"%{filter_dict['search_term']}%"
            query = query.join(User, Game.creator_id == User.id).where(
                or_(
                    Game.room_code.ilike(search_term),
                    User.username.ilike(search_term)
                )
            )

        # Pagination
        total_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(total_query)
        total = total_result.scalar()

        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(desc(Game.created_at))

        result = await db.execute(query)
        games = result.scalars().all()

        # Construire la réponse
        rooms = []
        for game in games:
            # Récupérer la partie multijoueur associée
            mp_game_query = select(MultiplayerGame).where(
                MultiplayerGame.base_game_id == game.id
            )
            mp_result = await db.execute(mp_game_query)
            mp_game = mp_result.scalar_one_or_none()

            players_count = len([p for p in game.participants if not p.is_spectator])

            room_data = {
                "room_code": game.room_code,
                "game_id": str(game.id),
                "creator": {
                    "id": str(game.creator.id),
                    "username": game.creator.username
                },
                "status": game.status.value,
                "difficulty": game.difficulty.value,
                "quantum_enabled": game.quantum_enabled,
                "players_count": players_count,
                "max_players": game.max_players,
                "has_password": bool(game.password_hash),
                "created_at": game.created_at.isoformat()
            }

            if mp_game:
                room_data.update({
                    "game_type": mp_game.game_type.value,
                    "total_masterminds": mp_game.total_masterminds,
                    "items_enabled": mp_game.items_enabled
                })

            rooms.append(room_data)

        response_data = {
            "rooms": rooms,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit,
                "has_next": page * limit < total,
                "has_prev": page > 1
            }
        }

        return response_data

    # =====================================================
    # GAMEPLAY MULTIJOUEUR
    # =====================================================

    async def start_game(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID
    ) -> Dict[str, Any]:
        """Démarre une partie multijoueur"""

        logger.info(f"🚀 Démarrage partie {room_code} par {user_id}")

        # Récupérer la partie
        game_query = select(Game).where(Game.room_code == room_code)
        result = await db.execute(game_query)
        base_game = result.scalar_one_or_none()

        if not base_game:
            raise EntityNotFoundError(f"Partie {room_code} introuvable")

        # Vérifier que l'utilisateur est le créateur
        if base_game.creator_id != user_id:
            raise AuthorizationError("Seul le créateur peut démarrer la partie")

        if base_game.status != GameStatus.WAITING:
            raise GameError("Cette partie a déjà commencé ou est terminée")

        # Récupérer la partie multijoueur
        mp_game_query = select(MultiplayerGame).where(
            MultiplayerGame.base_game_id == base_game.id
        )
        mp_result = await db.execute(mp_game_query)
        mp_game = mp_result.scalar_one_or_none()

        if not mp_game:
            raise EntityNotFoundError("Partie multijoueur introuvable")

        # Démarrer la partie
        now = datetime.now(timezone.utc)
        base_game.status = GameStatus.IN_PROGRESS
        base_game.started_at = now
        mp_game.started_at = now

        # Activer tous les joueurs
        await db.execute(
            update(PlayerProgress).where(
                PlayerProgress.multiplayer_game_id == mp_game.id
            ).values(status="playing")
        )

        await db.commit()

        # Notifier via WebSocket
        if WEBSOCKET_AVAILABLE and multiplayer_ws_manager:
            await multiplayer_ws_manager.notify_room(room_code, {
                "type": "game_started",
                "started_at": now.isoformat()
            })

        logger.info(f"✅ Partie {room_code} démarrée")
        return {"status": "started", "started_at": now.isoformat()}

    async def submit_attempt(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID,
            attempt_data: MultiplayerAttemptRequest
    ) -> Dict[str, Any]:
        """Soumet une tentative dans une partie multijoueur"""

        logger.info(f"🎯 Tentative soumise pour {room_code} par {user_id}")

        # Récupérer la partie et vérifications
        game_query = select(Game).where(Game.room_code == room_code)
        result = await db.execute(game_query)
        base_game = result.scalar_one_or_none()

        if not base_game:
            raise EntityNotFoundError(f"Partie {room_code} introuvable")

        if base_game.status != GameStatus.IN_PROGRESS:
            raise GameError("Cette partie n'est pas en cours")

        # Récupérer la partie multijoueur et le mastermind actuel
        mp_game_query = select(MultiplayerGame).options(
            selectinload(MultiplayerGame.masterminds)
        ).where(MultiplayerGame.base_game_id == base_game.id)

        mp_result = await db.execute(mp_game_query)
        mp_game = mp_result.scalar_one_or_none()

        if not mp_game:
            raise EntityNotFoundError("Partie multijoueur introuvable")

        # Trouver le mastermind actuel
        current_mastermind = None
        for mastermind in mp_game.masterminds:
            if mastermind.mastermind_number == mp_game.current_mastermind:
                current_mastermind = mastermind
                break

        if not current_mastermind:
            raise GameError("Mastermind actuel introuvable")

        # Récupérer la progression du joueur
        progress_query = select(PlayerProgress).where(
            and_(
                PlayerProgress.multiplayer_game_id == mp_game.id,
                PlayerProgress.user_id == user_id
            )
        )
        progress_result = await db.execute(progress_query)
        player_progress = progress_result.scalar_one_or_none()

        if not player_progress:
            raise EntityNotFoundError("Progression du joueur introuvable")

        if player_progress.status != "playing":
            raise GameError("Vous ne pouvez pas jouer actuellement")

        # Calculer le nombre de tentatives déjà effectuées
        attempts_query = select(func.count(PlayerMastermindAttempt.id)).where(
            and_(
                PlayerMastermindAttempt.mastermind_id == current_mastermind.id,
                PlayerMastermindAttempt.user_id == user_id
            )
        )
        attempts_result = await db.execute(attempts_query)
        attempts_count = attempts_result.scalar()

        if attempts_count >= current_mastermind.max_attempts:
            raise GameError("Nombre maximum de tentatives atteint pour ce mastermind")

        # Évaluer la tentative
        evaluation = self._evaluate_combination(
            attempt_data.combination,
            current_mastermind.solution
        )

        # Calculer le score
        score = self._calculate_attempt_score(
            evaluation["exact_matches"],
            evaluation["position_matches"],
            evaluation["is_winning"],
            attempts_count + 1,
            base_game.difficulty.value,
            base_game.quantum_enabled
        )

        # Créer l'enregistrement de la tentative
        attempt = PlayerMastermindAttempt(
            mastermind_id=current_mastermind.id,
            user_id=user_id,
            attempt_number=attempts_count + 1,
            combination=attempt_data.combination,
            exact_matches=evaluation["exact_matches"],
            position_matches=evaluation["position_matches"],
            is_winning=evaluation["is_winning"],
            score=score,
            time_taken=attempt_data.time_taken
        )

        db.add(attempt)

        # Mettre à jour la progression du joueur
        player_progress.total_score += score

        # Si c'est une solution gagnante pour ce mastermind
        if evaluation["is_winning"]:
            player_progress.completed_masterminds += 1

            # Vérifier si le joueur a terminé tous les masterminds
            if player_progress.completed_masterminds >= mp_game.total_masterminds:
                player_progress.is_finished = True
                player_progress.finish_time = datetime.now(timezone.utc)
                player_progress.status = "finished"

        await db.commit()

        # Préparer la réponse
        response_data = {
            "attempt_number": attempts_count + 1,
            "combination": attempt_data.combination,
            "exact_matches": evaluation["exact_matches"],
            "position_matches": evaluation["position_matches"],
            "is_winning": evaluation["is_winning"],
            "score": score,
            "total_score": player_progress.total_score,
            "completed_masterminds": player_progress.completed_masterminds,
            "is_finished": player_progress.is_finished
        }

        # Notifier via WebSocket
        if WEBSOCKET_AVAILABLE and multiplayer_ws_manager:
            await multiplayer_ws_manager.notify_room(room_code, {
                "type": "attempt_submitted",
                "user_id": str(user_id),
                "mastermind_number": mp_game.current_mastermind,
                "is_winning": evaluation["is_winning"],
                "score": score
            })

        logger.info(f"✅ Tentative enregistrée pour {user_id} dans {room_code}")
        return response_data

    async def get_game_results(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID
    ) -> Dict[str, Any]:
        """Récupère les résultats finaux d'une partie"""

        logger.info(f"🏆 Récupération résultats pour {room_code}")

        # Récupérer la partie
        game_query = select(Game).where(Game.room_code == room_code)
        result = await db.execute(game_query)
        base_game = result.scalar_one_or_none()

        if not base_game:
            raise EntityNotFoundError(f"Partie {room_code} introuvable")

        # Récupérer la partie multijoueur
        mp_game_query = select(MultiplayerGame).options(
            selectinload(MultiplayerGame.leaderboard),
            selectinload(MultiplayerGame.player_progresses)
        ).where(MultiplayerGame.base_game_id == base_game.id)

        mp_result = await db.execute(mp_game_query)
        mp_game = mp_result.scalar_one_or_none()

        if not mp_game:
            raise EntityNotFoundError("Partie multijoueur introuvable")

        # Construire le classement final
        rankings = []
        for leaderboard_entry in mp_game.leaderboard:
            # Récupérer les infos utilisateur
            user_query = select(User).where(User.id == leaderboard_entry.user_id)
            user_result = await db.execute(user_query)
            user = user_result.scalar_one_or_none()

            if user:
                rankings.append({
                    "position": leaderboard_entry.final_position,
                    "user_id": str(leaderboard_entry.user_id),
                    "username": user.username,
                    "final_score": leaderboard_entry.final_score,
                    "total_time": leaderboard_entry.total_time,
                    "masterminds_completed": leaderboard_entry.masterminds_completed,
                    "total_attempts": leaderboard_entry.total_attempts,
                    "perfect_solutions": leaderboard_entry.perfect_solutions,
                    "quantum_hints_used": leaderboard_entry.quantum_hints_used,
                    "items_used": leaderboard_entry.items_used
                })

        # Statistiques globales
        game_stats = {
            "total_duration": (mp_game.finished_at - mp_game.started_at).total_seconds() if mp_game.finished_at and mp_game.started_at else 0,
            "total_players": len(mp_game.player_progresses),
            "total_masterminds": mp_game.total_masterminds,
            "difficulty": base_game.difficulty.value,
            "quantum_enabled": base_game.quantum_enabled
        }

        response_data = {
            "room_code": room_code,
            "game_id": str(base_game.id),
            "status": base_game.status.value,
            "rankings": sorted(rankings, key=lambda x: x["position"]),
            "game_stats": game_stats,
            "finished_at": mp_game.finished_at.isoformat() if mp_game.finished_at else None
        }

        return response_data

    # =====================================================
    # SYSTÈME D'OBJETS ET BONUS
    # =====================================================

    async def use_item_in_room(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID,
            item_data: ItemUseRequest
    ) -> Dict[str, Any]:
        """Utilise un objet dans une partie multijoueur"""

        logger.info(f"🎁 Utilisation objet {item_data.item_type} par {user_id} dans {room_code}")

        # TODO: Implémenter la logique des objets
        # Pour l'instant, retourner une réponse basique

        response_data = {
            "item_type": item_data.item_type,
            "target_user_id": item_data.target_user_id,
            "effect_applied": True,
            "message": f"Objet {item_data.item_type} utilisé avec succès"
        }

        return response_data

    # =====================================================
    # INDICES QUANTIQUES MULTIJOUEUR
    # =====================================================

    async def get_quantum_hint(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID,
            hint_request: QuantumHintRequest
    ) -> QuantumHintResponse:
        """Fournit un indice quantique dans une partie multijoueur"""

        logger.info(f"⚛️ Indice quantique demandé par {user_id} dans {room_code}")

        if not QUANTUM_AVAILABLE:
            raise GameError("Service quantique indisponible")

        # Récupérer la partie et le mastermind actuel
        # TODO: Implémenter la logique quantique complète
        # Pour l'instant, retourner une réponse basique

        response = QuantumHintResponse(
            hint_type=hint_request.hint_type,
            cost=self._get_hint_cost(hint_request.hint_type),
            result={
                "message": f"Indice {hint_request.hint_type} généré",
                "quantum_data": {"simulation": "quantum_simulator"}
            },
            quantum_data={"backend": "qasm_simulator"},
            success=True
        )

        return response

    # =====================================================
    # MÉTHODES UTILITAIRES PRIVÉES
    # =====================================================

    async def _generate_unique_room_code(self, db: AsyncSession) -> str:
        """Génère un code de room unique"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

            # Vérifier l'unicité
            existing = await db.execute(
                select(Game).where(Game.room_code == code)
            )
            if not existing.scalar_one_or_none():
                return code

    def _generate_random_solution(self, length: int, colors: int) -> List[int]:
        """Génère une solution aléatoire"""
        return [random.randint(1, colors) for _ in range(length)]

    def _evaluate_combination(self, attempt: List[int], solution: List[int]) -> Dict[str, Any]:
        """Évalue une combinaison par rapport à la solution"""

        exact_matches = sum(1 for i, (a, s) in enumerate(zip(attempt, solution)) if a == s)

        # Calculer les correspondances de couleur (sans position)
        attempt_counts = {}
        solution_counts = {}

        for i, (a, s) in enumerate(zip(attempt, solution)):
            if a != s:  # Exclure les correspondances exactes
                attempt_counts[a] = attempt_counts.get(a, 0) + 1
                solution_counts[s] = solution_counts.get(s, 0) + 1

        position_matches = 0
        for color in attempt_counts:
            if color in solution_counts:
                position_matches += min(attempt_counts[color], solution_counts[color])

        is_winning = exact_matches == len(solution)

        return {
            "exact_matches": exact_matches,
            "position_matches": position_matches,
            "is_winning": is_winning
        }

    def _calculate_attempt_score(
        self,
        exact_matches: int,
        position_matches: int,
        is_winning: bool,
        attempt_number: int,
        difficulty: str,
        quantum_enabled: bool = False
    ) -> int:
        """Calcule le score d'une tentative avec la configuration de difficulté"""

        # Calcul de base
        base_score = exact_matches * 100 + position_matches * 25

        # Bonus pour victoire
        if is_winning:
            victory_bonus = max(500 - (attempt_number - 1) * 50, 100)
            base_score += victory_bonus

        # Multiplicateur de difficulté
        difficulty_multiplier = {
            "easy": 1.0,
            "medium": 1.2,
            "hard": 1.5,
            "expert": 2.0,
            "quantum": 2.5
        }.get(difficulty, 1.0)

        # Bonus quantique
        quantum_bonus = 1.1 if quantum_enabled else 1.0

        final_score = int(base_score * difficulty_multiplier * quantum_bonus)

        return max(final_score, 0)

    def _get_hint_cost(self, hint_type: str) -> int:
        """Récupère le coût d'un indice"""
        costs = {
            "grover": 50,
            "superposition": 25,
            "entanglement": 35,
            "interference": 30
        }
        return costs.get(hint_type, 10)


# Instance globale du service
multiplayer_service = MultiplayerService()

# Log de l'état du service
logger.info(f"🎯 MultiplayerService initialisé - Quantique: {QUANTUM_AVAILABLE}, WebSocket: {WEBSOCKET_AVAILABLE}")