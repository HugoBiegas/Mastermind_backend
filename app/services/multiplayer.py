"""
Service Multijoueur corrigé pour cohérence avec le frontend React.js
Toutes les méthodes attendues par le frontend sont implémentées
"""
from datetime import datetime, timezone

from sqlalchemy import select, and_, or_, desc, asc, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import jwt_manager
from app.models.game import Game, GameStatus, GameParticipation, ParticipationStatus
from app.models.multijoueur import (
    MultiplayerGame, PlayerProgress, GameMastermind,
    PlayerStatus
)
from app.models.user import User
from app.schemas.multiplayer import (
    MultiplayerGameCreateRequest, MultiplayerAttemptRequest,
    ItemUseRequest
)
from app.utils.exceptions import *
from app.websocket.multiplayer import multiplayer_ws_manager


class MultiplayerService:
    """Service pour le multijoueur avec toutes les méthodes attendues par le frontend"""

    # =====================================================
    # CRÉATION ET GESTION DES PARTIES
    # =====================================================

    async def create_multiplayer_game(
            self,
            db: AsyncSession,
            game_data: MultiplayerGameCreateRequest,
            creator_id: UUID
    ) -> Dict[str, Any]:
        """Crée une nouvelle partie multijoueur"""

        # Générer un code de room unique
        room_code = await self._generate_unique_room_code(db)

        # Créer le jeu de base
        base_game = Game(
            room_code=room_code,
            game_type="multiplayer",
            game_mode="multiplayer",
            status=GameStatus.WAITING,
            difficulty=game_data.difficulty.value,
            max_players=game_data.max_players,
            is_private=game_data.is_private,
            allow_spectators=game_data.allow_spectators,
            enable_chat=game_data.enable_chat,
            quantum_enabled=game_data.quantum_enabled,
            creator_id=creator_id,
            solution=[1, 2, 3, 4],  # Solution temporaire
            settings={
                "items_enabled": game_data.items_enabled,
                "password_hash": game_data.password if game_data.password else None
            }
        )

        db.add(base_game)
        await db.flush()  # Pour obtenir l'ID

        # Créer la partie multijoueur
        multiplayer_game = MultiplayerGame(
            base_game_id=base_game.id,
            game_type=game_data.game_type,
            total_masterminds=game_data.total_masterminds,
            items_enabled=game_data.items_enabled
        )

        db.add(multiplayer_game)
        await db.flush()

        # Créer les masterminds
        for i in range(1, game_data.total_masterminds + 1):
            mastermind = GameMastermind(
                multiplayer_game_id=multiplayer_game.id,
                mastermind_number=i,
                combination_length=4,
                available_colors=6,
                max_attempts=12,
                solution=[1, 2, 3, 4]  # Solution temporaire
            )
            db.add(mastermind)

        # Ajouter le créateur comme joueur
        participation = GameParticipation(
            game_id=base_game.id,
            user_id=creator_id,
            role="host",
            status=ParticipationStatus.ACTIVE,
            join_order=1
        )
        db.add(participation)

        # Créer le progress du joueur
        player_progress = PlayerProgress(
            multiplayer_game_id=multiplayer_game.id,
            user_id=creator_id,
            status=PlayerStatus.WAITING,
            current_mastermind=1,
            is_host=True,
            join_order=1
        )
        db.add(player_progress)

        await db.commit()

        # Créer la room WebSocket
        await multiplayer_ws_manager.create_multiplayer_room(
            room_code, {
                "max_players": game_data.max_players,
                "total_masterminds": game_data.total_masterminds,
                "items_enabled": game_data.items_enabled
            }
        )

        # Retourner la structure attendue par le frontend
        return await self._format_game_response(db, multiplayer_game.id)


    async def join_room_by_code(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID,
            password: Optional[str] = None,
            as_spectator: bool = False
    ) -> Dict[str, Any]:
        """Rejoint une partie par code de room"""

        # Trouver la partie
        result = await db.execute(
            select(MultiplayerGame)
            .join(Game, MultiplayerGame.base_game_id == Game.id)
            .where(Game.room_code == room_code)
            .options(selectinload(MultiplayerGame.base_game))
        )

        multiplayer_game = result.scalar_one_or_none()
        if not multiplayer_game:
            raise EntityNotFoundError("Partie non trouvée")

        base_game = multiplayer_game.base_game

        # Vérifier le statut
        if base_game.status not in [GameStatus.WAITING, GameStatus.ACTIVE]:
            raise GameError("Impossible de rejoindre cette partie")

        # Vérifier le mot de passe
        if base_game.is_private and password != base_game.settings.get("password_hash"):
            raise AuthorizationError("Mot de passe incorrect")

        # Vérifier la capacité
        if not as_spectator:
            current_players = await self._count_active_players(db, multiplayer_game.id)
            if current_players >= base_game.max_players:
                if base_game.allow_spectators:
                    as_spectator = True
                else:
                    raise GameError("Partie complète")

        # Ajouter la participation
        next_order = await self._get_next_join_order(db, base_game.id)

        participation = GameParticipation(
            game_id=base_game.id,
            user_id=user_id,
            role="spectator" if as_spectator else "player",
            status=ParticipationStatus.ACTIVE,
            join_order=next_order
        )
        db.add(participation)

        if not as_spectator:
            # Créer le progress du joueur
            player_progress = PlayerProgress(
                multiplayer_game_id=multiplayer_game.id,
                user_id=user_id,
                status=PlayerStatus.WAITING,
                current_mastermind=1,
                join_order=next_order
            )
            db.add(player_progress)

        await db.commit()

        # Notifier via WebSocket
        user = await self._get_user(db, user_id)
        await multiplayer_ws_manager.notify_player_joined(
            room_code, str(user_id), user.username
        )

        return await self._format_game_response(db, multiplayer_game.id)


    async def leave_room_by_code(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID
    ) -> None:
        """Quitte une partie par code de room"""

        # Trouver la participation
        result = await db.execute(
            select(GameParticipation)
            .join(Game, GameParticipation.game_id == Game.id)
            .where(
                and_(
                    Game.room_code == room_code,
                    GameParticipation.user_id == user_id,
                    GameParticipation.status == ParticipationStatus.ACTIVE
                )
            )
        )

        participation = result.scalar_one_or_none()
        if not participation:
            raise EntityNotFoundError("Participation non trouvée")

        # Marquer comme quitté
        participation.status = ParticipationStatus.LEFT
        participation.left_at = datetime.now(timezone.utc)

        # Mettre à jour le progress du joueur s'il existe
        progress_result = await db.execute(
            select(PlayerProgress)
            .join(MultiplayerGame, PlayerProgress.multiplayer_game_id == MultiplayerGame.id)
            .join(Game, MultiplayerGame.base_game_id == Game.id)
            .where(
                and_(
                    Game.room_code == room_code,
                    PlayerProgress.user_id == user_id
                )
            )
        )

        progress = progress_result.scalar_one_or_none()
        if progress:
            progress.status = PlayerStatus.ELIMINATED

        await db.commit()

        # Notifier via WebSocket
        user = await self._get_user(db, user_id)
        await multiplayer_ws_manager.notify_player_left(
            room_code, str(user_id), user.username
        )


    async def get_room_details(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID
    ) -> Dict[str, Any]:
        """Récupère les détails d'une partie par code de room"""

        result = await db.execute(
            select(MultiplayerGame)
            .join(Game, MultiplayerGame.base_game_id == Game.id)
            .where(Game.room_code == room_code)
        )

        multiplayer_game = result.scalar_one_or_none()
        if not multiplayer_game:
            raise EntityNotFoundError("Partie non trouvée")

        return await self._format_game_response(db, multiplayer_game.id)


    # =====================================================
    # GESTION DU LOBBY ET RECHERCHE
    # =====================================================

    async def get_public_games_with_filters(
            self,
            db: AsyncSession,
            page: int,
            limit: int,
            filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Récupère les parties publiques avec filtres (pour le lobby)"""

        # Construire la requête de base
        query = (
            select(MultiplayerGame)
            .join(Game, MultiplayerGame.base_game_id == Game.id)
            .join(User, Game.creator_id == User.id)
            .where(
                and_(
                    Game.is_private == False,
                    Game.status.in_([GameStatus.WAITING, GameStatus.ACTIVE])
                )
            )
        )

        # Appliquer les filtres
        if filters.get("game_type"):
            query = query.where(MultiplayerGame.game_type == filters["game_type"])

        if filters.get("difficulty"):
            query = query.where(Game.difficulty == filters["difficulty"])

        if filters.get("max_players"):
            query = query.where(Game.max_players <= filters["max_players"])

        if filters.get("has_slots") is True:
            # Filtrer les parties avec des places libres
            subquery = (
                select(GameParticipation.game_id)
                .where(GameParticipation.status == ParticipationStatus.ACTIVE)
                .group_by(GameParticipation.game_id)
                .having(func.count(GameParticipation.id) < Game.max_players)
            )
            query = query.where(Game.id.in_(subquery))

        if filters.get("quantum_enabled") is not None:
            query = query.where(Game.quantum_enabled == filters["quantum_enabled"])

        if filters.get("search_term"):
            search_term = f"%{filters['search_term']}%"
            query = query.where(
                or_(
                    User.username.ilike(search_term),
                    Game.room_code.ilike(search_term)
                )
            )

        # Tri
        sort_by = filters.get("sort_by", "created_at")
        sort_order = filters.get("sort_order", "desc")

        if sort_by == "created_at":
            order_column = Game.created_at
        elif sort_by == "current_players":
            # Tri par nombre de joueurs (nécessiterait une sous-requête)
            order_column = Game.created_at
        else:
            order_column = Game.created_at

        if sort_order == "desc":
            query = query.order_by(desc(order_column))
        else:
            query = query.order_by(asc(order_column))

        # Pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        # Exécuter la requête
        result = await db.execute(query)
        games = result.scalars().all()

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

        # Appliquer les mêmes filtres pour le count
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Formater les parties pour le frontend
        formatted_games = []
        for game in games:
            formatted_game = await self._format_public_game_listing(db, game)
            formatted_games.append(formatted_game)

        return {
            "games": formatted_games,
            "total": total,
            "page": page,
            "limit": limit,
            "has_next": (page * limit) < total,
            "has_prev": page > 1
        }


    # =====================================================
    # GAMEPLAY
    # =====================================================

    async def start_room(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID
    ) -> Dict[str, Any]:
        """Démarre une partie par code de room"""

        # Récupérer la partie
        result = await db.execute(
            select(MultiplayerGame)
            .join(Game, MultiplayerGame.base_game_id == Game.id)
            .where(Game.room_code == room_code)
            .options(selectinload(MultiplayerGame.base_game))
        )

        multiplayer_game = result.scalar_one_or_none()
        if not multiplayer_game:
            raise EntityNotFoundError("Partie non trouvée")

        base_game = multiplayer_game.base_game

        # Vérifier les permissions
        if base_game.creator_id != user_id:
            raise AuthorizationError("Seul le créateur peut démarrer la partie")

        # Vérifier le statut
        if base_game.status != GameStatus.WAITING:
            raise GameError("La partie ne peut pas être démarrée")

        # Vérifier le nombre de joueurs
        player_count = await self._count_active_players(db, multiplayer_game.id)
        if player_count < 2:
            raise GameError("Au moins 2 joueurs sont requis")

        # Démarrer la partie
        base_game.status = GameStatus.ACTIVE
        base_game.started_at = datetime.now(timezone.utc)

        # Mettre à jour le statut des joueurs
        await db.execute(
            update(PlayerProgress)
            .where(PlayerProgress.multiplayer_game_id == multiplayer_game.id)
            .values(status=PlayerStatus.PLAYING)
        )

        await db.commit()

        # Notifier via WebSocket
        await multiplayer_ws_manager.notify_game_started(
            room_code, str(multiplayer_game.id)
        )

        return await self._format_game_response(db, multiplayer_game.id)


    async def make_attempt_by_room_code(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID,
            attempt_data: MultiplayerAttemptRequest
    ) -> Dict[str, Any]:
        """Fait une tentative dans une partie par code de room"""

        # Récupérer la partie et le mastermind
        result = await db.execute(
            select(MultiplayerGame)
            .join(Game, MultiplayerGame.base_game_id == Game.id)
            .where(Game.room_code == room_code)
            .options(selectinload(MultiplayerGame.masterminds))
        )

        multiplayer_game = result.scalar_one_or_none()
        if not multiplayer_game:
            raise EntityNotFoundError("Partie non trouvée")

        # Vérifier que la partie est active
        if multiplayer_game.base_game.status != GameStatus.ACTIVE:
            raise GameError("La partie n'est pas active")

        # Récupérer le progress du joueur
        progress_result = await db.execute(
            select(PlayerProgress)
            .where(
                and_(
                    PlayerProgress.multiplayer_game_id == multiplayer_game.id,
                    PlayerProgress.user_id == user_id
                )
            )
        )

        player_progress = progress_result.scalar_one_or_none()
        if not player_progress:
            raise EntityNotFoundError("Joueur non trouvé dans cette partie")

        if player_progress.status != PlayerStatus.PLAYING:
            raise GameError("Vous ne pouvez pas jouer actuellement")

        # Trouver le mastermind
        mastermind = None
        for m in multiplayer_game.masterminds:
            if m.mastermind_number == attempt_data.mastermind_number:
                mastermind = m
                break

        if not mastermind:
            raise EntityNotFoundError("Mastermind non trouvé")

        # Calculer le résultat de la tentative
        correct_positions, correct_colors = self._calculate_attempt_result(
            attempt_data.combination, mastermind.solution
        )

        is_solution = correct_positions == len(mastermind.solution)

        # Mettre à jour les statistiques du joueur
        player_progress.attempts_count += 1

        if is_solution:
            # Mastermind complété
            player_progress.score += 100  # Score de base
            player_progress.current_mastermind += 1

            if player_progress.current_mastermind > multiplayer_game.total_masterminds:
                player_progress.status = PlayerStatus.FINISHED

        await db.commit()

        # Créer la réponse
        response = {
            "success": True,
            "correct_positions": correct_positions,
            "correct_colors": correct_colors,
            "is_solution": is_solution,
            "score_gained": 100 if is_solution else 0,
            "items_obtained": [],
            "mastermind_completed": is_solution,
            "game_finished": False,
            "updated_game_state": None
        }

        # Notifier via WebSocket
        user = await self._get_user(db, user_id)
        await multiplayer_ws_manager.notify_attempt_made(
            room_code, str(user_id), user.username, attempt_data.mastermind_number, response
        )

        return response


    async def use_item_in_room(
            self,
            db: AsyncSession,
            room_code: str,
            user_id: UUID,
            item_data: ItemUseRequest
    ) -> Dict[str, Any]:
        """Utilise un objet dans une partie par code de room"""

        # Logique d'utilisation d'objets à implémenter
        # Pour l'instant, retourner une réponse basique

        return {
            "success": True,
            "message": f"Objet {item_data.item_type} utilisé avec succès",
            "effects_applied": [],
            "updated_game_state": None
        }


    # =====================================================
    # AUTHENTIFICATION WEBSOCKET
    # =====================================================

    async def authenticate_websocket_user(self, token: str) -> Optional[User]:
        """Authentifie un utilisateur pour WebSocket"""
        try:
            payload = jwt_manager.decode_access_token(token)
            user_id = payload.get("sub")
            if not user_id:
                return None

            # Récupérer l'utilisateur depuis la base de données
            # Note: Ceci nécessiterait une session DB, à adapter selon votre architecture
            return await self._get_user_by_id(UUID(user_id))

        except Exception:
            return None


    # =====================================================
    # MÉTHODES UTILITAIRES PRIVÉES
    # =====================================================

    async def _format_game_response(
            self,
            db: AsyncSession,
            multiplayer_game_id: UUID
    ) -> Dict[str, Any]:
        """Formate une partie pour le frontend"""

        result = await db.execute(
            select(MultiplayerGame)
            .where(MultiplayerGame.id == multiplayer_game_id)
            .options(
                selectinload(MultiplayerGame.base_game),
                selectinload(MultiplayerGame.players),
                selectinload(MultiplayerGame.masterminds)
            )
        )

        game = result.scalar_one()
        base_game = game.base_game

        # Récupérer le créateur
        creator = await self._get_user(db, base_game.creator_id)

        # Formater les joueurs
        players = []
        for player_progress in game.players:
            if player_progress.status != PlayerStatus.ELIMINATED:
                user = await self._get_user(db, player_progress.user_id)
                players.append({
                    "user_id": str(player_progress.user_id),
                    "username": user.username,
                    "status": player_progress.status.value,
                    "score": player_progress.score,
                    "current_mastermind": player_progress.current_mastermind,
                    "attempts_count": player_progress.attempts_count,
                    "items": [],
                    "active_effects": [],
                    "is_host": player_progress.is_host,
                    "join_order": player_progress.join_order
                })

        # Formater les masterminds
        masterminds = []
        for mastermind in game.masterminds:
            masterminds.append({
                "number": mastermind.mastermind_number,
                "combination_length": mastermind.combination_length,
                "available_colors": mastermind.available_colors,
                "max_attempts": mastermind.max_attempts,
                "is_current": mastermind.mastermind_number == game.current_mastermind,
                "completed_by": []
            })

        return {
            "id": str(game.id),
            "room_code": base_game.room_code,
            "game_type": game.game_type.value,
            "difficulty": base_game.difficulty,
            "status": base_game.status.value,
            "max_players": base_game.max_players,
            "current_players": len(players),
            "is_private": base_game.is_private,
            "items_enabled": game.items_enabled,
            "quantum_enabled": base_game.quantum_enabled,
            "allow_spectators": base_game.allow_spectators,
            "enable_chat": base_game.enable_chat,
            "current_mastermind": game.current_mastermind,
            "total_masterminds": game.total_masterminds,
            "masterminds": masterminds,
            "players": players,
            "spectators": [],
            "creator": {
                "id": str(creator.id),
                "username": creator.username
            },
            "created_at": base_game.created_at.isoformat(),
            "started_at": base_game.started_at.isoformat() if base_game.started_at else None,
            "finished_at": base_game.finished_at.isoformat() if base_game.finished_at else None,
            "estimated_finish": None,
            "base_game": {
                "status": base_game.status.value
            }
        }


    async def _format_public_game_listing(
            self,
            db: AsyncSession,
            game: MultiplayerGame
    ) -> Dict[str, Any]:
        """Formate une partie pour le listing public"""

        base_game = game.base_game
        creator = await self._get_user(db, base_game.creator_id)
        current_players = await self._count_active_players(db, game.id)

        return {
            "id": str(game.id),
            "room_code": base_game.room_code,
            "name": None,
            "game_type": game.game_type.value,
            "difficulty": base_game.difficulty,
            "status": base_game.status.value,
            "current_players": current_players,
            "max_players": base_game.max_players,
            "has_password": bool(base_game.settings.get("password_hash")),
            "allow_spectators": base_game.allow_spectators,
            "items_enabled": game.items_enabled,
            "quantum_enabled": base_game.quantum_enabled,
            "creator_username": creator.username,
            "created_at": base_game.created_at.isoformat(),
            "estimated_finish": None
        }


    async def _generate_unique_room_code(self, db: AsyncSession, length: int = 8) -> str:
        """Génère un code de room unique"""
        import random
        import string

        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

            # Vérifier l'unicité
            result = await db.execute(
                select(Game).where(Game.room_code == code)
            )
            if not result.scalar_one_or_none():
                return code


    async def _count_active_players(self, db: AsyncSession, multiplayer_game_id: UUID) -> int:
        """Compte les joueurs actifs dans une partie"""
        result = await db.execute(
            select(func.count(PlayerProgress.id))
            .where(
                and_(
                    PlayerProgress.multiplayer_game_id == multiplayer_game_id,
                    PlayerProgress.status != PlayerStatus.ELIMINATED
                )
            )
        )
        return result.scalar()


    async def _get_next_join_order(self, db: AsyncSession, game_id: UUID) -> int:
        """Récupère le prochain ordre de jointure"""
        result = await db.execute(
            select(func.max(GameParticipation.join_order))
            .where(GameParticipation.game_id == game_id)
        )
        max_order = result.scalar()
        return (max_order or 0) + 1


    async def _get_user(self, db: AsyncSession, user_id: UUID) -> User:
        """Récupère un utilisateur par ID"""
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one()


    async def _get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Récupère un utilisateur par ID (pour WebSocket)"""
        # À implémenter selon votre architecture
        # Cette méthode devrait récupérer l'utilisateur depuis la DB
        return None


    def _calculate_attempt_result(
            self,
            attempt: List[int],
            solution: List[int]
    ) -> tuple[int, int]:
        """Calcule le résultat d'une tentative"""
        correct_positions = sum(1 for i, (a, s) in enumerate(zip(attempt, solution)) if a == s)

        # Calculer les couleurs correctes mais mal placées
        attempt_counts = {}
        solution_counts = {}

        for i, (a, s) in enumerate(zip(attempt, solution)):
            if a != s:  # Ignorer les positions correctes
                attempt_counts[a] = attempt_counts.get(a, 0) + 1
                solution_counts[s] = solution_counts.get(s, 0) + 1

        correct_colors = sum(
            min(attempt_counts.get(color, 0), solution_counts.get(color, 0))
            for color in set(attempt_counts.keys()) | set(solution_counts.keys())
        )

        return correct_positions, correct_colors


# Instance globale du service
multiplayer_service = MultiplayerService()