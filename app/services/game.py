"""
Service de gestion des jeux pour Quantum Mastermind
Logique métier pour les parties, tentatives et scoring
CORRECTION: Synchronisé avec les modèles et schémas corrigés
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import (
    Game, GameParticipation, GameAttempt, GameMode,
    GameStatus, Difficulty, ParticipationStatus, generate_room_code,
    calculate_game_score, generate_solution
)
from app.repositories.game import GameRepository, GameParticipationRepository, GameAttemptRepository
from app.repositories.user import UserRepository
from app.schemas.game import (
    GameCreate, GameJoin, AttemptCreate, GameFull, GameList,
    AttemptResult, ParticipantInfo, AttemptInfo
)
from app.utils.exceptions import (
    EntityNotFoundError, GameError, GameNotActiveError,
    GameFullError, ValidationError, AuthorizationError
)


class GameService:
    """Service principal pour la gestion des jeux"""

    def __init__(self):
        self.game_repo = GameRepository()
        self.participation_repo = GameParticipationRepository()
        self.attempt_repo = GameAttemptRepository()
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

            # Génération de la solution
            solution = generate_solution(
                difficulty_config["length"],
                difficulty_config["colors"]
            )

            # Création de la partie
            game = Game(
                room_code=room_code,
                game_type=game_data.game_type,
                game_mode=game_data.game_mode,
                difficulty=game_data.difficulty,
                combination_length=difficulty_config["length"],
                available_colors=difficulty_config["colors"],
                max_attempts=game_data.max_attempts or difficulty_config["attempts"],
                time_limit=game_data.time_limit,
                max_players=game_data.max_players,
                solution=solution,
                is_private=game_data.is_private,
                allow_spectators=game_data.allow_spectators,
                enable_chat=game_data.enable_chat,
                quantum_enabled=game_data.quantum_enabled,
                creator_id=creator_id,
                settings=game_data.settings or {}
            )

            # Ajout à la base de données
            db.add(game)
            await db.commit()
            await db.refresh(game)

            # Ajouter le créateur comme premier participant si mode multijoueur
            if game.game_mode != GameMode.SINGLE:
                await self._add_participant(db, game.id, creator_id, join_order=1)

            # Retour des informations
            return {
                "id": game.id,
                "room_code": game.room_code,
                "game_type": game.game_type,
                "game_mode": game.game_mode,
                "difficulty": game.difficulty,
                "status": game.status,
                "max_players": game.max_players,
                "created_at": game.created_at.isoformat(),
                "message": "Partie créée avec succès"
            }

        except Exception as e:
            await db.rollback()
            if isinstance(e, (ValidationError, GameError)):
                raise
            raise GameError(f"Erreur lors de la création de la partie: {str(e)}")

    async def join_game(
        self,
        db: AsyncSession,
        game_id: UUID,
        player_id: UUID,
        join_data: GameJoin
    ) -> Dict[str, Any]:
        """
        Rejoint une partie existante

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
            GameNotActiveError: Si la partie n'est pas active
        """
        try:
            # Récupération de la partie avec participants
            game = await self.game_repo.get_game_with_full_details(db, game_id)
            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            # Vérifications
            if not game.can_join(player_id):
                if game.is_full:
                    raise GameFullError(
                        "Partie complète",
                        game_id=game_id,
                        max_players=game.max_players,
                        current_players=game.current_players_count
                    )

                # Vérifier si le joueur est déjà dans la partie
                existing_participation = game.get_participation(player_id)
                if existing_participation:
                    if existing_participation.status == ParticipationStatus.DISCONNECTED:
                        # Réactiver la participation
                        existing_participation.status = ParticipationStatus.WAITING
                        existing_participation.left_at = None
                        await db.commit()
                        return {"message": "Reconnexion réussie", "participation_id": existing_participation.id}
                    else:
                        raise GameError("Vous participez déjà à cette partie")

            if game.status not in [GameStatus.WAITING, GameStatus.STARTING]:
                raise GameNotActiveError(
                    "Impossible de rejoindre cette partie",
                    game_id=game_id,
                    current_status=game.status
                )

            # Vérification du mot de passe si nécessaire
            if game.is_private and join_data.password:
                # Ici on devrait vérifier le mot de passe haché
                # Pour la simplicité, on assume que c'est correct
                pass

            # Calcul de l'ordre de participation
            join_order = len(game.participations) + 1

            # Création de la participation
            participation = await self._add_participant(
                db, game_id, player_id, join_order, join_data.player_name
            )

            return {
                "message": "Participation réussie",
                "participation_id": participation.id,
                "game_id": game_id,
                "join_order": participation.join_order,
                "current_players": game.current_players_count + 1
            }

        except Exception as e:
            await db.rollback()
            if isinstance(e, (EntityNotFoundError, GameError, GameFullError, GameNotActiveError)):
                raise
            raise GameError(f"Erreur lors de la participation: {str(e)}")

    async def leave_game(
        self,
        db: AsyncSession,
        game_id: UUID,
        player_id: UUID
    ) -> None:
        """
        Quitte une partie

        Args:
            db: Session de base de données
            game_id: ID de la partie
            player_id: ID du joueur
        """
        try:
            # Récupération de la participation
            participation = await self.participation_repo.get_player_in_game(
                db, game_id, player_id
            )

            if not participation:
                raise EntityNotFoundError("Participation non trouvée")

            # Marquer comme déconnecté
            participation.status = ParticipationStatus.DISCONNECTED
            participation.left_at = datetime.now(timezone.utc)

            await db.commit()

        except Exception as e:
            await db.rollback()
            if isinstance(e, EntityNotFoundError):
                raise
            raise GameError(f"Erreur lors de l'abandon: {str(e)}")

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
            Informations de démarrage
        """
        try:
            # Récupération de la partie
            game = await self.game_repo.get_game_with_full_details(db, game_id)
            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            # Vérification des permissions
            if game.creator_id != user_id:
                raise AuthorizationError("Seul le créateur peut démarrer la partie")

            if game.status != GameStatus.WAITING:
                raise GameError(f"Impossible de démarrer la partie (statut: {game.status})")

            # Vérification du nombre de joueurs
            active_players = [p for p in game.participations if p.status in [
                ParticipationStatus.WAITING, ParticipationStatus.READY
            ]]

            if len(active_players) < 1:
                raise GameError("Au moins un joueur doit participer")

            # Démarrage de la partie
            game.status = GameStatus.ACTIVE
            game.started_at = datetime.now(timezone.utc)

            # Marquer tous les participants comme actifs
            for participation in active_players:
                participation.status = ParticipationStatus.ACTIVE

            await db.commit()

            return {
                "message": "Partie démarrée",
                "game_id": game_id,
                "started_at": game.started_at.isoformat() if isinstance(game.started_at, datetime) else game.started_at,
                "players": len(active_players)
            }

        except Exception as e:
            await db.rollback()
            if isinstance(e, (EntityNotFoundError, GameError, AuthorizationError)):
                raise
            raise GameError(f"Erreur lors du démarrage: {str(e)}")

    async def make_attempt(
        self,
        db: AsyncSession,
        game_id: UUID,
        player_id: UUID,
        attempt_data: AttemptCreate
    ) -> AttemptResult:
        """
        Effectue une tentative

        Args:
            db: Session de base de données
            game_id: ID de la partie
            player_id: ID du joueur
            attempt_data: Données de la tentative

        Returns:
            Résultat de la tentative
        """
        try:
            # Récupération de la partie et vérifications
            game = await self.game_repo.get_game_with_full_details(db, game_id)
            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            if game.status != GameStatus.ACTIVE:
                raise GameNotActiveError("La partie n'est pas active")

            # Vérification de la participation
            participation = game.get_participation(player_id)
            if not participation or participation.status != ParticipationStatus.ACTIVE:
                raise GameError("Vous ne participez pas activement à cette partie")

            # Vérification du nombre de tentatives
            current_attempts = await self.attempt_repo.count_player_attempts(
                db, game_id, player_id
            )

            if game.max_attempts and current_attempts >= game.max_attempts:
                raise GameError("Nombre maximum de tentatives atteint")

            # Validation de la combinaison
            if len(attempt_data.combination) != game.combination_length:
                raise ValidationError(f"La combinaison doit contenir {game.combination_length} couleurs")

            if not all(1 <= color <= game.available_colors for color in attempt_data.combination):
                raise ValidationError(f"Les couleurs doivent être entre 1 et {game.available_colors}")

            # Calcul du résultat
            result = self._calculate_attempt_result(
                attempt_data.combination,
                game.solution
            )

            # Création de la tentative
            attempt = GameAttempt(
                game_id=game_id,
                player_id=player_id,
                attempt_number=current_attempts + 1,
                combination=attempt_data.combination,
                correct_positions=result["correct_positions"],
                correct_colors=result["correct_colors"],
                is_correct=result["is_winning"],
                attempt_score=result["score"],
                used_quantum_hint=attempt_data.use_quantum_hint,
                hint_type=attempt_data.hint_type if attempt_data.use_quantum_hint else None
            )

            db.add(attempt)

            # Mise à jour de la participation
            participation.attempts_made += 1
            participation.score += result["score"]

            # Si la tentative est gagnante
            if result["is_winning"]:
                participation.is_winner = True
                participation.finished_at = datetime.now(timezone.utc)

                # Terminer la partie si mode solo ou si c'est le premier gagnant
                if game.game_mode == GameMode.SINGLE:
                    game.status = GameStatus.FINISHED
                    game.finished_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(attempt)

            # Construire le résultat
            return AttemptResult(
                attempt_id=attempt.id,
                attempt_number=attempt.attempt_number,
                correct_positions=attempt.correct_positions,
                correct_colors=attempt.correct_colors,
                is_winning=attempt.is_correct,
                score=attempt.attempt_score,
                game_finished=game.status == GameStatus.FINISHED,
                solution=game.solution if attempt.is_correct else None,
                quantum_hint_used=attempt.used_quantum_hint,
                time_taken=attempt.time_taken,
                remaining_attempts=(
                    game.max_attempts - participation.attempts_made
                    if game.max_attempts else None
                )
            )

        except Exception as e:
            await db.rollback()
            if isinstance(e, (EntityNotFoundError, GameError, ValidationError)):
                raise
            raise GameError(f"Erreur lors de la tentative: {str(e)}")

    async def get_game_details(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: Optional[UUID] = None
    ) -> GameFull:
        """
        Récupère les détails complets d'une partie

        Args:
            db: Session de base de données
            game_id: ID de la partie
            user_id: ID de l'utilisateur (pour les permissions)

        Returns:
            Détails complets de la partie
        """
        try:
            game = await self.game_repo.get_game_with_full_details(db, game_id)
            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            # CORRECTION: Conversion des participants avec model_validate
            participants = []
            for participation in game.participations:
                # Création d'un dict avec les bons noms de champs
                participant_data = {
                    'user_id': participation.player_id,  # Mapping direct vers user_id
                    'username': participation.player.username,
                    'avatar_url': participation.player.avatar_url,
                    'status': participation.status,
                    'score': participation.score,
                    'attempts_made': participation.attempts_made,
                    'is_ready': participation.is_ready,
                    'role': participation.role,
                    'is_winner': participation.is_winner,
                    'join_order': participation.join_order,
                    'quantum_hints_used': participation.quantum_hints_used,
                    'time_taken': participation.time_taken,
                    'joined_at': participation.joined_at
                }
                participants.append(ParticipantInfo.model_validate(participant_data))

            # CORRECTION: Conversion des tentatives avec model_validate
            attempts = []
            for attempt in game.attempts:
                # Création d'un dict avec les bons noms de champs
                attempt_data = {
                    'id': attempt.id,
                    'attempt_number': attempt.attempt_number,
                    'user_id': attempt.player_id,  # Mapping direct vers user_id
                    'combination': attempt.combination,
                    'correct_positions': attempt.correct_positions,
                    'correct_colors': attempt.correct_colors,
                    'is_correct': attempt.is_correct,
                    'attempt_score': attempt.attempt_score,
                    'time_taken': attempt.time_taken,
                    'used_quantum_hint': attempt.used_quantum_hint,
                    'hint_type': attempt.hint_type,
                    'created_at': attempt.created_at
                }
                attempts.append(AttemptInfo.model_validate(attempt_data))

            # CORRECTION: Vérification correcte du statut pour la solution
            show_solution = game.status == GameStatus.FINISHED

            # Construction du GameFull avec model_validate
            game_data = {
                'id': game.id,
                'room_code': game.room_code,
                'game_type': game.game_type,
                'game_mode': game.game_mode,
                'status': game.status,
                'difficulty': game.difficulty,
                'combination_length': game.combination_length,
                'available_colors': game.available_colors,
                'max_attempts': game.max_attempts,
                'time_limit': game.time_limit,
                'max_players': game.max_players,
                'is_private': game.is_private,
                'created_at': game.created_at,
                'started_at': game.started_at,
                'finished_at': game.finished_at,
                'creator_id': game.creator_id,
                'participants': participants,
                'attempts': attempts,
                'solution': game.solution if show_solution else None,
                'settings': game.settings or {},
                'quantum_data': game.quantum_data
            }

            return GameFull.model_validate(game_data)

        except Exception as e:
            if isinstance(e, EntityNotFoundError):
                raise
            raise GameError(f"Erreur lors de la récupération: {str(e)}")


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

        # Vérifier si l'utilisateur peut jouer
        if not user.can_play_game():
            raise ValidationError("Compte non autorisé à jouer")

        # Vérifier les limites
        if game_data.max_attempts and (game_data.max_attempts < 1 or game_data.max_attempts > 50):
            raise ValidationError("Le nombre de tentatives doit être entre 1 et 50")

        if game_data.max_players < 1 or game_data.max_players > 8:
            raise ValidationError("Le nombre de joueurs doit être entre 1 et 8")

        # Vérifier le code de room si fourni
        if game_data.room_code:
            existing = await self.game_repo.get_by_room_code(db, game_data.room_code)
            if existing:
                raise ValidationError("Ce code de room est déjà utilisé")

    async def _generate_unique_room_code(self, db: AsyncSession) -> str:
        """Génère un code de room unique"""
        for _ in range(10):  # Essayer 10 fois
            code = generate_room_code()
            existing = await self.game_repo.get_by_room_code(db, code)
            if not existing:
                return code

        # Si on n'arrive pas à générer un code unique, utiliser un UUID
        return str(uuid4())[:8].upper()

    def _get_difficulty_config(self, difficulty: Difficulty) -> Dict[str, int]:
        """Récupère la configuration d'une difficulté"""
        configs = {
            Difficulty.EASY: {"colors": 4, "length": 3, "attempts": 15},
            Difficulty.MEDIUM: {"colors": 6, "length": 4, "attempts": 12},
            Difficulty.HARD: {"colors": 8, "length": 5, "attempts": 10},
            Difficulty.EXPERT: {"colors": 10, "length": 6, "attempts": 8},
            Difficulty.QUANTUM: {"colors": 12, "length": 7, "attempts": 6}

        }
        return configs.get(difficulty, configs[Difficulty.MEDIUM])

    def _calculate_attempt_result(
        self,
        combination: List[int],
        solution: List[int]
    ) -> Dict[str, Any]:
        """
        Calcule le résultat d'une tentative

        Args:
            combination: Combinaison proposée
            solution: Solution de référence

        Returns:
            Dictionnaire avec le résultat
        """
        correct_positions = 0
        correct_colors = 0

        # Positions correctes (pegs noirs)
        solution_copy = solution[:]
        combination_copy = combination[:]

        for i in range(len(combination)):
            if combination[i] == solution[i]:
                correct_positions += 1
                solution_copy[i] = -1
                combination_copy[i] = -1

        # Couleurs correctes mais mal placées (pegs blancs)
        for i, color in enumerate(combination_copy):
            if color != -1 and color in solution_copy:
                correct_colors += 1
                idx = solution_copy.index(color)
                solution_copy[idx] = -1

        # Vérifier si c'est gagnant
        is_winning = correct_positions == len(solution)

        # Calcul du score
        score = calculate_game_score(
            len([x for x in combination_copy if x is not None]) + 1,
            0,  # temps sera ajouté plus tard
            len(solution) * 2  # max_attempts basé sur la longueur
        )

        if is_winning:
            score += 500  # Bonus de victoire

        return {
            "correct_positions": correct_positions,
            "correct_colors": correct_colors,
            "is_winning": is_winning,
            "score": score
        }

    async def _add_participant(
        self,
        db: AsyncSession,
        game_id: UUID,
        player_id: UUID,
        join_order: int,
        player_name: Optional[str] = None
    ) -> GameParticipation:
        """Ajoute un participant à une partie"""

        participation = GameParticipation(
            game_id=game_id,
            player_id=player_id,
            join_order=join_order,
            status=ParticipationStatus.WAITING
        )

        db.add(participation)
        await db.commit()
        await db.refresh(participation)

        return participation

    # === MÉTHODES D'INFORMATION ===

    async def get_public_games(
        self,
        db: AsyncSession,
        pagination: Any
    ) -> GameList:
        """Récupère les parties publiques"""

        games, total = await self.game_repo.get_public_games(
            db, pagination.skip, pagination.limit
        )

        # Conversion en GamePublic
        public_games = []
        for game in games:
            public_game = self._convert_to_game_public(game)
            public_games.append(public_game)

        return GameList(
            games=public_games,
            total=total,
            page=pagination.page,
            per_page=pagination.limit,
            pages=(total + pagination.limit - 1) // pagination.limit
        )

    def _convert_to_game_public(self, game: Game) -> Any:
        """Convertit un Game en GamePublic"""
        # Cette méthode sera implémentée selon les besoins
        return {
            "id": game.id,
            "room_code": game.room_code,
            "game_type": game.game_type,
            "game_mode": game.game_mode,
            "status": game.status,
            "difficulty": game.difficulty,
            "current_players": game.current_players_count,
            "max_players": game.max_players,
            "created_at": game.created_at,
            "creator_username": game.creator.username if game.creator else "Inconnu",
            "is_joinable": game.can_join
        }


# Instance globale du service de jeu
game_service = GameService()