"""
Service de gestion des jeux pour Quantum Mastermind
Logique métier pour les parties, tentatives et scoring
MODIFIÉ: Intégration des fonctionnalités quantiques pour la génération de solution et le calcul d'indices
"""
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import (
    Game, GameParticipation, GameAttempt, GameMode, GameType,
    GameStatus, ParticipationStatus, generate_room_code,
    calculate_game_score, generate_solution
)
from app.repositories.game import GameRepository, GameParticipationRepository, GameAttemptRepository
from app.repositories.user import UserRepository
from app.schemas.game import (
    GameCreate, GameJoin, AttemptCreate, AttemptResult
)
from app.services.quantum import quantum_service  # NOUVEAU: Import du service quantique
from app.utils.exceptions import (
    EntityNotFoundError, GameError, GameNotActiveError,
    GameFullError, ValidationError, AuthorizationError
)


class GameService:
    """Service principal pour la gestion des jeux avec support quantique"""

    def __init__(self):
        self.game_repo = GameRepository()
        self.participation_repo = GameParticipationRepository()
        self.attempt_repo = GameAttemptRepository()
        self.user_repo = UserRepository()

    # === CRÉATION ET GESTION DES PARTIES AVEC SUPPORT QUANTIQUE ===

    async def create_game(
            self,
            db: AsyncSession,
            game_data: GameCreate,
            creator_id: UUID
    ) -> Dict[str, Any]:
        """
        Crée une nouvelle partie avec support quantique
        MODIFIÉ: Utilise la génération quantique si le mode quantique est activé

        Args:
            db: Session de base de données
            game_data: Données de création de la partie
            creator_id: ID du créateur

        Returns:
            Informations de la partie créée

        Raises:
            ValidationError: Si les données sont invalides
            GameError: Si la création échoue
        """
        try:
            # Validation des données AVANT vérification des parties actives
            await self._validate_game_creation(db, game_data, creator_id)

            # Vérification des parties actives
            active_participations = await self.participation_repo.get_user_active_participations(
                db, creator_id
            )

            if active_participations:
                active_games_info = []
                for participation in active_participations:
                    active_games_info.append(f"Room: {participation.game.room_code}")

                games_list = ", ".join(active_games_info)
                raise GameError(
                    f"Vous participez déjà à des parties actives ({games_list}). "
                    "Quittez d'abord ces parties avant d'en créer une nouvelle."
                )

            # NOUVEAU: Déterminer si le mode quantique est activé
            is_quantum_mode = (
                game_data.game_type == GameType.QUANTUM or
                game_data.quantum_enabled
            )

            # Créer la partie
            game = Game(
                game_type=game_data.game_type,
                game_mode=game_data.game_mode,
                difficulty=game_data.difficulty,
                combination_length=getattr(game_data, 'combination_length', 4),
                available_colors=getattr(game_data, 'available_colors', 6),
                max_attempts=game_data.max_attempts,
                time_limit=game_data.time_limit,
                max_players=game_data.max_players,
                is_private=game_data.is_private,
                allow_spectators=game_data.allow_spectators,
                enable_chat=game_data.enable_chat,
                created_by=creator_id,
                room_code=generate_room_code(),
                solution=[],  # Sera généré ci-dessous
                settings=game_data.settings or {}
            )

            # NOUVEAU: Configuration quantique
            if is_quantum_mode:
                game.quantum_settings = {
                    "shots": getattr(game_data, 'quantum_shots', 1024),
                    "max_qubits": 5,
                    "use_quantum_solution": True,
                    "use_quantum_hints": True,
                    "quantum_hint_cost": 50
                }

            # NOUVEAU: Génération de solution (quantique ou classique)
            try:
                if is_quantum_mode:
                    # Génération quantique de la solution
                    solution = await quantum_service.generate_quantum_solution(
                        combination_length=game.combination_length,
                        available_colors=game.available_colors,
                        shots=game.quantum_settings.get("shots", 1024) if game.quantum_settings else 1024
                    )
                    game.solution = solution
                    game.set_quantum_solution_generated({
                        "method": "quantum_hadamard_superposition",
                        "shots": game.quantum_settings.get("shots", 1024),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    print(f"✅ Solution quantique générée: {solution}")
                else:
                    # Génération classique
                    game.solution = generate_solution(
                        game.combination_length,
                        game.available_colors
                    )
                    print(f"✅ Solution classique générée: {game.solution}")

            except Exception as e:
                print(f"⚠️ Erreur génération solution quantique, fallback classique: {e}")
                # Fallback sur la génération classique
                game.solution = generate_solution(
                    game.combination_length,
                    game.available_colors
                )

            # Gestion du mot de passe
            if game_data.password:
                from app.core.security import password_manager
                game.password_hash = password_manager.hash_password(game_data.password)

            # Sauvegarder la partie
            await self.game_repo.create(db, obj_in=game)

            # Créer la participation du créateur
            participation_data = {
                "game_id": game.id,
                "player_id": creator_id,
                "status": ParticipationStatus.ACTIVE
            }
            await self.participation_repo.create(db, obj_in=participation_data)

            await db.commit()

            # Retourner les informations de la partie
            return {
                "game_id": str(game.id),
                "room_code": game.room_code,
                "game_type": game.game_type,
                "game_mode": game.game_mode,
                "difficulty": game.difficulty,
                "max_players": game.max_players,
                "quantum_enabled": is_quantum_mode,
                "quantum_solution": game.quantum_solution,
                "message": f"Partie {'quantique' if is_quantum_mode else 'classique'} créée avec succès!",
                "status": "created",
                "created_at": game.created_at.isoformat()
            }

        except Exception as e:
            await db.rollback()
            if isinstance(e, (ValidationError, GameError)):
                raise
            raise GameError(f"Erreur lors de la création de la partie: {str(e)}")

    async def make_attempt(
            self,
            db: AsyncSession,
            game_id: UUID,
            player_id: UUID,
            attempt_data: AttemptCreate
    ) -> AttemptResult:
        """
        Enregistre une tentative et calcule les indices
        MODIFIÉ: Utilise le calcul quantique si activé

        Args:
            db: Session de base de données
            game_id: ID de la partie
            player_id: ID du joueur
            attempt_data: Données de la tentative

        Returns:
            Résultat de la tentative avec indices calculés

        Raises:
            EntityNotFoundError: Si la partie ou le joueur n'existe pas
            GameNotActiveError: Si la partie n'est pas active
            ValidationError: Si la tentative est invalide
        """
        try:
            # Récupérer la partie avec vérifications
            game = await self.game_repo.get_by_id(db, game_id)
            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            if game.status != GameStatus.ACTIVE:
                raise GameNotActiveError("La partie n'est pas active")

            # Vérifier la participation
            participation = await self.participation_repo.get_player_in_game(
                db, game_id, player_id
            )
            if not participation:
                raise EntityNotFoundError("Vous ne participez pas à cette partie")

            if participation.status != ParticipationStatus.ACTIVE:
                raise GameError("Votre participation n'est pas active")

            # Valider la tentative
            await self._validate_attempt(db, game, participation, attempt_data)

            # Obtenir le numéro de tentative
            attempt_number = participation.attempts_made + 1

            # Calcul des indices (quantique ou classique)
            is_quantum_mode = game.is_quantum_enabled
            exact_matches = 0
            position_matches = 0
            quantum_calculated = False
            quantum_calculation_data = None

            try:
                if is_quantum_mode:
                    # Calcul quantique des indices
                    exact_matches, position_matches = await quantum_service.calculate_quantum_hints(
                        solution=game.solution,
                        attempt=attempt_data.combination,
                        shots=game.quantum_settings.get("shots", 1024) if game.quantum_settings else 1024
                    )
                    quantum_calculated = True
                    quantum_calculation_data = {
                        "method": "quantum_hamming_distance",
                        "shots": game.get_quantum_config().get("shots", 1024),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    print(f"✅ Indices calculés quantiquement: {exact_matches} bien placés, {position_matches} mal placés")
                else:
                    # Calcul classique
                    exact_matches, position_matches = self._calculate_classical_hints(
                        game.solution, attempt_data.combination
                    )
                    print(f"✅ Indices calculés classiquement: {exact_matches} bien placés, {position_matches} mal placés")

            except Exception as e:
                print(f"⚠️ Erreur calcul quantique, fallback classique: {e}")
                # Fallback sur le calcul classique
                exact_matches, position_matches = self._calculate_classical_hints(
                    game.solution, attempt_data.combination
                )

            # Vérifier si c'est la solution correcte
            is_correct = exact_matches == len(game.solution)

            # Créer la tentative
            attempt = GameAttempt(
                game_id=game_id,
                player_id=player_id,
                attempt_number=attempt_number,
                combination=attempt_data.combination,
                exact_matches=exact_matches,
                position_matches=position_matches,
                quantum_calculated=quantum_calculated,
                is_correct=is_correct,
                hint_used=getattr(attempt_data, 'use_quantum_hint', False)
            )

            # NOUVEAU: Ajouter les données quantiques si applicable
            if quantum_calculated and quantum_calculation_data:
                attempt.set_quantum_calculated(quantum_calculation_data)

            # Sauvegarder la tentative
            await self.attempt_repo.create(db, obj_in=attempt)

            # Mettre à jour la participation
            participation.attempts_made += 1

            # NOUVEAU: Mise à jour du score quantique
            if quantum_calculated:
                participation.quantum_score += 5  # Bonus pour utilisation quantique

            # Si c'est correct, marquer la participation comme terminée
            if is_correct:
                participation.status = ParticipationStatus.FINISHED
                participation.finished_at = datetime.now(timezone.utc)
                participation.time_taken = game.duration_seconds

                # Calculer le score final
                if game.duration_seconds:
                    participation.score = calculate_game_score(
                        attempt_number, game.duration_seconds, game.max_attempts or 12
                    )

            # Vérifier si c'est le maximum de tentatives
            elif game.max_attempts and attempt_number >= game.max_attempts:
                participation.status = ParticipationStatus.FINISHED
                participation.finished_at = datetime.now(timezone.utc)

            await self.participation_repo.update(db, db_obj=participation, obj_in={})

            # Vérifier si la partie doit se terminer
            await self._check_game_completion(db, game)

            await db.commit()

            # Calculer les tentatives restantes
            remaining_attempts = None
            if game.max_attempts:
                remaining_attempts = max(0, game.max_attempts - attempt_number)

            return AttemptResult(
                attempt_number=attempt_number,
                combination=attempt_data.combination,
                exact_matches=exact_matches,
                position_matches=position_matches,
                is_correct=is_correct,
                quantum_calculated=quantum_calculated,
                remaining_attempts=remaining_attempts,
                game_finished=participation.status == ParticipationStatus.FINISHED,
                score=participation.score,
                quantum_score=participation.quantum_score
            )

        except Exception as e:
            await db.rollback()
            if isinstance(e, (EntityNotFoundError, GameNotActiveError, ValidationError, GameError)):
                raise
            raise GameError(f"Erreur lors du traitement de la tentative: {str(e)}")

    def _calculate_classical_hints(self, solution: List[int], attempt: List[int]) -> tuple[int, int]:
        """
        Calcul classique des indices (fallback)

        Args:
            solution: La solution secrète
            attempt: La tentative du joueur

        Returns:
            Tuple[int, int]: (bien_places, mal_places)
        """
        if len(solution) != len(attempt):
            return 0, 0

        # Bien placés
        exact_matches = sum(1 for s, a in zip(solution, attempt) if s == a)

        # Compter les correspondances totales
        solution_counts = {}
        attempt_counts = {}

        for color in solution:
            solution_counts[color] = solution_counts.get(color, 0) + 1

        for color in attempt:
            attempt_counts[color] = attempt_counts.get(color, 0) + 1

        total_matches = 0
        for color in solution_counts:
            if color in attempt_counts:
                total_matches += min(solution_counts[color], attempt_counts[color])

        # Mal placés = correspondances totales - bien placés
        wrong_position = total_matches - exact_matches

        return exact_matches, wrong_position

    # === MÉTHODES EXISTANTES (inchangées) ===

    async def create_game_with_auto_leave(
            self,
            db: AsyncSession,
            game_data: GameCreate,
            creator_id: UUID,
            auto_leave: bool = False
    ) -> Dict[str, Any]:
        """
        Crée une partie en quittant automatiquement les parties actives si demandé
        """
        if auto_leave:
            # Quitter toutes les parties actives
            await self.leave_all_active_games(db, creator_id)

        # Créer la nouvelle partie
        return await self.create_game(db, game_data, creator_id)

    async def join_game(
            self,
            db: AsyncSession,
            game_id: UUID,
            player_id: UUID,
            join_data: GameJoin
    ) -> Dict[str, Any]:
        """Rejoint une partie existante"""
        try:
            # Récupérer la partie
            game = await self.game_repo.get_by_id(db, game_id)
            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            # Vérifications
            if game.status not in [GameStatus.WAITING, GameStatus.STARTING]:
                raise GameError("Impossible de rejoindre cette partie")

            if game.is_full:
                raise GameFullError("La partie est pleine")

            # Vérifier si déjà participant
            existing_participation = await self.participation_repo.get_player_in_game(
                db, game_id, player_id
            )
            if existing_participation:
                raise GameError("Vous participez déjà à cette partie")

            # Vérifier le mot de passe si nécessaire
            if game.is_private and game.password_hash:
                if not join_data.password:
                    raise ValidationError("Mot de passe requis")

                from app.core.security import password_manager
                if not password_manager.verify_password(join_data.password, game.password_hash):
                    raise ValidationError("Mot de passe incorrect")

            # Créer la participation
            participation_data = {
                "game_id": game_id,
                "player_id": player_id,
                "status": ParticipationStatus.ACTIVE
            }
            participation = await self.participation_repo.create(db, obj_in=participation_data)

            # Démarrer automatiquement si conditions remplies
            if game.can_start and game.game_mode != GameMode.SINGLE:
                game.status = GameStatus.ACTIVE
                game.started_at = datetime.now(timezone.utc)
                await self.game_repo.update(db, db_obj=game, obj_in={})

            await db.commit()

            # Je vais corriger la partie où on récupère l'objet participation
            return {
                "message": "Partie rejointe avec succès",
                "game_id": str(game_id),
                "room_code": game.room_code,
                "status": game.status,
                "quantum_enabled": game.is_quantum_enabled,
                "current_players": len([p for p in game.participations if p.status != ParticipationStatus.DISCONNECTED]) + 1
            }

        except Exception as e:
            await db.rollback()
            if isinstance(e, (EntityNotFoundError, GameError, GameFullError, ValidationError)):
                raise
            raise GameError(f"Erreur lors de la participation: {str(e)}")

    async def leave_all_active_games(self, db: AsyncSession, user_id: UUID) -> Dict[str, Any]:
        """Quitte toutes les parties actives d'un utilisateur"""
        try:
            # Récupérer toutes les participations actives
            active_participations = await self.participation_repo.get_user_active_participations(
                db, user_id
            )

            if not active_participations:
                return {
                    "message": "Aucune partie active trouvée",
                    "games_left": 0
                }

            games_left = []

            for participation in active_participations:
                # Mettre le statut à disconnected
                participation.status = ParticipationStatus.DISCONNECTED
                await self.participation_repo.update(db, db_obj=participation, obj_in={})

                game = participation.game
                games_left.append({
                    "game_id": str(game.id),
                    "room_code": game.room_code,
                    "game_type": game.game_type
                })

                # Vérifier si la partie doit être annulée
                await self._check_game_completion(db, game)

            await db.commit()

            return {
                "message": f"Vous avez quitté {len(games_left)} partie(s)",
                "games_left": len(games_left),
                "games": games_left
            }

        except Exception as e:
            await db.rollback()
            raise GameError(f"Erreur lors de l'abandon des parties: {str(e)}")

    async def start_game(self, db: AsyncSession, game_id: UUID, user_id: UUID) -> Dict[str, Any]:
        """Démarre une partie"""
        try:
            game = await self.game_repo.get_by_id(db, game_id)
            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            if game.created_by != user_id:
                raise AuthorizationError("Seul le créateur peut démarrer la partie")

            if game.status != GameStatus.WAITING:
                raise GameError("La partie ne peut pas être démarrée")

            if not game.can_start:
                raise GameError("Conditions de démarrage non remplies")

            game.status = GameStatus.ACTIVE
            game.started_at = datetime.now(timezone.utc)
            await self.game_repo.update(db, db_obj=game, obj_in={})

            await db.commit()

            return {
                "message": "Partie démarrée avec succès",
                "game_id": str(game_id),
                "started_at": game.started_at.isoformat(),
                "quantum_enabled": game.is_quantum_enabled
            }

        except Exception as e:
            await db.rollback()
            if isinstance(e, (EntityNotFoundError, AuthorizationError, GameError)):
                raise
            raise GameError(f"Erreur lors du démarrage: {str(e)}")

    # === MÉTHODES PRIVÉES D'AIDE ===

    async def _validate_game_creation(self, db: AsyncSession, game_data: GameCreate, creator_id: UUID):
        """Valide les données de création d'une partie"""
        # Vérifier que l'utilisateur existe
        user = await self.user_repo.get_by_id(db, creator_id)
        if not user:
            raise EntityNotFoundError("Utilisateur non trouvé")

        # Validation des paramètres de jeu
        if game_data.max_players < 1 or game_data.max_players > 8:
            raise ValidationError("Le nombre de joueurs doit être entre 1 et 8")

        if game_data.max_attempts and (game_data.max_attempts < 1 or game_data.max_attempts > 50):
            raise ValidationError("Le nombre de tentatives doit être entre 1 et 50")

        if game_data.time_limit and (game_data.time_limit < 60 or game_data.time_limit > 3600):
            raise ValidationError("La limite de temps doit être entre 1 minute et 1 heure")

    async def _validate_attempt(self, db: AsyncSession, game: Game, participation: GameParticipation, attempt_data: AttemptCreate):
        """Valide une tentative"""
        # Vérifier la longueur de la combinaison
        if len(attempt_data.combination) != game.combination_length:
            raise ValidationError(f"La combinaison doit contenir {game.combination_length} couleurs")

        # Vérifier les couleurs valides
        for color in attempt_data.combination:
            if color < 1 or color > game.available_colors:
                raise ValidationError(f"Les couleurs doivent être entre 1 et {game.available_colors}")

        # Vérifier le nombre de tentatives
        if game.max_attempts and participation.attempts_made >= game.max_attempts:
            raise ValidationError("Nombre maximum de tentatives atteint")

    async def _check_game_completion(self, db: AsyncSession, game: Game):
        """Vérifie si une partie doit se terminer"""
        if game.status != GameStatus.ACTIVE:
            return

        # Récupérer toutes les participations
        participations = await self.participation_repo.get_game_players(db, game.id)

        # Vérifier si tous les joueurs ont terminé ou sont déconnectés
        active_players = [p for p in participations if p.status == ParticipationStatus.ACTIVE]

        if not active_players:
            # Plus de joueurs actifs, terminer la partie
            game.status = GameStatus.FINISHED
            game.finished_at = datetime.now(timezone.utc)
            await self.game_repo.update(db, db_obj=game, obj_in={})

    # === NOUVELLES MÉTHODES UTILITAIRES QUANTIQUES ===

    async def get_quantum_game_info(self, db: AsyncSession, game_id: UUID) -> Dict[str, Any]:
        """Récupère les informations quantiques spécifiques d'une partie"""
        game = await self.game_repo.get_by_id(db, game_id)
        if not game:
            raise EntityNotFoundError("Partie non trouvée")

        quantum_info = {
            "is_quantum_enabled": game.is_quantum_enabled,
            "quantum_solution": game.quantum_solution,
            "quantum_settings": game.quantum_settings or {},
            "quantum_backend_status": await quantum_service.test_quantum_backend()
        }

        if game.is_quantum_enabled:
            # Statistiques quantiques des tentatives - TODO: implémenter get_by_game_id
            try:
                # Temporaire : utiliser une requête directe
                from sqlalchemy import select
                attempts_query = select(GameAttempt).where(GameAttempt.game_id == game_id)
                attempts_result = await db.execute(attempts_query)
                attempts = attempts_result.scalars().all()
                quantum_attempts = [a for a in attempts if a.quantum_calculated]
            except Exception:
                attempts = []
                quantum_attempts = []

            quantum_info.update({
                "total_attempts": len(attempts),
                "quantum_attempts": len(quantum_attempts),
                "quantum_usage_ratio": len(quantum_attempts) / len(attempts) if attempts else 0
            })

        return quantum_info


# Instance globale du service de jeu
game_service = GameService()