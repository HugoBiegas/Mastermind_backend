"""
Service de gestion des jeux pour Quantum Mastermind
Logique métier pour les parties, tentatives et scoring
"""
import json
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, or_, desc
from sqlalchemy.orm import selectinload, joinedload

from app.models.game import (
    Game, GameParticipation, GameAttempt, GameType, GameMode,
    GameStatus, Difficulty, ParticipationStatus, generate_room_code,
    calculate_game_score
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.game import GameCreate, GameJoin, AttemptCreate
from app.utils.exceptions import (
    EntityNotFoundError, GameError, GameNotActiveError,
    GameFullError, ValidationError, AuthorizationError
)


class GameService:
    """Service principal pour la gestion des jeux"""

    def __init__(self):
        self.user_repo = UserRepository()

    # === CRÉATION ET GESTION DES PARTIES ===

    async def create_game(
        self,
        db: AsyncSession,
        game_data: GameCreate,
        creator_id: UUID
    ) -> Dict[str, Any]:
        """
        Crée une nouvelle partie

        Args:
            db: Session de base de données
            game_data: Données de création
            creator_id: ID du créateur

        Returns:
            Informations de la partie créée

        Raises:
            ValidationError: Si les données sont invalides
        """
        try:
            # Validation des données
            await self._validate_game_creation(db, game_data, creator_id)

            # Génération du code de room si non fourni
            room_code = game_data.room_code
            if not room_code:
                room_code = await self._generate_unique_room_code(db)

            # Configuration basée sur la difficulté
            difficulty_config = self._get_difficulty_config(game_data.difficulty)

            # Hachage du mot de passe si fourni
            password_hash = None
            if game_data.password:
                password_hash = hashlib.sha256(game_data.password.encode()).hexdigest()

            # Création de la partie
            game = Game(
                room_code=room_code,
                game_type=game_data.game_type,
                game_mode=game_data.game_mode,
                difficulty=game_data.difficulty,
                max_attempts=game_data.max_attempts or difficulty_config["attempts"],
                combination_length=difficulty_config["length"],
                color_count=difficulty_config["colors"],
                time_limit_seconds=game_data.time_limit,
                max_players=game_data.max_players,
                is_private=game_data.is_private,
                password_hash=password_hash,
                creator_id=creator_id,
                settings=game_data.settings or {}
            )

            # Génération de la solution
            await self._generate_solution(game)

            db.add(game)
            await db.commit()
            await db.refresh(game)

            # Ajouter le créateur comme participant si c'est un jeu multijoueur
            if game.max_players > 1:
                await self._add_participant(db, game.id, creator_id)

            return {
                "game_id": str(game.id),
                "room_code": game.room_code,
                "game_type": game.game_type,
                "status": game.status,
                "max_players": game.max_players,
                "difficulty": game.difficulty,
                "created_at": game.created_at.isoformat()
            }

        except Exception as e:
            await db.rollback()
            raise ValidationError(f"Erreur lors de la création de la partie: {str(e)}")

    async def join_game(
        self,
        db: AsyncSession,
        game_id: UUID,
        player_id: UUID,
        join_data: GameJoin
    ) -> Dict[str, Any]:
        """
        Fait rejoindre un joueur à une partie

        Args:
            db: Session de base de données
            game_id: ID de la partie
            player_id: ID du joueur
            join_data: Données de participation

        Returns:
            Informations de participation

        Raises:
            EntityNotFoundError: Si la partie n'existe pas
            GameFullError: Si la partie est complète
            GameNotActiveError: Si la partie ne peut pas être rejointe
        """
        # Récupérer la partie
        game = await self._get_game_with_participations(db, game_id)
        if not game:
            raise EntityNotFoundError("Partie non trouvée", "Game", game_id)

        # Vérifications
        if not game.can_join:
            if game.is_full:
                raise GameFullError(
                    "Partie complète",
                    game_id=game_id,
                    max_players=game.max_players,
                    current_players=game.active_player_count
                )
            else:
                raise GameNotActiveError(
                    "Impossible de rejoindre cette partie",
                    game_id=game_id,
                    current_status=game.status
                )

        # Vérification du mot de passe si nécessaire
        if game.password_hash and join_data.password:
            password_hash = hashlib.sha256(join_data.password.encode()).hexdigest()
            if password_hash != game.password_hash:
                raise AuthorizationError("Mot de passe incorrect")
        elif game.password_hash:
            raise AuthorizationError("Mot de passe requis")

        # Vérifier si le joueur n'est pas déjà dans la partie
        existing = await self._get_participation(db, game_id, player_id)
        if existing:
            if existing.status == ParticipationStatus.ACTIVE:
                raise ValidationError("Vous participez déjà à cette partie")
            else:
                # Réactiver la participation
                existing.status = ParticipationStatus.ACTIVE
                existing.joined_at = datetime.now(timezone.utc)
                await db.commit()
                return {"participation_id": str(existing.id), "rejoined": True}

        # Créer la participation
        participation = await self._add_participant(
            db, game_id, player_id, join_data.player_name
        )

        return {
            "participation_id": str(participation.id),
            "game_info": {
                "id": str(game.id),
                "room_code": game.room_code,
                "status": game.status,
                "player_count": game.active_player_count + 1,
                "max_players": game.max_players
            }
        }

    async def start_game(
        self,
        db: AsyncSession,
        game_id: UUID,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Démarre une partie

        Args:
            db: Session de base de données
            game_id: ID de la partie
            user_id: ID de l'utilisateur qui démarre

        Returns:
            État de la partie démarrée

        Raises:
            EntityNotFoundError: Si la partie n'existe pas
            AuthorizationError: Si l'utilisateur ne peut pas démarrer
            GameError: Si la partie ne peut pas être démarrée
        """
        game = await self._get_game_with_participations(db, game_id)
        if not game:
            raise EntityNotFoundError("Partie non trouvée", "Game", game_id)

        # Vérifier les permissions
        if game.creator_id != user_id:
            raise AuthorizationError("Seul le créateur peut démarrer la partie")

        # Vérifier l'état
        if game.status != GameStatus.WAITING:
            raise GameError(f"La partie ne peut pas être démarrée (statut: {game.status})")

        # Vérifier qu'il y a assez de joueurs
        if game.game_mode != GameMode.SOLO and game.active_player_count < 2:
            raise GameError("Au moins 2 joueurs requis pour démarrer")

        # Démarrer la partie
        game.start_game()
        await db.commit()

        return await self.get_game_state(db, game_id)

    # === GAMEPLAY ===

    async def make_attempt(
        self,
        db: AsyncSession,
        game_id: UUID,
        player_id: UUID,
        attempt: AttemptCreate
    ) -> Dict[str, Any]:
        """
        Traite une tentative de solution

        Args:
            db: Session de base de données
            game_id: ID de la partie
            player_id: ID du joueur
            attempt: Données de la tentative

        Returns:
            Résultat de la tentative
        """
        # Récupérer la partie et la participation
        game = await self._get_game_with_participations(db, game_id)
        if not game:
            raise EntityNotFoundError("Partie non trouvée", "Game", game_id)

        if not game.is_active:
            raise GameNotActiveError("La partie n'est pas active", game_id, game.status)

        participation = await self._get_participation(db, game_id, player_id)
        if not participation or participation.status != ParticipationStatus.ACTIVE:
            raise AuthorizationError("Vous ne participez pas à cette partie")

        # Vérifier les limites
        if participation.attempts_made >= game.max_attempts:
            raise GameError("Nombre maximum de tentatives atteint")

        # Valider la combinaison
        if len(attempt.combination) != game.combination_length:
            raise ValidationError(f"La combinaison doit contenir {game.combination_length} éléments")

        # Calculer le résultat
        black_pegs, white_pegs = self._calculate_pegs(
            attempt.combination,
            json.loads(game.classical_solution)
        )

        is_solution = black_pegs == game.combination_length

        # Créer la tentative
        game_attempt = GameAttempt(
            game_id=game_id,
            player_id=player_id,
            attempt_number=participation.attempts_made + 1,
            combination=json.dumps(attempt.combination),
            black_pegs=black_pegs,
            white_pegs=white_pegs,
            is_solution=is_solution,
            used_quantum_hint=attempt.use_quantum_hint or False
        )

        db.add(game_attempt)

        # Mettre à jour les statistiques
        participation.attempts_made += 1
        game.total_attempts += 1

        # Si c'est la solution
        if is_solution:
            await self._handle_solution_found(db, game, participation, game_attempt)

        await db.commit()

        result = {
            "attempt_number": game_attempt.attempt_number,
            "combination": attempt.combination,
            "black_pegs": black_pegs,
            "white_pegs": white_pegs,
            "is_solution": is_solution,
            "attempts_remaining": game.max_attempts - participation.attempts_made,
            "game_finished": is_solution or participation.attempts_made >= game.max_attempts
        }

        if is_solution:
            result["congratulations"] = True
            result["score"] = participation.score

        return result

    async def make_attempt_websocket(
        self,
        db: AsyncSession,
        game_id: UUID,
        player_id: UUID,
        combination: List[Any]
    ) -> Dict[str, Any]:
        """Version WebSocket de make_attempt"""
        attempt_data = AttemptCreate(combination=combination)
        return await self.make_attempt(db, game_id, player_id, attempt_data)

    # === ÉTAT ET INFORMATIONS ===

    async def get_game_state(
        self,
        db: AsyncSession,
        game_id: UUID
    ) -> Dict[str, Any]:
        """
        Récupère l'état complet d'une partie

        Args:
            db: Session de base de données
            game_id: ID de la partie

        Returns:
            État complet de la partie
        """
        game = await self._get_game_with_all_relations(db, game_id)
        if not game:
            raise EntityNotFoundError("Partie non trouvée", "Game", game_id)

        # Participants actifs
        participants = []
        for participation in game.participations:
            if participation.status == ParticipationStatus.ACTIVE:
                participants.append({
                    "player_id": str(participation.player_id),
                    "username": participation.player.username,
                    "player_name": participation.player_name or participation.player.username,
                    "attempts_made": participation.attempts_made,
                    "score": participation.score,
                    "is_winner": participation.is_winner,
                    "quantum_hints_used": participation.quantum_hints_used
                })

        # Dernières tentatives (pour l'historique)
        recent_attempts = []
        for attempt in game.attempts.order_by(desc(GameAttempt.created_at)).limit(10):
            recent_attempts.append({
                "player_id": str(attempt.player_id),
                "username": attempt.player.username,
                "attempt_number": attempt.attempt_number,
                "black_pegs": attempt.black_pegs,
                "white_pegs": attempt.white_pegs,
                "is_solution": attempt.is_solution,
                "created_at": attempt.created_at.isoformat()
            })

        return {
            "game_id": str(game.id),
            "room_code": game.room_code,
            "status": game.status,
            "game_type": game.game_type,
            "game_mode": game.game_mode,
            "difficulty": game.difficulty,
            "combination_length": game.combination_length,
            "color_count": game.color_count,
            "max_attempts": game.max_attempts,
            "max_players": game.max_players,
            "current_turn": game.current_turn,
            "total_attempts": game.total_attempts,
            "participants": participants,
            "recent_attempts": recent_attempts,
            "started_at": game.started_at.isoformat() if game.started_at else None,
            "duration_minutes": game.duration_minutes,
            "settings": game.settings
        }

    async def get_spectator_view(
        self,
        db: AsyncSession,
        game_id: UUID
    ) -> Dict[str, Any]:
        """Vue pour les spectateurs (informations limitées)"""
        state = await self.get_game_state(db, game_id)

        # Masquer les informations sensibles pour les spectateurs
        for participant in state["participants"]:
            participant.pop("quantum_hints_used", None)

        # Limiter l'historique
        state["recent_attempts"] = state["recent_attempts"][:5]

        return state

    # === GESTION AVANCÉE ===

    async def pause_game(
        self,
        db: AsyncSession,
        game_id: UUID,
        user_id: UUID
    ) -> None:
        """Met en pause une partie"""
        game = await self._get_game_by_id(db, game_id)
        if not game:
            raise EntityNotFoundError("Partie non trouvée", "Game", game_id)

        if game.creator_id != user_id:
            raise AuthorizationError("Seul le créateur peut mettre en pause")

        game.pause_game()
        await db.commit()

    async def moderate_game(
        self,
        db: AsyncSession,
        game_id: UUID,
        action: str,
        reason: str,
        moderator_id: UUID
    ) -> None:
        """Actions de modération sur une partie"""
        game = await self._get_game_by_id(db, game_id)
        if not game:
            raise EntityNotFoundError("Partie non trouvée", "Game", game_id)

        if action == "terminate":
            game.status = GameStatus.CANCELLED
            game.finished_at = datetime.now(timezone.utc)
        elif action == "pause":
            game.pause_game()
        elif action == "resume":
            game.resume_game()

        await db.commit()

    # === STATISTIQUES ET CLASSEMENTS ===

    async def get_leaderboard(
        self,
        db: AsyncSession,
        game_type: Optional[GameType] = None,
        time_period: str = "all",
        limit: int = 10
    ) -> Dict[str, Any]:
        """Récupère le classement des joueurs"""

        # Base query
        query = select(User).where(User.is_active == True)

        # Filtrage par période
        if time_period != "all":
            cutoff_date = datetime.now(timezone.utc)
            if time_period == "week":
                cutoff_date -= timedelta(weeks=1)
            elif time_period == "month":
                cutoff_date -= timedelta(days=30)

            # TODO: Ajouter filtrage par date quand on aura les stats par période

        # Ordre par score total (pour l'instant)
        query = query.order_by(desc(User.total_score)).limit(limit)

        result = await db.execute(query)
        users = result.scalars().all()

        leaderboard = []
        for i, user in enumerate(users, 1):
            leaderboard.append({
                "position": i,
                "user_id": str(user.id),
                "username": user.username,
                "total_score": user.total_score,
                "total_games": user.total_games,
                "win_rate": user.win_rate,
                "quantum_points": user.quantum_points,
                "rank": user.rank
            })

        return {
            "type": game_type or "all",
            "period": time_period,
            "entries": leaderboard,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

    # === MÉTHODES PRIVÉES ===

    async def _validate_game_creation(
        self,
        db: AsyncSession,
        game_data: GameCreate,
        creator_id: UUID
    ) -> None:
        """Valide les données de création de partie"""

        # Vérifier l'utilisateur
        user = await self.user_repo.get_by_id(db, creator_id)
        if not user or not user.is_active:
            raise ValidationError("Utilisateur invalide")

        # Vérifier les limites
        if game_data.max_attempts and (game_data.max_attempts < 1 or game_data.max_attempts > 50):
            raise ValidationError("Le nombre de tentatives doit être entre 1 et 50")

        if game_data.max_players < 1 or game_data.max_players > 8:
            raise ValidationError("Le nombre de joueurs doit être entre 1 et 8")

        # Vérifier le code de room si fourni
        if game_data.room_code:
            existing = await self._get_game_by_room_code(db, game_data.room_code)
            if existing:
                raise ValidationError("Ce code de room est déjà utilisé")

    async def _generate_unique_room_code(self, db: AsyncSession) -> str:
        """Génère un code de room unique"""
        for _ in range(10):  # Essayer 10 fois
            code = generate_room_code()
            existing = await self._get_game_by_room_code(db, code)
            if not existing:
                return code

        # Si on n'arrive pas à générer un code unique, utiliser un UUID
        return str(uuid4())[:8].upper()

    def _get_difficulty_config(self, difficulty: Difficulty) -> Dict[str, int]:
        """Récupère la configuration d'une difficulté"""
        configs = {
            Difficulty.EASY: {"colors": 4, "length": 3, "attempts": 15},
            Difficulty.NORMAL: {"colors": 6, "length": 4, "attempts": 12},
            Difficulty.HARD: {"colors": 8, "length": 5, "attempts": 10},
            Difficulty.EXPERT: {"colors": 10, "length": 6, "attempts": 8}
        }
        return configs.get(difficulty, configs[Difficulty.NORMAL])

    async def _generate_solution(self, game: Game) -> None:
        """Génère la solution pour une partie"""
        import random

        # Solution classique
        colors = list(range(game.color_count))
        solution = random.choices(colors, k=game.combination_length)
        game.classical_solution = json.dumps(solution)

        # Hash de vérification
        solution_str = json.dumps(solution, sort_keys=True)
        game.solution_hash = hashlib.sha256(solution_str.encode()).hexdigest()

        # TODO: Générer solution quantique si nécessaire
        if game.game_type in [GameType.QUANTUM, GameType.HYBRID]:
            game.quantum_solution = "quantum_state_placeholder"

    def _calculate_pegs(
        self,
        guess: List[Any],
        solution: List[Any]
    ) -> Tuple[int, int]:
        """
        Calcule les pions noirs et blancs pour une tentative

        Args:
            guess: Combinaison proposée
            solution: Solution correcte

        Returns:
            Tuple (pions_noirs, pions_blancs)
        """
        if len(guess) != len(solution):
            return 0, 0

        black_pegs = 0
        white_pegs = 0

        # Compter les pions noirs (bonne position)
        guess_remaining = []
        solution_remaining = []

        for i in range(len(guess)):
            if guess[i] == solution[i]:
                black_pegs += 1
            else:
                guess_remaining.append(guess[i])
                solution_remaining.append(solution[i])

        # Compter les pions blancs (bonne couleur, mauvaise position)
        for color in guess_remaining:
            if color in solution_remaining:
                white_pegs += 1
                solution_remaining.remove(color)

        return black_pegs, white_pegs

    async def _handle_solution_found(
        self,
        db: AsyncSession,
        game: Game,
        participation: GameParticipation,
        attempt: GameAttempt
    ) -> None:
        """Gère la découverte de la solution"""

        # Marquer le joueur comme gagnant
        participation.is_winner = True
        participation.finished_at = datetime.now(timezone.utc)

        # Calculer le score
        score = calculate_game_score(
            attempts=participation.attempts_made,
            max_attempts=game.max_attempts,
            time_taken=game.duration_minutes * 60 if game.duration_minutes else None,
            quantum_used=participation.quantum_hints_used > 0,
            difficulty=game.difficulty
        )

        participation.score = score

        # Mettre à jour les stats utilisateur
        await self.user_repo.update_user_stats(
            db, participation.player_id, True, score, participation.quantum_hints_used > 0
        )

        # Terminer la partie si mode solo
        if game.game_mode == GameMode.SOLO:
            game.finish_game()

    # === REQUÊTES DE BASE DE DONNÉES ===

    async def _get_game_by_id(self, db: AsyncSession, game_id: UUID) -> Optional[Game]:
        """Récupère une partie par ID"""
        stmt = select(Game).where(Game.id == game_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_game_by_room_code(self, db: AsyncSession, room_code: str) -> Optional[Game]:
        """Récupère une partie par code de room"""
        stmt = select(Game).where(Game.room_code == room_code)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_game_with_participations(self, db: AsyncSession, game_id: UUID) -> Optional[Game]:
        """Récupère une partie avec ses participations"""
        stmt = (
            select(Game)
            .options(selectinload(Game.participations).selectinload(GameParticipation.player))
            .where(Game.id == game_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_game_with_all_relations(self, db: AsyncSession, game_id: UUID) -> Optional[Game]:
        """Récupère une partie avec toutes ses relations"""
        stmt = (
            select(Game)
            .options(
                selectinload(Game.participations).selectinload(GameParticipation.player),
                selectinload(Game.attempts).selectinload(GameAttempt.player)
            )
            .where(Game.id == game_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_participation(
        self,
        db: AsyncSession,
        game_id: UUID,
        player_id: UUID
    ) -> Optional[GameParticipation]:
        """Récupère une participation"""
        stmt = select(GameParticipation).where(
            and_(
                GameParticipation.game_id == game_id,
                GameParticipation.player_id == player_id
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _add_participant(
        self,
        db: AsyncSession,
        game_id: UUID,
        player_id: UUID,
        player_name: Optional[str] = None
    ) -> GameParticipation:
        """Ajoute un participant à une partie"""
        participation = GameParticipation(
            game_id=game_id,
            player_id=player_id,
            player_name=player_name
        )

        db.add(participation)
        await db.commit()
        await db.refresh(participation)

        return participation


# Instance globale du service de jeu
game_service = GameService()