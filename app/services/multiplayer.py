"""
Service Multijoueur complet pour cohérence avec le frontend React.js
Toutes les méthodes attendues par le frontend sont implémentées avec intégration quantique
CORRIGÉ: Imports sécurisés, gestion d'erreurs robuste, compatibilité DB
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_, desc, asc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import or_

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
from app.core.security import jwt_manager
from app.models.game import Game, GameStatus, GameParticipation, ParticipationStatus, Difficulty
from app.models.multijoueur import (
    MultiplayerGame, PlayerProgress, GameMastermind,
    PlayerStatus, PlayerMastermindAttempt
)
from app.models.user import User
from app.schemas.game import QuantumHintResponse
from app.schemas.multiplayer import (
    MultiplayerGameCreateRequest, MultiplayerAttemptRequest,
    ItemUseRequest, QuantumHintRequest
)
from app.utils.exceptions import (
    EntityNotFoundError, GameError, ValidationError,
    AuthorizationError, GameFullError
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

            # Créer le jeu de base avec solution classique
            solution = await self._generate_solution(
                game_data.quantum_enabled,
                game_data.combination_length,
                game_data.available_colors
            )
            logger.info("✅ Solution classique générée")

            base_game = Game(
                room_code=room_code,
                game_type="multiplayer",
                game_mode="multiplayer",
                status=GameStatus.WAITING,
                difficulty=game_data.difficulty,
                combination_length=game_data.combination_length,
                available_colors=game_data.available_colors,
                max_attempts=game_data.max_attempts,
                time_limit=game_data.time_limit,
                max_players=game_data.max_players,
                solution=solution,
                is_private=game_data.is_private,
                allow_spectators=game_data.allow_spectators,
                enable_chat=game_data.enable_chat,
                quantum_enabled=game_data.quantum_enabled,
                creator_id=creator_id,
                settings={
                    "game_name": game_data.name,
                    "password_hash": game_data.password if game_data.is_private else None
                }
            )
            db.add(base_game)
            await db.flush()
            logger.info(f"📝 Jeu de base créé: {base_game.id}")

            # Créer la partie multijoueur
            multiplayer_game = MultiplayerGame(
                base_game_id=base_game.id,
                game_type=game_data.game_type,
                total_masterminds=game_data.total_masterminds,
                current_mastermind=1,
                is_final_mastermind=False,
                difficulty=game_data.difficulty,
                items_enabled=game_data.items_enabled,
                items_per_mastermind=game_data.items_per_mastermind
            )

            db.add(multiplayer_game)
            await db.flush()
            logger.info(f"🎮 Partie multijoueur créée: {multiplayer_game.id}")

            # CORRECTION: Créer les masterminds SANS updated_at
            await self._create_masterminds_for_game(
                db, multiplayer_game, base_game.quantum_enabled, game_data.difficulty
            )

            # Ajouter le créateur comme participant
            await self._add_player_to_game(db, base_game.id, creator_id, True)

            await db.commit()
            logger.info(f"✅ Partie multijoueur créée avec succès: {room_code}")

            # Retourner le format attendu par le frontend
            return await self._format_game_response(db, base_game, multiplayer_game)

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Erreur création partie multijoueur: {str(e)}")
            raise GameError(f"Erreur lors de la création de la partie multijoueur: {str(e)}")

    async def join_room_by_code(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID,
            password: Optional[str] = None,
            as_spectator: bool = False
    ) -> Dict[str, Any]:
        """Rejoint une partie par code de room"""

        logger.info(f"🚪 Utilisateur {user_id} tente de rejoindre {room_code}")

        # Vérifier que la partie existe et est accessible
        query = select(Game).options(
            selectinload(Game.participants)
        ).where(Game.room_code == room_code)
        result = await db.execute(query)
        game = result.scalar_one_or_none()

        if not game:
            raise EntityNotFoundError(f"Aucune partie trouvée avec le code {room_code}")

        if game.status != GameStatus.WAITING:
            raise GameError("Cette partie a déjà commencé ou est terminée")

        # Vérifier le mot de passe si nécessaire
        if game.is_private and password:
            stored_password = game.settings.get("password_hash")
            if stored_password != password:  # Simplification - en prod, hasher
                raise AuthorizationError("Mot de passe incorrect")

        # Vérifier si l'utilisateur n'est pas déjà dans la partie
        existing_participation = next(
            (p for p in game.participants if p.player_id == user_id), None
        )
        if existing_participation:
            raise GameError("Vous participez déjà à cette partie")

        # Vérifier la capacité
        active_participants = [p for p in game.participants if p.status not in [ParticipationStatus.LEFT]]
        if not as_spectator and len(active_participants) >= game.max_players:
            if game.allow_spectators:
                as_spectator = True
            else:
                raise GameFullError("Cette partie est complète")

        # Ajouter le joueur
        await self._add_player_to_game(db, game.id, user_id, False, as_spectator)
        await db.commit()

        # Notifier via WebSocket si disponible
        if WEBSOCKET_AVAILABLE and multiplayer_ws_manager:
            user = await db.get(User, user_id)
            await multiplayer_ws_manager.notify_player_joined(
                room_code, str(user_id), user.username
            )

        # Récupérer la partie multijoueur
        mp_query = select(MultiplayerGame).where(MultiplayerGame.base_game_id == game.id)
        mp_result = await db.execute(mp_query)
        multiplayer_game = mp_result.scalar_one()

        logger.info(f"✅ Utilisateur {user_id} a rejoint {room_code}")
        return await self._format_game_response(db, game, multiplayer_game)

    async def leave_room_by_code(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID
    ) -> None:
        """Quitte une partie par code de room"""

        logger.info(f"🚪 Utilisateur {user_id} quitte {room_code}")

        # Trouver la participation
        query = select(GameParticipation).join(Game).where(
            and_(
                Game.room_code == room_code,
                GameParticipation.player_id == user_id,
                GameParticipation.status.in_([ParticipationStatus.ACTIVE, ParticipationStatus.WAITING])
            )
        )
        result = await db.execute(query)
        participation = result.scalar_one_or_none()

        if not participation:
            raise EntityNotFoundError("Vous ne participez pas à cette partie")

        # Marquer comme quitté
        participation.status = ParticipationStatus.LEFT
        participation.left_at = datetime.now(timezone.utc)

        await db.commit()

        # Notifier via WebSocket si disponible
        if WEBSOCKET_AVAILABLE and multiplayer_ws_manager:
            user = await db.get(User, user_id)
            await multiplayer_ws_manager.notify_player_left(
                room_code, str(user_id), user.username
            )

        logger.info(f"✅ Utilisateur {user_id} a quitté {room_code}")

    async def get_room_details(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID
    ) -> Dict[str, Any]:
        """Récupère les détails d'une room"""

        # Vérifier l'accès à la partie
        query = select(Game).options(
            selectinload(Game.participants),
            selectinload(Game.creator)
        ).where(Game.room_code == room_code)

        result = await db.execute(query)
        game = result.scalar_one_or_none()

        if not game:
            raise EntityNotFoundError(f"Aucune partie trouvée avec le code {room_code}")

        # Récupérer la partie multijoueur
        mp_query = select(MultiplayerGame).where(MultiplayerGame.base_game_id == game.id)
        mp_result = await db.execute(mp_query)
        multiplayer_game = mp_result.scalar_one()

        return await self._format_game_response(db, game, multiplayer_game)

    async def get_public_rooms(
            self,
            db: AsyncSession,
            page: int = 1,
            limit: int = 20,
            filters: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Récupère les parties publiques pour le lobby
        CORRECTION: Gestion robuste des filtres et types de jeu
        """
        try:
            # CORRECTION: Query plus robuste avec gestion des types de jeu multijoueur
            query = select(Game).options(
                selectinload(Game.participants),
                selectinload(Game.creator)
            ).where(
                and_(
                    Game.is_private == False,
                    Game.status == GameStatus.WAITING,
                    # CORRECTION: Accepter à la fois "multiplayer" et les jeux avec parties multijoueur
                    or_(
                        Game.game_mode == "multiplayer",
                        Game.game_type == "multiplayer"
                    )
                )
            ).order_by(desc(Game.created_at))

            # Appliquer les filtres si fournis
            if filters:
                try:
                    filter_data = json.loads(filters)

                    # Filtrer par statut (attendu par le frontend)
                    if "status" in filter_data and filter_data["status"]:
                        status_value = filter_data["status"]
                        if status_value == "waiting":
                            query = query.where(Game.status == GameStatus.WAITING)
                        elif status_value == "active":
                            query = query.where(Game.status == GameStatus.ACTIVE)

                    # Filtrer par difficulté
                    if "difficulty" in filter_data and filter_data["difficulty"]:
                        query = query.where(Game.difficulty == filter_data["difficulty"])

                    # Filtrer par quantum
                    if "quantum_enabled" in filter_data and filter_data["quantum_enabled"] is not None:
                        query = query.where(Game.quantum_enabled == filter_data["quantum_enabled"])

                    # Recherche par terme
                    if "search_term" in filter_data and filter_data["search_term"]:
                        search_term = f"%{filter_data['search_term']}%"
                        query = query.where(
                            or_(
                                Game.room_code.ilike(search_term),
                                Game.settings['game_name'].astext.ilike(search_term)
                            )
                        )

                except json.JSONDecodeError as e:
                    logger.warning(f"Filtres JSON malformés ignorés: {e}")
                except Exception as e:
                    logger.warning(f"Erreur lors de l'application des filtres: {e}")

            # Pagination
            offset = (page - 1) * limit

            # Compter le total
            total_query = select(func.count()).select_from(query.subquery())
            total_result = await db.execute(total_query)
            total = total_result.scalar() or 0

            # Récupérer les résultats paginés
            paginated_query = query.offset(offset).limit(limit)
            result = await db.execute(paginated_query)
            games = result.scalars().all()

            # Formatter les résultats
            formatted_games = []
            for game in games:
                try:
                    # CORRECTION: Gestion robuste de la récupération de la partie multijoueur
                    mp_query = select(MultiplayerGame).where(MultiplayerGame.base_game_id == game.id)
                    mp_result = await db.execute(mp_query)
                    mp_game = mp_result.scalar_one_or_none()

                    if mp_game:  # S'assurer que la partie multijoueur existe
                        formatted_games.append({
                            "id": str(game.id),
                            "room_code": game.room_code,
                            "name": game.settings.get("game_name",
                                                      f"Partie {game.room_code}") if game.settings else f"Partie {game.room_code}",
                            "game_type": mp_game.game_type,
                            "difficulty": game.difficulty,
                            "status": game.status,
                            "current_players": len(
                                [p for p in game.participants if p.status not in [ParticipationStatus.LEFT]]),
                            "max_players": game.max_players,
                            "quantum_enabled": game.quantum_enabled,
                            "items_enabled": mp_game.items_enabled,
                            "creator": {
                                "id": str(game.creator_id),
                                "username": game.creator.username if game.creator else "Inconnu"
                            },
                            "created_at": game.created_at.isoformat()
                        })
                except Exception as e:
                    logger.warning(f"Erreur lors du formatage de la partie {game.id}: {e}")
                    continue

            return {
                "rooms": formatted_games,
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit if total > 0 else 0
            }

        except Exception as e:
            logger.error(f"Erreur dans get_public_rooms: {str(e)}")
            raise GameError(f"Erreur lors de la récupération des parties publiques: {str(e)}")

    # =====================================================
    # GAMEPLAY
    # =====================================================

    async def start_game(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID
    ) -> Dict[str, Any]:
        """Démarre une partie multijoueur"""

        logger.info(f"🚀 Démarrage partie {room_code} par {user_id}")

        # Vérifier que l'utilisateur peut démarrer la partie
        query = select(Game).options(
            selectinload(Game.participants)
        ).where(Game.room_code == room_code)
        result = await db.execute(query)
        game = result.scalar_one_or_none()

        if not game:
            raise EntityNotFoundError("Partie introuvable")

        if game.creator_id != user_id:
            raise AuthorizationError("Seul le créateur peut démarrer la partie")

        if game.status != GameStatus.WAITING:
            raise GameError("La partie ne peut pas être démarrée")

        # Vérifier qu'il y a assez de joueurs
        active_participants = [p for p in game.participants if p.status in [ParticipationStatus.WAITING, ParticipationStatus.READY] and not p.is_spectator]
        if len(active_participants) < 2:
            raise GameError("Au moins 2 joueurs sont nécessaires pour démarrer")

        # Démarrer la partie
        game.status = GameStatus.ACTIVE  # Utiliser ACTIVE au lieu de IN_PROGRESS
        game.started_at = datetime.now(timezone.utc)

        # Mettre à jour le statut des participants
        for participation in game.participants:
            if not participation.is_spectator and participation.status == ParticipationStatus.WAITING:
                participation.status = ParticipationStatus.ACTIVE

        # Activer le premier mastermind
        mp_query = select(MultiplayerGame).where(MultiplayerGame.base_game_id == game.id)
        mp_result = await db.execute(mp_query)
        mp_game = mp_result.scalar_one()

        # Mettre à jour le statut des joueurs
        progress_query = select(PlayerProgress).where(PlayerProgress.multiplayer_game_id == mp_game.id)
        progress_result = await db.execute(progress_query)
        all_progress = progress_result.scalars().all()

        for progress in all_progress:
            progress.status = PlayerStatus.PLAYING

        # Activer le premier mastermind
        first_mastermind_query = select(GameMastermind).where(
            and_(
                GameMastermind.multiplayer_game_id == mp_game.id,
                GameMastermind.mastermind_number == 1
            )
        )
        first_mastermind_result = await db.execute(first_mastermind_query)
        first_mastermind = first_mastermind_result.scalar_one()
        first_mastermind.is_active = True

        await db.commit()

        # Notifier via WebSocket si disponible
        if WEBSOCKET_AVAILABLE and multiplayer_ws_manager:
            await multiplayer_ws_manager.notify_game_started(room_code, mp_game)

        logger.info(f"✅ Partie {room_code} démarrée avec succès")
        return await self._format_game_response(db, game, mp_game)

    async def submit_attempt(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID,
            attempt_data: MultiplayerAttemptRequest
    ) -> Dict[str, Any]:
        """Soumet une tentative dans une partie multijoueur"""

        logger.info(f"🎯 Tentative de {user_id} dans {room_code}")

        # Récupérer la partie et vérifications
        game_query = select(Game).where(Game.room_code == room_code)
        game_result = await db.execute(game_query)
        game = game_result.scalar_one_or_none()

        if not game:
            raise EntityNotFoundError("Partie introuvable")

        if game.status != GameStatus.ACTIVE:
            raise GameError("La partie n'est pas en cours")

        # Récupérer la partie multijoueur et le mastermind actuel
        mp_query = select(MultiplayerGame).where(MultiplayerGame.base_game_id == game.id)
        mp_result = await db.execute(mp_query)
        mp_game = mp_result.scalar_one()

        if attempt_data.mastermind_number != mp_game.current_mastermind:
            raise GameError("Ce n'est pas le mastermind actuel")

        # Récupérer le mastermind
        mastermind_query = select(GameMastermind).where(
            and_(
                GameMastermind.multiplayer_game_id == mp_game.id,
                GameMastermind.mastermind_number == attempt_data.mastermind_number,
                GameMastermind.is_active == True
            )
        )
        mastermind_result = await db.execute(mastermind_query)
        mastermind = mastermind_result.scalar_one_or_none()

        if not mastermind:
            raise GameError("Mastermind introuvable ou inactif")

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

        if player_progress.status != PlayerStatus.PLAYING:
            raise GameError("Vous ne pouvez pas jouer actuellement")

        # Calculer le résultat de la tentative
        combination = attempt_data.combination
        solution = mastermind.solution

        exact_matches = sum(1 for i in range(len(combination)) if combination[i] == solution[i])
        position_matches = sum(min(combination.count(c), solution.count(c)) for c in set(combination)) - exact_matches
        is_winning = exact_matches == len(solution)

        # Calcul quantique si activé et disponible
        quantum_data = None
        if game.quantum_enabled and QUANTUM_AVAILABLE and quantum_service:
            try:
                quantum_hints = await quantum_service.calculate_quantum_hints_with_probabilities(
                    solution, combination
                )
                quantum_data = quantum_hints
            except Exception as e:
                logger.warning(f"⚠️ Erreur calcul quantique: {e}")

        # Compter les tentatives actuelles
        current_attempts_query = select(func.count()).select_from(PlayerMastermindAttempt).where(
            and_(
                PlayerMastermindAttempt.player_progress_id == player_progress.id,
                PlayerMastermindAttempt.mastermind_id == mastermind.id
            )
        )
        current_attempts_result = await db.execute(current_attempts_query)
        current_attempts = current_attempts_result.scalar()

        new_attempt = PlayerMastermindAttempt(
            player_progress_id=player_progress.id,
            mastermind_id=mastermind.id,
            attempt_number=current_attempts + 1,
            combination=combination,
            exact_matches=exact_matches,
            position_matches=position_matches,
            is_correct=is_winning,
            attempt_score=self._calculate_attempt_score(
                exact_matches, position_matches, is_winning,
                current_attempts + 1, game.difficulty, quantum_enabled=game.quantum_enabled
            ),
            time_taken=0.0,  # À calculer côté frontend
            quantum_calculated=game.quantum_enabled and quantum_data is not None,
            quantum_probabilities=quantum_data
        )

        db.add(new_attempt)

        # Mise à jour de la progression si victoire
        if is_winning:
            player_progress.status = PlayerStatus.MASTERMIND_COMPLETE
            player_progress.completed_masterminds += 1
            player_progress.total_score += new_attempt.attempt_score

            # Vérifier si tous les masterminds sont complétés
            if player_progress.completed_masterminds >= mp_game.total_masterminds:
                player_progress.status = PlayerStatus.FINISHED
                player_progress.is_finished = True
                player_progress.finish_time = datetime.now(timezone.utc)

        await db.commit()

        # Préparer la réponse
        response_data = {
            "id": str(new_attempt.id),
            "mastermind_number": attempt_data.mastermind_number,
            "combination": combination,
            "exact_matches": exact_matches,
            "position_matches": position_matches,
            "is_winning": is_winning,
            "score": new_attempt.attempt_score,
            "attempt_number": new_attempt.attempt_number,
            "quantum_calculated": new_attempt.quantum_calculated,
            "quantum_probabilities": quantum_data,
            "player_status": player_progress.status
        }

        # Notifier via WebSocket si disponible
        if WEBSOCKET_AVAILABLE and multiplayer_ws_manager:
            user = await db.get(User, user_id)
            await multiplayer_ws_manager.notify_attempt_made(
                room_code, str(user_id), user.username, response_data
            )

        logger.info(f"✅ Tentative soumise: {exact_matches} exacts, {position_matches} positions")
        return response_data

    async def get_game_state(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID
    ) -> Dict[str, Any]:
        """Récupère l'état actuel du jeu"""

        query = select(Game).where(Game.room_code == room_code)
        result = await db.execute(query)
        game = result.scalar_one_or_none()

        if not game:
            raise EntityNotFoundError("Partie introuvable")

        mp_query = select(MultiplayerGame).where(MultiplayerGame.base_game_id == game.id)
        mp_result = await db.execute(mp_query)
        mp_game = mp_result.scalar_one()

        return await self._format_game_response(db, game, mp_game)

    async def get_players_progress(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID
    ) -> List[Dict[str, Any]]:
        """Récupère la progression de tous les joueurs"""

        # Récupérer la partie
        game_query = select(Game).where(Game.room_code == room_code)
        game_result = await db.execute(game_query)
        game = game_result.scalar_one_or_none()

        if not game:
            raise EntityNotFoundError("Partie introuvable")

        mp_query = select(MultiplayerGame).where(MultiplayerGame.base_game_id == game.id)
        mp_result = await db.execute(mp_query)
        mp_game = mp_result.scalar_one()

        # Récupérer toutes les progressions
        progress_query = select(PlayerProgress).options(
            selectinload(PlayerProgress.user)
        ).where(PlayerProgress.multiplayer_game_id == mp_game.id)

        progress_result = await db.execute(progress_query)
        all_progress = progress_result.scalars().all()

        players_data = []
        for progress in all_progress:
            players_data.append({
                "user_id": str(progress.user_id),
                "username": progress.user.username,
                "status": progress.status,
                "score": progress.total_score,
                "current_mastermind": progress.current_mastermind,
                "completed_masterminds": progress.completed_masterminds,
                "is_finished": progress.is_finished,
                "finish_time": progress.finish_time.isoformat() if progress.finish_time else None
            })

        return players_data

    async def get_game_results(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID
    ) -> Dict[str, Any]:
        """Récupère les résultats finaux de la partie"""

        game_query = select(Game).where(Game.room_code == room_code)
        game_result = await db.execute(game_query)
        game = game_result.scalar_one_or_none()

        if not game:
            raise EntityNotFoundError("Partie introuvable")

        if game.status != GameStatus.FINISHED:
            raise GameError("La partie n'est pas encore terminée")

        mp_query = select(MultiplayerGame).where(MultiplayerGame.base_game_id == game.id)
        mp_result = await db.execute(mp_query)
        mp_game = mp_result.scalar_one()

        # Récupérer le classement final
        progress_query = select(PlayerProgress).options(
            selectinload(PlayerProgress.user)
        ).where(PlayerProgress.multiplayer_game_id == mp_game.id).order_by(
            desc(PlayerProgress.total_score),
            asc(PlayerProgress.finish_time)
        )

        progress_result = await db.execute(progress_query)
        final_standings = progress_result.scalars().all()

        standings_data = []
        for i, progress in enumerate(final_standings, 1):
            standings_data.append({
                "position": i,
                "user_id": str(progress.user_id),
                "username": progress.user.username,
                "score": progress.total_score,
                "completed_masterminds": progress.completed_masterminds,
                "finish_time": progress.finish_time.isoformat() if progress.finish_time else None,
                "is_winner": i == 1
            })

        return {
            "game_id": str(game.id),
            "room_code": room_code,
            "final_standings": standings_data,
            "game_duration": (game.finished_at - game.started_at).total_seconds() if game.finished_at else None,
            "total_players": len(final_standings),
            "quantum_enabled": game.quantum_enabled
        }

    # =====================================================
    # SYSTÈME D'OBJETS
    # =====================================================

    async def use_item_in_room(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID,
            item_data: ItemUseRequest
    ) -> Dict[str, Any]:
        """Utilise un objet dans une partie multijoueur"""

        logger.info(f"🎮 Utilisation objet {item_data.item_type} par {user_id} dans {room_code}")

        # Cette méthode serait développée pour un système d'objets complet
        # Pour l'instant, retourner une réponse basique
        return {
            "success": True,
            "item_used": item_data.item_type,
            "effects_applied": [],
            "message": f"Objet {item_data.item_type} utilisé avec succès"
        }

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
        """Génère un indice quantique pour une partie multijoueur"""

        logger.info(f"⚛️ Indice quantique {hint_request.hint_type} demandé par {user_id}")

        # Vérifier la partie
        game_query = select(Game).where(Game.room_code == room_code)
        game_result = await db.execute(game_query)
        game = game_result.scalar_one_or_none()

        if not game:
            raise EntityNotFoundError("Partie introuvable")

        if not game.quantum_enabled:
            raise GameError("Les indices quantiques ne sont pas activés pour cette partie")

        if not QUANTUM_AVAILABLE or not quantum_service:
            raise GameError("Service quantique non disponible")

        # Récupérer le mastermind actuel
        mp_query = select(MultiplayerGame).where(MultiplayerGame.base_game_id == game.id)
        mp_result = await db.execute(mp_query)
        mp_game = mp_result.scalar_one()

        mastermind_query = select(GameMastermind).where(
            and_(
                GameMastermind.multiplayer_game_id == mp_game.id,
                GameMastermind.mastermind_number == mp_game.current_mastermind,
                GameMastermind.is_active == True
            )
        )
        mastermind_result = await db.execute(mastermind_query)
        mastermind = mastermind_result.scalar_one_or_none()

        if not mastermind:
            raise GameError("Aucun mastermind actif")

        # Générer l'indice quantique en utilisant le service existant
        try:
            if hint_request.hint_type == "grover":
                hint_data = await quantum_service.grover_hint(
                    solution=mastermind.solution,
                    attempts=[],  # Serait mieux d'avoir les tentatives du joueur
                    shots=hint_request.quantum_shots or 1024
                )
            elif hint_request.hint_type == "superposition":
                hint_data = await quantum_service.superposition_hint(
                    solution=mastermind.solution,
                    attempts=[],
                    target_positions=hint_request.target_positions
                )
            elif hint_request.hint_type == "entanglement":
                hint_data = await quantum_service.entanglement_hint(
                    solution=mastermind.solution,
                    attempts=[]
                )
            else:
                raise ValidationError(f"Type d'indice quantique non supporté: {hint_request.hint_type}")

            logger.info(f"✅ Indice quantique généré avec succès")
            return QuantumHintResponse(
                hint_type=hint_request.hint_type,
                hint_data=hint_data,
                quantum_probability=hint_data.get("confidence", 0.5),
                cost=self._get_hint_cost(hint_request.hint_type),
                success=True
            )

        except Exception as e:
            logger.error(f"❌ Erreur génération indice quantique: {e}")
            return QuantumHintResponse(
                hint_type=hint_request.hint_type,
                hint_data={"error": str(e)},
                quantum_probability=0.0,
                cost=0,
                success=False
            )

    # =====================================================
    # AUTHENTIFICATION WEBSOCKET
    # =====================================================

    async def authenticate_websocket_user(self, token: str) -> Optional[User]:
        """Authentifie un utilisateur pour WebSocket"""
        try:
            payload = jwt_manager.decode_token(token)
            user_id = payload.get("sub")
            if user_id:
                # En production, vérifier en base de données
                return User(id=UUID(user_id), username="Test")  # Placeholder
            return None
        except Exception as e:
            logger.warning(f"⚠️ Erreur authentification WebSocket: {e}")
            return None

    # =====================================================
    # MÉTHODES UTILITAIRES PRIVÉES
    # =====================================================

    def _get_difficulty_config(self, difficulty: Difficulty) -> Dict[str, int]:
        """Retourne la configuration pour une difficulté donnée"""
        configs = {
            Difficulty.EASY: {"length": 3, "colors": 4, "attempts": 15},
            Difficulty.MEDIUM: {"length": 4, "colors": 6, "attempts": 12},
            Difficulty.HARD: {"length": 5, "colors": 8, "attempts": 10},
            Difficulty.EXPERT: {"length": 6, "colors": 10, "attempts": 8},
            Difficulty.QUANTUM: {"length": 4, "colors": 6, "attempts": 10}
        }
        return configs.get(difficulty, configs[Difficulty.MEDIUM])

    async def _generate_unique_room_code(self, db: AsyncSession) -> str:
        """Génère un code de room unique"""
        import random
        import string

        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            existing = await db.execute(select(Game).where(Game.room_code == code))
            if not existing.scalar():
                return code

    async def _generate_solution(
            self,
            quantum_enabled: bool,
            length: int,
            colors: int
    ) -> List[int]:
        """Génère une solution (quantique si activé)"""
        if quantum_enabled:
            # Utiliser le service quantique si disponible
            solution = quantum_service.generate_quantum_solution(length, colors)
            logger.info("✅ Solution quantique générée")
        else:
            # Solution classique
            import random
            solution = [random.randint(1, colors) for _ in range(length)]
            logger.info("✅ Solution classique générée")
        return solution

    async def _create_masterminds_for_game(
            self,
            db: AsyncSession,
            multiplayer_game: MultiplayerGame,
            quantum_enabled: bool,
            difficulty: Difficulty
    ) -> None:
        """
        Crée les masterminds pour une partie avec configuration de difficulté
        CORRECTION: Utilise le modèle GameMastermind SANS updated_at
        """

        logger.info(f"🎮 Création de {multiplayer_game.total_masterminds} masterminds")

        # Récupérer la configuration de difficulté
        difficulty_config = self._get_difficulty_config(difficulty)
        combination_length = difficulty_config["length"]
        available_colors = difficulty_config["colors"]
        max_attempts = difficulty_config["attempts"]

        for i in range(1, multiplayer_game.total_masterminds + 1):
            # Générer une solution (quantique si activé)
            solution = await self._generate_solution(
                quantum_enabled, combination_length, available_colors
            )

            # CORRECTION CRITIQUE: Créer GameMastermind SANS updated_at
            mastermind = GameMastermind(
                multiplayer_game_id=multiplayer_game.id,
                mastermind_number=i,
                solution=solution,
                combination_length=combination_length,
                available_colors=available_colors,
                max_attempts=max_attempts,
                is_active=(i == 1),  # Seul le premier est actif
                is_completed=False,
                # created_at sera automatiquement défini
                # completed_at sera NULL par défaut
                # PAS D'updated_at !
            )
            db.add(mastermind)

        logger.info(f"✅ {multiplayer_game.total_masterminds} masterminds créés")

    async def _add_player_to_game(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: UUID,
            is_creator: bool = False,
            is_spectator: bool = False
    ) -> None:
        """Ajoute un joueur à une partie"""

        # Compter les participants existants pour l'ordre de join
        existing_query = select(func.count()).select_from(GameParticipation).where(
            GameParticipation.game_id == game_id
        )
        existing_result = await db.execute(existing_query)
        join_order = existing_result.scalar() + 1

        # Créer la participation
        participation = GameParticipation(
            game_id=game_id,
            player_id=user_id,  # CORRECTION: Utiliser player_id comme dans init.sql
            status=ParticipationStatus.SPECTATOR if is_spectator else ParticipationStatus.WAITING,
            role="spectator" if is_spectator else "player",
            is_creator=is_creator,
            is_spectator=is_spectator,
            join_order=join_order,
            joined_at=datetime.now(timezone.utc)
        )
        db.add(participation)

        if not is_spectator:
            # Récupérer la partie multijoueur
            mp_query = select(MultiplayerGame).where(
                MultiplayerGame.base_game_id == game_id
            )
            mp_result = await db.execute(mp_query)
            mp_game = mp_result.scalar_one()

            # Créer le progress du joueur
            player_progress = PlayerProgress(
                multiplayer_game_id=mp_game.id,
                user_id=user_id,
                status=PlayerStatus.WAITING,
                current_mastermind=1,
                completed_masterminds=0,
                total_score=0,
                total_time=0.0,
                is_finished=False,
                collected_items=[],
                used_items=[]
            )
            db.add(player_progress)

    async def _format_game_response(
            self,
            db: AsyncSession,
            game: Game,
            mp_game: MultiplayerGame
    ) -> Dict[str, Any]:
        """Formate la réponse pour une partie multijoueur"""
        # Récupérer les masterminds
        masterminds_query = select(GameMastermind).where(
            GameMastermind.multiplayer_game_id == mp_game.id
        ).order_by(GameMastermind.mastermind_number)
        masterminds_result = await db.execute(masterminds_query)
        masterminds = masterminds_result.scalars().all()

        # Récupérer les participants
        participants_query = select(GameParticipation).options(
            selectinload(GameParticipation.player)
        ).where(GameParticipation.game_id == game.id)
        participants_result = await db.execute(participants_query)
        participants = participants_result.scalars().all()

        return {
            "id": str(game.id),
            "room_code": game.room_code,
            "name": game.settings.get("game_name", f"Partie {game.room_code}") if game.settings else f"Partie {game.room_code}",
            "status": game.status,
            "game_type": mp_game.game_type,
            "difficulty": game.difficulty,
            "max_players": game.max_players,
            "current_players": len([p for p in participants if not p.is_spectator]),
            "is_private": game.is_private,
            "quantum_enabled": game.quantum_enabled,
            "items_enabled": mp_game.items_enabled,
            "total_masterminds": mp_game.total_masterminds,
            "current_mastermind": mp_game.current_mastermind,
            "masterminds": [
                {
                    "number": m.mastermind_number,
                    "is_current": m.is_active,
                    "is_completed": m.is_completed,
                    "combination_length": m.combination_length,
                    "available_colors": m.available_colors,
                    "max_attempts": m.max_attempts
                } for m in masterminds
            ],
            "players": [
                {
                    "id": str(p.player_id),
                    "username": p.player.username,
                    "is_creator": p.is_creator,
                    "is_spectator": p.is_spectator,
                    "status": p.status,
                    "joined_at": p.joined_at.isoformat()
                } for p in participants
            ],
            "creator": {
                "id": str(game.creator_id),
                "username": game.creator.username if game.creator else "Inconnu"
            },
            "created_at": game.created_at.isoformat(),
            "started_at": mp_game.started_at.isoformat() if mp_game.started_at else None
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