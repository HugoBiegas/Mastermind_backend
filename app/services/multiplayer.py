"""
Service pour la gestion du multijoueur Quantum Mastermind
Logique métier complète pour les parties multijoueur avec objets bonus/malus
"""
import asyncio
import json
import secrets
import string
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, and_, or_, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.game import Game, GameMode, GameStatus, GameParticipation, ParticipationStatus, Difficulty
from app.models.multijoueur import (
    MultiplayerGame, PlayerProgress, GameMastermind, PlayerLeaderboard,
    MultiplayerGameType, ItemType, PlayerStatus
)
from app.schemas.multiplayer import MultiplayerGameCreate
from app.services.quantum import quantum_service
from app.utils.exceptions import (
    GameError, ValidationError, EntityNotFoundError,
    AuthorizationError, GameNotActiveError
)
from app.websocket.multiplayer import MultiplayerWebSocketManager


class Attempt:
    pass


class MultiplayerService:
    """Service de gestion du multijoueur"""

    # Configuration des objets disponibles
    AVAILABLE_ITEMS = {
        ItemType.EXTRA_HINT: {
            "name": "Indice Supplémentaire",
            "description": "Révèle la position d'une ou deux bonnes couleurs",
            "rarity": "common",
            "is_self_target": True,
            "effect_value": 2
        },
        ItemType.TIME_BONUS: {
            "name": "Temps Bonus",
            "description": "Ajoute 30 secondes à votre chronomètre",
            "rarity": "common",
            "is_self_target": True,
            "effect_value": 30,
            "duration_seconds": 0
        },
        ItemType.SKIP_MASTERMIND: {
            "name": "Passer le Mastermind",
            "description": "Passe automatiquement au mastermind suivant",
            "rarity": "legendary",
            "is_self_target": True
        },
        ItemType.DOUBLE_SCORE: {
            "name": "Score Double",
            "description": "Double le score du prochain mastermind réussi",
            "rarity": "epic",
            "is_self_target": True
        },
        ItemType.FREEZE_TIME: {
            "name": "Gel du Temps",
            "description": "Gèle le temps de tous les adversaires pendant 30 secondes",
            "rarity": "rare",
            "is_self_target": False,
            "duration_seconds": 30
        },
        ItemType.ADD_MASTERMIND: {
            "name": "Mastermind Supplémentaire",
            "description": "Ajoute un mastermind à faire à tous les adversaires",
            "rarity": "epic",
            "is_self_target": False
        },
        ItemType.REDUCE_ATTEMPTS: {
            "name": "Réduire les Tentatives",
            "description": "Réduit de 2 le nombre de tentatives maximum des adversaires",
            "rarity": "rare",
            "is_self_target": False,
            "effect_value": 2
        },
        ItemType.SCRAMBLE_COLORS: {
            "name": "Mélanger les Couleurs",
            "description": "Mélange l'affichage des couleurs pour les adversaires",
            "rarity": "rare",
            "is_self_target": False,
            "duration_seconds": 60
        }
    }

    # Configuration des difficultés
    DIFFICULTY_CONFIGS = {
        Difficulty.EASY: {
            "combination_length": 4,
            "available_colors": 6,
            "max_attempts": 12
        },
        Difficulty.MEDIUM: {
            "combination_length": 5,
            "available_colors": 7,
            "max_attempts": 10
        },
        Difficulty.HARD: {
            "combination_length": 6,
            "available_colors": 8,
            "max_attempts": 8
        },
        Difficulty.EXPERT: {
            "combination_length": 6,
            "available_colors": 8,
            "max_attempts": 6
        }
    }

    def _generate_room_code(self) -> str:
        """Génère un code de room unique"""
        return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

    def _generate_combination(self, length: int, available_colors: int) -> List[int]:
        """Génère une combinaison aléatoire"""
        return [secrets.randbelow(available_colors) for _ in range(length)]

    def _calculate_attempt_score(self, exact_matches: int, position_matches: int,
                                 attempt_number: int, max_attempts: int, time_taken: float) -> int:
        """Calcule le score d'une tentative"""
        base_score = (exact_matches * 10) + (position_matches * 5)

        # Bonus pour réussir rapidement
        attempt_bonus = max(0, (max_attempts - attempt_number + 1) * 5)

        # Bonus pour le temps (moins de temps = plus de points)
        time_bonus = max(0, int(120 - time_taken))  # 120 secondes comme référence

        return base_score + attempt_bonus + time_bonus

    async def create_multiplayer_game(
            self,
            db: AsyncSession,
            game_data: MultiplayerGameCreate,
            creator_id: UUID
    ) -> Dict[str, Any]:
        """Crée une nouvelle partie multijoueur"""

        # Vérifier si l'utilisateur a déjà une partie active
        existing_game = await db.execute(
            select(Game)
            .join(GameParticipation)
            .where(
                and_(
                    GameParticipation.user_id == creator_id,
                    GameParticipation.status == ParticipationStatus.ACTIVE,
                    Game.status.in_([GameStatus.WAITING, GameStatus.ACTIVE])
                )
            )
        )

        if existing_game.scalar_one_or_none():
            raise GameError("Vous avez déjà une partie active")

        # Créer la partie de base
        room_code = self._generate_room_code()

        base_game = Game(
            id=uuid4(),
            game_mode=GameMode.MULTIPLAYER,
            game_type=game_data.game_type if hasattr(game_data, 'game_type') else "quantum",
            difficulty=game_data.difficulty,
            status=GameStatus.WAITING,
            max_players=game_data.max_players,
            is_private=game_data.is_private,
            password_hash=game_data.password if game_data.is_private else None,
            allow_spectators=game_data.allow_spectators,
            enable_chat=game_data.enable_chat,
            quantum_enabled=True,  # Toujours quantum pour le multijoueur
            created_by=creator_id,
            room_code=room_code
        )

        db.add(base_game)
        await db.flush()

        # Créer la partie multijoueur
        multiplayer_game = MultiplayerGame(
            id=uuid4(),
            base_game_id=base_game.id,
            game_type=MultiplayerGameType.MULTI_MASTERMIND,
            total_masterminds=game_data.total_masterminds,
            difficulty=game_data.difficulty,
            current_mastermind=1,
            items_enabled=game_data.items_enabled,
            items_per_mastermind=1,
            created_at=datetime.now(timezone.utc)
        )

        db.add(multiplayer_game)
        await db.flush()

        # Créer la participation du créateur
        participation = GameParticipation(
            id=uuid4(),
            game_id=base_game.id,
            user_id=creator_id,
            status=ParticipationStatus.ACTIVE,
            joined_at=datetime.now(timezone.utc)
        )

        db.add(participation)

        # Créer le progrès du créateur
        player_progress = PlayerProgress(
            id=uuid4(),
            multiplayer_game_id=multiplayer_game.id,
            user_id=creator_id,
            current_mastermind=1,
            status=PlayerStatus.WAITING
        )

        db.add(player_progress)

        # Générer tous les masterminds de la partie
        difficulty_config = self.DIFFICULTY_CONFIGS[game_data.difficulty]

        for i in range(1, game_data.total_masterminds + 1):
            mastermind = GameMastermind(
                id=uuid4(),
                multiplayer_game_id=multiplayer_game.id,
                mastermind_number=i,
                solution=self._generate_combination(
                    difficulty_config["combination_length"],
                    difficulty_config["available_colors"]
                ),
                combination_length=difficulty_config["combination_length"],
                available_colors=difficulty_config["available_colors"],
                max_attempts=difficulty_config["max_attempts"],
                is_active=(i == 1),  # Seul le premier est actif
                is_completed=False
            )
            db.add(mastermind)

        await db.commit()
        await db.refresh(base_game)
        await db.refresh(multiplayer_game)

        # Charger les données complètes
        result = await self._get_multiplayer_game_with_relations(db, multiplayer_game.id)

        return {
            "id": str(multiplayer_game.id),
            "room_code": room_code,
            "multiplayer_game": result,
            "message": "Partie multijoueur créée avec succès"
        }

    async def get_public_games(
            self,
            db: AsyncSession,
            page: int = 1,
            limit: int = 10,
            difficulty: Optional[str] = None,
            max_players: Optional[int] = None,
            has_slots: Optional[bool] = None,
            sort_by: str = "created_at",
            sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """Récupère les parties publiques avec filtres"""

        # Construction de la requête
        query = (
            select(MultiplayerGame, Game, User.username.label('creator_username'))
            .join(Game, MultiplayerGame.base_game_id == Game.id)
            .join(User, Game.created_by == User.id)
            .where(
                and_(
                    Game.is_private == False,
                    Game.status.in_([GameStatus.WAITING, GameStatus.ACTIVE])
                )
            )
        )

        # Application des filtres
        if difficulty:
            query = query.where(Game.difficulty == difficulty)

        if max_players:
            query = query.where(Game.max_players <= max_players)

        if has_slots is not None:
            if has_slots:
                # Parties avec des places libres
                subquery = (
                    select(func.count(GameParticipation.id))
                    .where(
                        and_(
                            GameParticipation.game_id == Game.id,
                            GameParticipation.status == ParticipationStatus.ACTIVE
                        )
                    )
                    .scalar_subquery()
                )
                query = query.where(subquery < Game.max_players)
            else:
                # Parties complètes
                subquery = (
                    select(func.count(GameParticipation.id))
                    .where(
                        and_(
                            GameParticipation.game_id == Game.id,
                            GameParticipation.status == ParticipationStatus.ACTIVE
                        )
                    )
                    .scalar_subquery()
                )
                query = query.where(subquery >= Game.max_players)

        # Tri
        sort_column = {
            "created_at": Game.created_at,
            "current_players": func.count(GameParticipation.id),
            "difficulty": Game.difficulty
        }.get(sort_by, Game.created_at)

        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        # Exécution
        result = await db.execute(query)
        rows = result.all()

        # Compter le total
        count_query = (
            select(func.count(MultiplayerGame.id))
            .join(Game, MultiplayerGame.base_game_id == Game.id)
            .where(
                and_(
                    Game.is_private == False,
                    Game.status.in_([GameStatus.WAITING, GameStatus.ACTIVE])
                )
            )
        )

        if difficulty:
            count_query = count_query.where(Game.difficulty == difficulty)
        if max_players:
            count_query = count_query.where(Game.max_players <= max_players)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Formatage des résultats
        games = []
        for row in rows:
            multiplayer_game, game, creator_username = row

            # Compter les joueurs actuels
            current_players_result = await db.execute(
                select(func.count(GameParticipation.id))
                .where(
                    and_(
                        GameParticipation.game_id == game.id,
                        GameParticipation.status == ParticipationStatus.ACTIVE
                    )
                )
            )
            current_players = current_players_result.scalar() or 0

            games.append({
                "id": multiplayer_game.id,
                "room_code": game.room_code,
                "creator_username": creator_username,
                "difficulty": game.difficulty,
                "total_masterminds": multiplayer_game.total_masterminds,
                "current_players": current_players,
                "max_players": game.max_players,
                "status": game.status,
                "created_at": game.created_at,
                "items_enabled": multiplayer_game.items_enabled
            })

        return {
            "games": games,
            "total": total,
            "page": page,
            "limit": limit,
            "has_next": (page * limit) < total
        }

    async def join_multiplayer_game(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: UUID,
            password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Rejoint une partie multijoueur"""

        # Récupérer la partie
        result = await db.execute(
            select(MultiplayerGame, Game)
            .join(Game, MultiplayerGame.base_game_id == Game.id)
            .where(MultiplayerGame.id == game_id)
        )

        row = result.first()
        if not row:
            raise EntityNotFoundError("Partie non trouvée")

        multiplayer_game, base_game = row

        # Vérifications
        if base_game.status not in [GameStatus.WAITING, GameStatus.ACTIVE]:
            raise GameError("Cette partie n'est plus disponible")

        if base_game.is_private and base_game.password_hash != password:
            raise AuthorizationError("Mot de passe incorrect")

        # Vérifier si déjà participant
        existing_participation = await db.execute(
            select(GameParticipation)
            .where(
                and_(
                    GameParticipation.game_id == base_game.id,
                    GameParticipation.user_id == user_id,
                    GameParticipation.status == ParticipationStatus.ACTIVE
                )
            )
        )

        if existing_participation.scalar_one_or_none():
            raise GameError("Vous participez déjà à cette partie")

        # Vérifier les places disponibles
        current_players = await db.execute(
            select(func.count(GameParticipation.id))
            .where(
                and_(
                    GameParticipation.game_id == base_game.id,
                    GameParticipation.status == ParticipationStatus.ACTIVE
                )
            )
        )

        if current_players.scalar() >= base_game.max_players:
            raise GameError("Cette partie est complète")

        # Créer la participation
        participation = GameParticipation(
            id=uuid4(),
            game_id=base_game.id,
            user_id=user_id,
            status=ParticipationStatus.ACTIVE,
            joined_at=datetime.now(timezone.utc)
        )

        db.add(participation)

        # Créer le progrès du joueur
        player_progress = PlayerProgress(
            id=uuid4(),
            multiplayer_game_id=multiplayer_game.id,
            user_id=user_id,
            current_mastermind=1,
            status=PlayerStatus.WAITING
        )

        db.add(player_progress)
        await db.commit()

        # Récupérer les données complètes
        game_data = await self._get_multiplayer_game_with_relations(db, multiplayer_game.id)

        # Notifier via WebSocket
        await  MultiplayerWebSocketManager.notify_player_joined(
            str(game_id), user_id, game_data
        )

        return {
            "success": True,
            "game": game_data,
            "message": "Partie rejointe avec succès"
        }

    async def leave_multiplayer_game(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: UUID
    ) -> None:
        """Quitte une partie multijoueur"""

        # Récupérer la participation
        participation = await db.execute(
            select(GameParticipation)
            .join(Game, GameParticipation.game_id == Game.id)
            .join(MultiplayerGame, Game.id == MultiplayerGame.base_game_id)
            .where(
                and_(
                    MultiplayerGame.id == game_id,
                    GameParticipation.user_id == user_id,
                    GameParticipation.status == ParticipationStatus.ACTIVE
                )
            )
        )

        participation_obj = participation.scalar_one_or_none()
        if not participation_obj:
            raise EntityNotFoundError("Participation non trouvée")

        # Marquer comme quitté
        participation_obj.status = ParticipationStatus.LEFT
        participation_obj.left_at = datetime.now(timezone.utc)

        # Mettre à jour le statut du joueur
        player_progress = await db.execute(
            select(PlayerProgress)
            .where(
                and_(
                    PlayerProgress.multiplayer_game_id == game_id,
                    PlayerProgress.user_id == user_id
                )
            )
        )

        progress_obj = player_progress.scalar_one_or_none()
        if progress_obj:
            progress_obj.status = PlayerStatus.ELIMINATED

        await db.commit()

        # Notifier via WebSocket
        await MultiplayerWebSocketManager.notify_player_left(
            str(game_id), user_id
        )

    async def make_attempt(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: UUID,
            mastermind_number: int,
            combination: List[int]
    ) -> Dict[str, Any]:
        """Fait une tentative dans une partie multijoueur"""

        # Récupérer la partie et le mastermind
        multiplayer_game = await db.execute(
            select(MultiplayerGame)
            .options(selectinload(MultiplayerGame.masterminds))
            .where(MultiplayerGame.id == game_id)
        )

        game_obj = multiplayer_game.scalar_one_or_none()
        if not game_obj:
            raise EntityNotFoundError("Partie non trouvée")

        # Trouver le mastermind actuel
        current_mastermind = None
        for mastermind in game_obj.masterminds:
            if mastermind.mastermind_number == mastermind_number:
                current_mastermind = mastermind
                break

        if not current_mastermind or not current_mastermind.is_active:
            raise GameError("Ce mastermind n'est pas disponible")

        # Récupérer le progrès du joueur
        player_progress = await db.execute(
            select(PlayerProgress)
            .where(
                and_(
                    PlayerProgress.multiplayer_game_id == game_id,
                    PlayerProgress.user_id == user_id
                )
            )
        )

        progress_obj = player_progress.scalar_one_or_none()
        if not progress_obj:
            raise EntityNotFoundError("Progression du joueur non trouvée")

        if progress_obj.status not in [PlayerStatus.PLAYING, PlayerStatus.WAITING]:
            raise GameError("Vous ne pouvez pas faire de tentative maintenant")

        # Calculer les résultats
        exact_matches = sum(1 for i, color in enumerate(combination)
                            if i < len(current_mastermind.solution) and
                            color == current_mastermind.solution[i])

        solution_copy = current_mastermind.solution.copy()
        combination_copy = combination.copy()

        # Retirer les correspondances exactes
        for i in range(min(len(combination), len(solution_copy)) - 1, -1, -1):
            if combination_copy[i] == solution_copy[i]:
                combination_copy.pop(i)
                solution_copy.pop(i)

        position_matches = 0
        for color in combination_copy:
            if color in solution_copy:
                solution_copy.remove(color)
                position_matches += 1

        is_correct = exact_matches == len(current_mastermind.solution)

        # Compter les tentatives actuelles
        attempts_count = await db.execute(
            select(func.count(Attempt.id))
            .where(
                and_(
                    Attempt.game_id == game_obj.base_game_id,
                    Attempt.user_id == user_id
                )
            )
        )

        attempt_number = (attempts_count.scalar() or 0) + 1

        # Calculer le score
        time_taken = 30.0  # Temps par défaut, à améliorer avec un système de timing
        attempt_score = self._calculate_attempt_score(
            exact_matches, position_matches, attempt_number,
            current_mastermind.max_attempts, time_taken
        )

        # Créer la tentative
        attempt = Attempt(
            id=uuid4(),
            game_id=game_obj.base_game_id,
            user_id=user_id,
            attempt_number=attempt_number,
            combination=combination,
            exact_matches=exact_matches,
            position_matches=position_matches,
            is_correct=is_correct,
            attempt_score=attempt_score,
            time_taken=time_taken,
            quantum_calculated=True,
            created_at=datetime.now(timezone.utc)
        )

        db.add(attempt)

        # Mettre à jour la progression
        progress_obj.total_score += attempt_score
        progress_obj.total_time += time_taken
        progress_obj.status = PlayerStatus.PLAYING

        mastermind_completed = False
        items_obtained = []
        next_mastermind = None
        game_finished = False
        final_position = None

        if is_correct:
            # Mastermind complété
            mastermind_completed = True
            current_mastermind.is_completed = True
            current_mastermind.completed_at = datetime.now(timezone.utc)
            current_mastermind.is_active = False

            progress_obj.completed_masterminds += 1
            progress_obj.status = PlayerStatus.MASTERMIND_COMPLETE

            # Donner des objets si activés
            if game_obj.items_enabled:
                items_obtained = await self._generate_items_for_player(
                    db, game_id, user_id
                )

            # Vérifier si c'est le dernier mastermind
            if progress_obj.completed_masterminds >= game_obj.total_masterminds:
                progress_obj.status = PlayerStatus.FINISHED
                progress_obj.is_finished = True
                progress_obj.finish_time = datetime.now(timezone.utc)

                # Calculer la position finale
                final_position = await self._calculate_final_position(db, game_id, user_id)
                progress_obj.finish_position = final_position

                # Vérifier si la partie est terminée
                game_finished = await self._check_game_finished(db, game_id)

            else:
                # Activer le prochain mastermind
                next_mastermind = await self._activate_next_mastermind(
                    db, game_obj, progress_obj.completed_masterminds + 1
                )
                progress_obj.current_mastermind = progress_obj.completed_masterminds + 1

        await db.commit()

        # Notifier via WebSocket
        await MultiplayerWebSocketManager.notify_attempt_made(
            str(game_id), user_id, attempt, mastermind_completed
        )

        if mastermind_completed:
            await MultiplayerWebSocketManager.notify_mastermind_complete(
                str(game_id), user_id, mastermind_number, attempt_score, items_obtained
            )

        if game_finished:
            await MultiplayerWebSocketManager.notify_game_finished(str(game_id))

        return {
            "attempt": {
                "id": attempt.id,
                "attempt_number": attempt.attempt_number,
                "combination": attempt.combination,
                "exact_matches": attempt.exact_matches,
                "position_matches": attempt.position_matches,
                "is_correct": attempt.is_correct,
                "attempt_score": attempt.attempt_score,
                "time_taken": attempt.time_taken,
                "quantum_calculated": attempt.quantum_calculated,
                "created_at": attempt.created_at
            },
            "mastermind_completed": mastermind_completed,
            "items_obtained": items_obtained,
            "score": attempt_score,
            "next_mastermind": next_mastermind,
            "game_finished": game_finished,
            "final_position": final_position
        }

    async def use_item(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: UUID,
            item_type: ItemType,
            target_players: Optional[List[UUID]] = None
    ) -> Dict[str, Any]:
        """Utilise un objet dans une partie multijoueur"""

        # Récupérer le progrès du joueur
        player_progress = await db.execute(
            select(PlayerProgress)
            .where(
                and_(
                    PlayerProgress.multiplayer_game_id == game_id,
                    PlayerProgress.user_id == user_id
                )
            )
        )

        progress_obj = player_progress.scalar_one_or_none()
        if not progress_obj:
            raise EntityNotFoundError("Progression du joueur non trouvée")

        # Vérifier que le joueur a cet objet
        collected_items = progress_obj.collected_items or []
        available_item = None

        for item in collected_items:
            if item.get('type') == item_type.value and not item.get('used', False):
                available_item = item
                break

        if not available_item:
            raise ValidationError("Vous n'avez pas cet objet disponible")

        # Marquer l'objet comme utilisé
        available_item['used'] = True
        available_item['used_at'] = datetime.now(timezone.utc).isoformat()

        # Ajouter aux objets utilisés
        used_items = progress_obj.used_items or []
        used_items.append(available_item.copy())
        progress_obj.used_items = used_items

        # Appliquer l'effet selon le type d'objet
        effect_applied = True
        affected_players = target_players or [user_id]
        message = f"Objet {self.AVAILABLE_ITEMS[item_type]['name']} utilisé"

        if item_type in [ItemType.FREEZE_TIME, ItemType.ADD_MASTERMIND,
                         ItemType.REDUCE_ATTEMPTS, ItemType.SCRAMBLE_COLORS]:
            # Effets sur les adversaires
            if not target_players:
                # Appliquer à tous les autres joueurs
                all_players = await db.execute(
                    select(PlayerProgress.user_id)
                    .where(
                        and_(
                            PlayerProgress.multiplayer_game_id == game_id,
                            PlayerProgress.user_id != user_id,
                            PlayerProgress.status.in_([PlayerStatus.PLAYING, PlayerStatus.WAITING])
                        )
                    )
                )
                affected_players = [row[0] for row in all_players.all()]

            await self._apply_malus_effect(db, game_id, item_type, affected_players)

        else:
            # Effets sur soi-même
            await self._apply_bonus_effect(db, game_id, user_id, item_type)

        await db.commit()

        # Notifier via WebSocket
        await MultiplayerWebSocketManager.notify_item_used(
            str(game_id), user_id, available_item, affected_players
        )

        # Récupérer les objets restants
        remaining_items = [item for item in collected_items if not item.get('used', False)]

        return {
            "success": True,
            "message": message,
            "effect_applied": effect_applied,
            "remaining_items": remaining_items,
            "affected_players": affected_players,
            "effect_duration": self.AVAILABLE_ITEMS[item_type].get('duration_seconds')
        }

    async def get_available_items(self) -> Dict[str, Dict[str, Any]]:
        """Récupère la liste des objets disponibles"""
        return {item_type.value: info for item_type, info in self.AVAILABLE_ITEMS.items()}

    # Méthodes utilitaires privées

    async def _get_multiplayer_game_with_relations(
            self, db: AsyncSession, game_id: UUID
    ) -> Dict[str, Any]:
        """Récupère une partie multijoueur avec toutes ses relations"""

        result = await db.execute(
            select(MultiplayerGame, Game, User.username.label('creator_username'))
            .join(Game, MultiplayerGame.base_game_id == Game.id)
            .join(User, Game.created_by == User.id)
            .options(
                selectinload(MultiplayerGame.player_progresses),
                selectinload(MultiplayerGame.masterminds),
                selectinload(MultiplayerGame.leaderboard)
            )
            .where(MultiplayerGame.id == game_id)
        )

        row = result.first()
        if not row:
            raise EntityNotFoundError("Partie non trouvée")

        multiplayer_game, base_game, creator_username = row

        # Compter les joueurs actuels
        current_players = await db.execute(
            select(func.count(GameParticipation.id))
            .where(
                and_(
                    GameParticipation.game_id == base_game.id,
                    GameParticipation.status == ParticipationStatus.ACTIVE
                )
            )
        )

        return {
            "id": multiplayer_game.id,
            "base_game_id": base_game.id,
            "room_code": base_game.room_code,
            "game_type": multiplayer_game.game_type,
            "total_masterminds": multiplayer_game.total_masterminds,
            "difficulty": multiplayer_game.difficulty,
            "current_mastermind": multiplayer_game.current_mastermind,
            "is_final_mastermind": multiplayer_game.is_final_mastermind,
            "items_enabled": multiplayer_game.items_enabled,
            "items_per_mastermind": multiplayer_game.items_per_mastermind,
            "created_at": multiplayer_game.created_at,
            "started_at": multiplayer_game.started_at,
            "finished_at": multiplayer_game.finished_at,
            "status": base_game.status,
            "max_players": base_game.max_players,
            "current_players": current_players.scalar() or 0,
            "creator_username": creator_username,
            "is_private": base_game.is_private,
            "player_progresses": [self._format_player_progress(p) for p in multiplayer_game.player_progresses],
            "masterminds": [self._format_mastermind(m) for m in multiplayer_game.masterminds],
            "leaderboard": [self._format_leaderboard(l) for l in multiplayer_game.leaderboard]
        }

    def _format_player_progress(self, progress: PlayerProgress) -> Dict[str, Any]:
        """Formate la progression d'un joueur"""
        return {
            "id": progress.id,
            "user_id": progress.user_id,
            "username": progress.username,
            "current_mastermind": progress.current_mastermind,
            "completed_masterminds": progress.completed_masterminds,
            "total_score": progress.total_score,
            "total_time": progress.total_time,
            "status": progress.status,
            "is_finished": progress.is_finished,
            "finish_position": progress.finish_position,
            "finish_time": progress.finish_time,
            "collected_items": progress.collected_items or [],
            "used_items": progress.used_items or []
        }

    def _format_mastermind(self, mastermind: GameMastermind) -> Dict[str, Any]:
        """Formate un mastermind"""
        return {
            "id": mastermind.id,
            "mastermind_number": mastermind.mastermind_number,
            "combination_length": mastermind.combination_length,
            "available_colors": mastermind.available_colors,
            "max_attempts": mastermind.max_attempts,
            "is_active": mastermind.is_active,
            "is_completed": mastermind.is_completed,
            "completed_at": mastermind.completed_at
        }

    def _format_leaderboard(self, entry: PlayerLeaderboard) -> Dict[str, Any]:
        """Formate une entrée du classement"""
        return {
            "id": entry.id,
            "user_id": entry.user_id,
            "username": entry.username,
            "final_position": entry.final_position,
            "total_score": entry.total_score,
            "masterminds_completed": entry.masterminds_completed,
            "total_time": entry.total_time,
            "total_attempts": entry.total_attempts,
            "items_collected": entry.items_collected,
            "items_used": entry.items_used,
            "best_mastermind_time": entry.best_mastermind_time,
            "worst_mastermind_time": entry.worst_mastermind_time
        }

    async def _generate_items_for_player(
            self, db: AsyncSession, game_id: UUID, user_id: UUID
    ) -> List[Dict[str, Any]]:
        """Génère des objets aléatoirement pour un joueur"""

        # Logique simple de génération d'objets
        # Plus tard on peut ajouter de la complexité avec des probabilités
        import random

        items_to_give = []
        item_types = list(self.AVAILABLE_ITEMS.keys())

        # Donner 1-2 objets aléatoirement
        num_items = random.randint(1, 2)

        for _ in range(num_items):
            item_type = random.choice(item_types)
            item_info = self.AVAILABLE_ITEMS[item_type]

            item = {
                "type": item_type.value,
                "name": item_info["name"],
                "description": item_info["description"],
                "rarity": item_info["rarity"],
                "obtained_at": datetime.now(timezone.utc).isoformat(),
                "used": False
            }

            items_to_give.append(item)

        # Ajouter aux objets collectés du joueur
        player_progress = await db.execute(
            select(PlayerProgress)
            .where(
                and_(
                    PlayerProgress.multiplayer_game_id == game_id,
                    PlayerProgress.user_id == user_id
                )
            )
        )

        progress_obj = player_progress.scalar_one_or_none()
        if progress_obj:
            collected_items = progress_obj.collected_items or []
            collected_items.extend(items_to_give)
            progress_obj.collected_items = collected_items

        return items_to_give

    async def _apply_bonus_effect(
            self, db: AsyncSession, game_id: UUID, user_id: UUID, item_type: ItemType
    ) -> None:
        """Applique un effet bonus sur le joueur"""
        # Implémentation des effets bonus
        # Pour le moment, les effets sont principalement gérés côté frontend
        pass

    async def _apply_malus_effect(
            self, db: AsyncSession, game_id: UUID, item_type: ItemType, target_players: List[UUID]
    ) -> None:
        """Applique un effet malus sur les joueurs cibles"""
        # Implémentation des effets malus
        # Pour le moment, les effets sont principalement gérés côté frontend
        pass

    async def _calculate_final_position(
            self, db: AsyncSession, game_id: UUID, user_id: UUID
    ) -> int:
        """Calcule la position finale d'un joueur"""

        # Compter combien de joueurs ont déjà fini
        finished_count = await db.execute(
            select(func.count(PlayerProgress.id))
            .where(
                and_(
                    PlayerProgress.multiplayer_game_id == game_id,
                    PlayerProgress.is_finished == True,
                    PlayerProgress.finish_time < (
                        select(PlayerProgress.finish_time)
                        .where(
                            and_(
                                PlayerProgress.multiplayer_game_id == game_id,
                                PlayerProgress.user_id == user_id
                            )
                        )
                    )
                )
            )
        )

        return (finished_count.scalar() or 0) + 1

    async def _check_game_finished(self, db: AsyncSession, game_id: UUID) -> bool:
        """Vérifie si la partie est terminée"""

        # Compter les joueurs actifs
        active_players = await db.execute(
            select(func.count(PlayerProgress.id))
            .where(
                and_(
                    PlayerProgress.multiplayer_game_id == game_id,
                    PlayerProgress.status.in_([
                        PlayerStatus.PLAYING, PlayerStatus.WAITING, PlayerStatus.MASTERMIND_COMPLETE
                    ])
                )
            )
        )

        # Si plus aucun joueur actif, la partie est finie
        return (active_players.scalar() or 0) == 0

    async def _activate_next_mastermind(
            self, db: AsyncSession, game_obj: MultiplayerGame, mastermind_number: int
    ) -> Optional[Dict[str, Any]]:
        """Active le prochain mastermind"""

        for mastermind in game_obj.masterminds:
            if mastermind.mastermind_number == mastermind_number:
                mastermind.is_active = True
                return self._format_mastermind(mastermind)

        return None


# Instance globale du service
multiplayer_service = MultiplayerService()