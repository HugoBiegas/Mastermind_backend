"""
Service de gestion des jeux pour Quantum Mastermind
Logique métier pour les parties, tentatives et scoring
 Version fonctionnelle avec les vrais Enums
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

#  Import des vrais Enums depuis models
from app.models.game import (
    Game, GameParticipation, GameAttempt,
    GameType, GameMode, GameStatus, ParticipationStatus,
    generate_room_code, calculate_game_score
)
from app.repositories.game import GameRepository, GameParticipationRepository, GameAttemptRepository
from app.repositories.user import UserRepository
from app.schemas.game import (
    GameCreate, GameJoin, AttemptCreate, AttemptResult
)
from app.services.quantum import quantum_service
from app.utils.exceptions import (
    EntityNotFoundError, GameError, GameNotActiveError,
    GameFullError, ValidationError, AuthorizationError, logger
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
         Gestion correcte des valeurs None
        """
        try:
            # VÉRIFICATION: Empêcher la création si l'utilisateur est déjà dans une partie active
            active_participations = await self.participation_repo.get_user_active_participations(
                db, creator_id
            )

            if active_participations:
                participation = active_participations[0]
                active_game = participation.game
                raise GameError(
                    f"Vous participez déjà à une partie active (Room: {active_game.room_code}). "
                    "Quittez d'abord cette partie avant d'en créer une nouvelle."
                )

            #  Récupérer la configuration de difficulté
            difficulty_config = self._get_difficulty_config(game_data.difficulty)

            #  Assigner les valeurs finales d'abord
            combination_length = game_data.combination_length if game_data.combination_length is not None else \
            difficulty_config["length"]
            available_colors = game_data.available_colors if game_data.available_colors is not None else \
            difficulty_config["colors"]
            max_attempts = game_data.max_attempts if game_data.max_attempts is not None else difficulty_config[
                "attempts"]

            #  Gestion du quantum_enabled selon le game_type
            quantum_enabled = game_data.quantum_enabled
            if game_data.game_type == GameType.QUANTUM or (
                    hasattr(game_data.game_type, 'value') and game_data.game_type.value == 'quantum'):
                quantum_enabled = True

            #  Validation après assignation des valeurs
            if combination_length < 2 or combination_length > 8:
                raise ValidationError("La longueur de combinaison doit être entre 2 et 8")

            if available_colors < 3 or available_colors > 15:
                raise ValidationError("Le nombre de couleurs doit être entre 3 et 15")

            if max_attempts is not None and (max_attempts < 1 or max_attempts > 50):
                raise ValidationError("Le nombre de tentatives doit être entre 1 et 50")

            if game_data.max_players < 1 or game_data.max_players > 8:
                raise ValidationError("Le nombre de joueurs doit être entre 1 et 8")

            # Génération du code de room unique
            room_code = await self._generate_unique_room_code(db)

            # Génération de la solution avec les valeurs finales en quantique si nésésére
            if quantum_enabled:
                solution = await quantum_service.generate_quantum_solution(combination_length, available_colors,1024)
            else:
                solution = self._generate_solution(combination_length, available_colors)

            #  Création de la partie avec les bonnes valeurs
            game = Game(
                room_code=room_code,
                game_type=str(game_data.game_type.value) if hasattr(game_data.game_type, 'value') else str(game_data.game_type),
                game_mode=game_data.game_mode.value if hasattr(game_data.game_mode, 'value') else game_data.game_mode,
                difficulty=game_data.difficulty.value if hasattr(game_data.difficulty,
                                                                 'value') else game_data.difficulty,
                combination_length=combination_length,
                available_colors=available_colors,
                max_attempts=max_attempts,
                time_limit=game_data.time_limit,
                max_players=game_data.max_players,
                solution=solution,
                is_private=game_data.is_private,
                allow_spectators=game_data.allow_spectators,
                enable_chat=game_data.enable_chat,
                quantum_enabled=quantum_enabled,
                creator_id=creator_id,
                settings=game_data.settings or {}
            )

            # Ajout à la base de données
            db.add(game)
            await db.commit()
            await db.refresh(game)

            # Ajouter TOUJOURS le créateur comme participant
            await self._add_participant(db, game.id, creator_id, join_order=1)

            #  Récupérer l'utilisateur créateur pour le nom
            creator = await self.user_repo.get_by_id(db, creator_id)
            creator_username = creator.username if creator else "Inconnu"

            # Retour des informations COMPLÈTES selon le schéma attendu
            return {
                # Identification
                "id": str(game.id),
                "room_code": game.room_code,

                # Configuration de base
                "game_type": game.game_type,
                "game_mode": game.game_mode,
                "difficulty": game.difficulty,
                "status": game.status,
                "quantum_enabled": game.quantum_enabled,

                # Paramètres de jeu ( utiliser les valeurs finales)
                "combination_length": combination_length,
                "available_colors": available_colors,
                "max_players": game.max_players,

                # Configuration avancée
                "is_private": game.is_private,
                "allow_spectators": game.allow_spectators,
                "enable_chat": game.enable_chat,

                # Créateur
                "creator_id": str(game.creator_id),
                "creator_username": creator_username,

                # Timestamps
                "created_at": game.created_at.isoformat(),
                "started_at": game.started_at.isoformat() if game.started_at else None,
                "finished_at": game.finished_at.isoformat() if game.finished_at else None,

                # Statistiques
                "current_players": 1,  # Le créateur vient d'être ajouté

                # Message de succès
                "message": "Partie créée avec succès - vous avez été automatiquement ajouté à la partie"
            }

        except Exception as e:
            await db.rollback()
            if isinstance(e, (ValidationError, GameError)):
                raise
            raise GameError(f"Erreur lors de la création de la partie: {str(e)}")

    async def create_game_with_auto_leave(
            self,
            db: AsyncSession,
            game_data: GameCreate,
            creator_id: UUID,
            auto_leave: bool = False
    ) -> Dict[str, Any]:
        """
        Crée une partie en quittant automatiquement les parties actives si demandé
        NOUVELLE MÉTHODE pour gérer auto_leave
        """
        if auto_leave:
            # Quitter toutes les parties actives
            await self.leave_all_active_games(db, creator_id)

        # Créer la nouvelle partie
        return await self.create_game(db, game_data, creator_id)

    async def leave_all_active_games(
            self,
            db: AsyncSession,
            player_id: UUID
    ) -> Dict[str, Any]:
        """Quitte toutes les parties actives"""
        try:
            active_participations = await self.participation_repo.get_user_active_participations(
                db, player_id
            )

            left_games = []
            for participation in active_participations:
                participation.status = ParticipationStatus.DISCONNECTED.value
                participation.left_at = datetime.now(timezone.utc)
                await self.participation_repo.update(db, db_obj=participation, obj_in={})
                left_games.append(participation.game.room_code)

            await db.commit()

            return {
                "message": f"Quitté {len(left_games)} partie(s) active(s)",
                "left_games": left_games
            }

        except Exception as e:
            await db.rollback()
            raise GameError(f"Erreur lors de l'abandon des parties: {str(e)}")

    async def join_game(
            self,
            db: AsyncSession,
            game_id: UUID,
            player_id: UUID,
            join_data: GameJoin
    ) -> Dict[str, Any]:
        """
        Rejoint une partie existante
         Utilisation des valeurs d'Enums
        """
        try:
            # NOUVELLE VÉRIFICATION : Empêcher de rejoindre si l'utilisateur est déjà dans une partie active
            active_participations = await self.participation_repo.get_user_active_participations(
                db, player_id
            )

            if active_participations:
                # Vérifier si c'est la même partie (reconnexion) ou une autre partie
                current_game_participation = None
                other_game_participations = []

                for participation in active_participations:
                    if participation.game_id == game_id:
                        current_game_participation = participation
                    else:
                        other_game_participations.append(participation)

                # Si l'utilisateur est dans une AUTRE partie, l'empêcher de rejoindre
                if other_game_participations:
                    other_game = other_game_participations[0].game
                    raise GameError(
                        f"Vous participez déjà à une autre partie (Room: {other_game.room_code}). "
                        "Quittez d'abord cette partie avant d'en rejoindre une nouvelle."
                    )

                # Si c'est la même partie et que le joueur était déconnecté, le reconnecter
                if current_game_participation and current_game_participation.status == ParticipationStatus.DISCONNECTED.value:
                    current_game_participation.status = ParticipationStatus.WAITING.value
                    current_game_participation.left_at = None
                    await db.commit()
                    return {
                        "message": "Reconnexion réussie à la partie",
                        "participation_id": str(current_game_participation.id),
                        "game_id": str(game_id),
                        "join_order": current_game_participation.join_order
                    }

                # Si c'est la même partie et que le joueur est déjà actif
                if current_game_participation:
                    raise GameError("Vous participez déjà à cette partie")

            # Récupération de la partie avec participants
            game = await self.game_repo.get_game_with_full_details(db, game_id)
            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            #  Vérifications avec les valeurs d'Enums
            if game.is_full():
                raise GameFullError(
                    "Partie complète",
                    game_id=game_id,
                    max_players=game.max_players,
                    current_players=game.get_current_player_count()
                )

            if game.status not in [GameStatus.WAITING.value, GameStatus.STARTING.value]:
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
                "message": "Vous avez rejoint la partie avec succès",
                "participation_id": str(participation.id),
                "game_id": str(game_id),
                "join_order": participation.join_order,
                "current_players": game.get_current_player_count() + 1
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
    ) -> Dict[str, Any]:
        """
        Quitte une partie
         Retour d'un Dict
        """
        try:
            # Récupération de la participation
            participation = await self.participation_repo.get_player_in_game(
                db, game_id, player_id
            )

            if not participation:
                # AMÉLIORATION : Message d'erreur plus explicite
                # Vérifier si la partie existe
                game = await self.game_repo.get_by_id(db, game_id)
                if not game:
                    raise EntityNotFoundError("Partie non trouvée")
                else:
                    raise EntityNotFoundError(
                        "Vous ne participez pas à cette partie. "
                        "Impossible de quitter une partie à laquelle vous n'avez pas rejoint."
                    )

            # Vérifier si le joueur est déjà déconnecté
            if participation.status == ParticipationStatus.DISCONNECTED.value:
                raise GameError("Vous avez déjà quitté cette partie")

            # Marquer comme déconnecté
            participation.status = ParticipationStatus.DISCONNECTED.value
            participation.left_at = datetime.now(timezone.utc)

            await db.commit()

            # AMÉLIORATION : Log de l'action pour audit
            print(f"Joueur {player_id} a quitté la partie {game_id} à {participation.left_at}")

            return {"message": "Partie quittée avec succès"}

        except Exception as e:
            await db.rollback()
            if isinstance(e, (EntityNotFoundError, GameError)):
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
         Utilisation des valeurs d'Enums
        """
        try:
            # Récupération de la partie
            game = await self.game_repo.get_game_with_full_details(db, game_id)
            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            # Vérification des permissions
            if game.creator_id != user_id:
                raise AuthorizationError("Seul le créateur peut démarrer la partie")

            if game.status != GameStatus.WAITING.value:
                raise GameError(f"Impossible de démarrer la partie (statut: {game.status})")

            # Vérification du nombre de joueurs
            active_players = [p for p in game.participations if p.status in [
                ParticipationStatus.WAITING.value, ParticipationStatus.READY.value
            ]]

            if len(active_players) < 1:
                raise GameError("Au moins un joueur doit participer")

            # Démarrage de la partie
            game.status = GameStatus.ACTIVE.value
            game.started_at = datetime.now(timezone.utc)

            # Marquer tous les participants comme actifs
            for participation in active_players:
                participation.status = ParticipationStatus.ACTIVE.value

            await db.commit()

            return {
                "message": "Partie démarrée",
                "game_id": str(game_id),
                "started_at": game.started_at.isoformat() if isinstance(game.started_at, datetime) else None,
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
        Effectue une tentative avec gestion des probabilités quantiques et solution automatique
        """
        try:
            # Récupération de la partie et vérifications
            game = await self.game_repo.get_game_with_full_details(db, game_id)
            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            if game.status != GameStatus.ACTIVE.value:
                raise GameNotActiveError("La partie n'est pas active")

            # Vérification de la participation
            participation = None
            for p in game.participations:
                if p.player_id == player_id:
                    participation = p
                    break

            if not participation or participation.status != ParticipationStatus.ACTIVE.value:
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

            # === Calcul du résultat avec support quantique ===
            result = await self._calculate_attempt_result(
                attempt_data.combination,
                game.solution,
                game
            )

            # Créer la tentative en base
            attempt = GameAttempt(
                game_id=game_id,
                player_id=player_id,
                attempt_number=current_attempts + 1,
                combination=attempt_data.combination,
                correct_positions=result["correct_positions"],
                correct_colors=result["correct_colors"],
                is_correct=result["is_winning"],
                used_quantum_hint=result.get("quantum_calculated", False),
                hint_type=None,
                quantum_data=result.get("quantum_probabilities"),
                attempt_score=result["score"],
                time_taken=None
            )

            db.add(attempt)

            # Mise à jour de la participation
            participation.attempts_made = current_attempts + 1
            participation.score += result["score"]

            # Gestion de la fin de partie
            game_finished = False
            player_eliminated = False

            if result["is_winning"]:
                # Le joueur a gagné
                participation.status = ParticipationStatus.FINISHED.value
                participation.is_winner = True
                participation.finished_at = datetime.utcnow()
                game_finished = True

                # Vérifier si c'est le premier gagnant
                existing_winners = [p for p in game.participations if p.is_winner]
                if len(existing_winners) <= 1:  # Ce joueur est le premier ou seul gagnant
                    game.status = GameStatus.FINISHED.value
                    game.finished_at = datetime.utcnow()
            else:
                # Vérifier si le joueur a épuisé ses tentatives
                if game.max_attempts and participation.attempts_made >= game.max_attempts:
                    participation.status = ParticipationStatus.ELIMINATED.value
                    participation.is_eliminated = True
                    participation.finished_at = datetime.utcnow()
                    player_eliminated = True

                    # Vérifier si tous les joueurs sont finis
                    if await self._check_all_players_finished(db, game):
                        game.status = GameStatus.FINISHED.value
                        game.finished_at = datetime.utcnow()
                        game_finished = True

            await db.commit()
            await db.refresh(attempt)

            # Calculer les tentatives restantes
            remaining_attempts = None
            if game.max_attempts:
                remaining_attempts = max(0, game.max_attempts - participation.attempts_made)

            # === DÉTERMINER SI LA SOLUTION DOIT ÊTRE RÉVÉLÉE ===
            revealed_solution = None
            should_reveal_solution = (
                    result["is_winning"] or  # Joueur a gagné
                    player_eliminated or  # Joueur éliminé
                    game_finished  # Partie terminée
            )

            if should_reveal_solution:
                revealed_solution = game.solution
                print(
                    f"🎯 Solution révélée: {revealed_solution} (raison: {'victoire' if result['is_winning'] else 'élimination' if player_eliminated else 'fin de partie'})")

            # === CONSTRUCTION DU RÉSULTAT AVEC TOUS LES CHAMPS OBLIGATOIRES ===
            attempt_result = AttemptResult(
                id=attempt.id,
                attempt_number=attempt.attempt_number,
                combination=attempt.combination,
                exact_matches=attempt.correct_positions,  # Mapping correct
                position_matches=attempt.correct_colors,  # Mapping correct
                is_winning=attempt.is_correct,  # Champ principal
                score=attempt.attempt_score,  # Score
                time_taken=attempt.time_taken,
                game_finished=game_finished or player_eliminated,
                game_status=game.status,
                remaining_attempts=remaining_attempts,
                quantum_calculated=result.get("quantum_calculated", False),
                quantum_probabilities=result.get("quantum_probabilities"),
                quantum_hint_used=attempt.used_quantum_hint,
                solution=revealed_solution,

                # Champs legacy automatiquement calculés par les validators
                is_correct=attempt.is_correct,
                correct_positions=attempt.correct_positions,
                correct_colors=attempt.correct_colors
            )

            return attempt_result

        except Exception as e:
            await db.rollback()
            if isinstance(e, (EntityNotFoundError, GameError, ValidationError)):
                raise
            raise GameError(f"Erreur lors de la tentative: {str(e)}")

    async def _check_all_players_finished(self, db: AsyncSession, game) -> bool:
        """Vérifie si tous les joueurs ont terminé leur partie"""
        active_players = [
            p for p in game.participations
            if p.status in [ParticipationStatus.ACTIVE.value, ParticipationStatus.READY.value]
        ]
        return len(active_players) == 0

    async def _calculate_attempt_result(
            self,
            combination: List[int],
            solution: List[int],
            game: Game = None
    ) -> Dict[str, Any]:
        """
        Calcule le résultat d'une tentative avec support quantique - CORRIGÉ
        """
        is_quantum_game = game and (game.game_type == GameType.QUANTUM.value or game.quantum_enabled)

        if is_quantum_game:
            # === MODE QUANTIQUE ===
            try:
                quantum_result = await quantum_service.calculate_quantum_hints_with_probabilities(
                    solution, combination
                )

                # CORRECTION: Utiliser les bons noms de champs du service quantique
                correct_positions = quantum_result["exact_matches"]  # correct_positions vient de exact_matches
                correct_colors = quantum_result["wrong_position"]  # correct_colors vient de wrong_position

                # Vérifier si c'est gagnant
                is_winning = correct_positions == len(solution)

                # Calcul du score avec bonus quantique
                score = calculate_game_score(
                    len(combination) + 1,
                    len(solution) * 2,
                    0  # temps sera ajouté plus tard
                )

                if is_winning:
                    score += 500  # Bonus de victoire

                # Bonus quantique supplémentaire
                if quantum_result.get("quantum_calculated", False):
                    score += 100  # Bonus pour calcul quantique

                print(f"Calcul quantique utilisé: positions={correct_positions}, couleurs={correct_colors}")

                return {
                    "correct_positions": correct_positions,  # Ce que la DB attend
                    "correct_colors": correct_colors,  # Ce que la DB attend
                    "is_winning": is_winning,
                    "score": score,
                    "quantum_calculated": True,
                    "quantum_probabilities": quantum_result
                }

            except Exception as e:
                print(f"Erreur dans le calcul quantique, fallback classique: {e}")
                # Fallback vers le calcul classique
                return await self._calculate_classical_attempt_result(combination, solution)

        else:
            # === MODE CLASSIQUE ===
            return await self._calculate_classical_attempt_result(combination, solution)

    async def _calculate_classical_attempt_result(
            self,
            combination: List[int],
            solution: List[int]
    ) -> Dict[str, Any]:
        """
        Calcul classique séparé pour clarté - CORRIGÉ
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
            len(combination) + 1,
            len(solution) * 2,
            0
        )

        if is_winning:
            score += 500  # Bonus de victoire

        print(f"Calcul classique utilisé: positions={correct_positions}, couleurs={correct_colors}")

        return {
            "correct_positions": correct_positions,  # Ce que la DB attend
            "correct_colors": correct_colors,  # Ce que la DB attend
            "is_winning": is_winning,
            "score": score,
            "quantum_calculated": False,
            "quantum_probabilities": None
        }

    def _calculate_classical_hints(self, combination: List[int], solution: List[int]) -> tuple[int, int]:
        """
        Calcule les indices de manière classique (méthode de fallback)
        NOUVEAU: Extraite pour réutilisation
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

        return correct_positions, correct_colors

    # === MÉTHODES UTILITAIRES ===
    async def _check_all_players_finished(
            self,
            db: AsyncSession,
            game: Game
    ) -> bool:
        """
        Vérifie si tous les joueurs de la partie sont dans un état final

        Returns:
            True si tous les joueurs sont 'finished', 'eliminated', ou 'disconnected'
        """
        try:
            final_statuses = [
                ParticipationStatus.FINISHED.value,
                ParticipationStatus.ELIMINATED.value,
                ParticipationStatus.DISCONNECTED.value
            ]

            # Récupérer toutes les participations de la partie
            active_participations = [
                p for p in game.participations
                if p.status not in final_statuses
            ]

            # Si aucun joueur actif, la partie peut se terminer
            return len(active_participations) == 0

        except Exception as e:
            print(f"Erreur lors de la vérification des joueurs: {e}")
            return False

    async def get_user_current_game(
            self,
            db: AsyncSession,
            user_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Récupère la partie active actuelle d'un utilisateur"""
        try:
            active_participations = await self.participation_repo.get_user_active_participations(
                db, user_id
            )

            if not active_participations:
                return None

            # Prendre la première participation active
            participation = active_participations[0]
            game = participation.game

            return {
                "game_id": str(game.id),
                "room_code": game.room_code,
                "game_type": game.game_type,
                "game_mode": game.game_mode,
                "status": game.status,
                "participation_status": participation.status,
                "joined_at": participation.joined_at.isoformat() if participation.joined_at else None
            }

        except Exception as e:
            raise GameError(f"Erreur lors de la récupération de la partie active: {str(e)}")

    # Méthodes pour compatibilité avec l'API
    async def search_games(
            self,
            db: AsyncSession,
            pagination: Any,
            search: Any,
            **kwargs
    ) -> Dict[str, Any]:
        """Recherche des parties selon des critères"""
        # TODO: Implémenter la vraie logique de recherche
        return {
            "games": [],
            "total": 0,
            "page": 1,
            "per_page": 10,
            "pages": 0
        }

    async def _format_participant_info(self, participation: GameParticipation) -> Dict[str, Any]:
        """Formate les informations d'un participant"""
        return {
            "id": participation.id,
            "player_id": participation.player_id,
            "player_username": participation.player.username if participation.player else "Inconnu",
            "player_full_name": participation.player.full_name if participation.player else None,
            "status": participation.status,
            "role": participation.role,
            "join_order": participation.join_order,
            "score": participation.score,
            "attempts_made": participation.attempts_made,
            "quantum_hints_used": participation.quantum_hints_used,
            "quantum_score": 0,  # Calculé si nécessaire
            "is_ready": participation.is_ready,
            "is_winner": participation.is_winner,
            "is_eliminated": participation.is_eliminated,
            "joined_at": participation.joined_at,
            "finished_at": participation.finished_at
        }

    async def _format_attempt_info(self, attempt: GameAttempt) -> Dict[str, Any]:
        """Formate les informations d'une tentative"""
        return {
            "id": attempt.id,
            "attempt_number": attempt.attempt_number,
            "combination": attempt.combination,
            "correct_positions": attempt.correct_positions,
            "correct_colors": attempt.correct_colors,
            "is_correct": attempt.is_correct,
            "used_quantum_hint": attempt.used_quantum_hint,
            "hint_type": attempt.hint_type,
            "quantum_data": attempt.quantum_data,
            "attempt_score": attempt.attempt_score,
            "time_taken": attempt.time_taken,
            "created_at": attempt.created_at
        }

    async def get_game_details(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: UUID
    ) -> Dict[str, Any]:
        """
        Récupère les détails complets d'une partie avec tous les champs requis
         Retour complet pour le schéma GameFull SANS la solution
        """
        try:
            # Récupérer la partie avec tous les détails (participants, tentatives, créateur)
            game = await self.game_repo.get_game_with_full_details(db, game_id)
            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            # Récupérer le créateur
            creator = await self.user_repo.get_by_id(db, game.creator_id)
            creator_username = creator.username if creator else "Inconnu"

            # Formater les participants
            participants = []
            for participation in game.participations:
                participant_info = {
                    "id": participation.id,
                    "player_id": participation.player_id,
                    "player_username": participation.player.username if participation.player else "Inconnu",
                    "player_full_name": participation.player.full_name if participation.player else None,
                    "status": participation.status,
                    "role": participation.role,
                    "join_order": participation.join_order,
                    "score": participation.score,
                    "attempts_made": participation.attempts_made,
                    "quantum_hints_used": participation.quantum_hints_used,
                    "quantum_score": 0,  # Calculé si nécessaire
                    "is_ready": participation.is_ready,
                    "is_winner": participation.is_winner,
                    "is_eliminated": participation.is_eliminated,
                    "joined_at": participation.joined_at,
                    "finished_at": participation.finished_at
                }
                participants.append(participant_info)

            # Formater les tentatives
            attempts = []
            for attempt in game.attempts:
                attempt_info = {
                    "id": attempt.id,
                    "attempt_number": attempt.attempt_number,
                    "combination": attempt.combination,
                    "correct_positions": attempt.correct_positions,
                    "correct_colors": attempt.correct_colors,
                    "is_correct": attempt.is_correct,
                    "used_quantum_hint": attempt.used_quantum_hint,
                    "hint_type": attempt.hint_type,
                    "quantum_data": attempt.quantum_data,
                    "attempt_score": attempt.attempt_score,
                    "time_taken": attempt.time_taken,
                    "created_at": attempt.created_at
                }
                attempts.append(attempt_info)

            # Calculer le nombre de joueurs actuels
            current_players = len([p for p in game.participations if p.status in ['waiting', 'ready', 'active']])

            # Construire la réponse complète selon le schéma GameFull
            #La solution n'est JAMAIS exposée ici
            return {
                # GameInfo base fields
                "id": game.id,
                "room_code": game.room_code,
                "game_type": game.game_type,
                "game_mode": game.game_mode,
                "status": game.status,
                "difficulty": game.difficulty,
                "combination_length": game.combination_length,
                "available_colors": game.available_colors,
                "max_attempts": game.max_attempts,
                "time_limit": game.time_limit,
                "max_players": game.max_players,
                "is_private": game.is_private,
                "allow_spectators": game.allow_spectators,
                "enable_chat": game.enable_chat,
                "quantum_enabled": game.quantum_enabled,
                "creator_id": game.creator_id,
                "creator_username": creator_username,
                "created_at": game.created_at,
                "started_at": game.started_at,
                "finished_at": game.finished_at,
                "current_players": current_players,

                # GameFull additional fields
                "participants": participants,
                "attempts": attempts,
                "settings": game.settings or {},
                "quantum_data": game.quantum_data,
                "solution": None
            }

        except Exception as e:
            if isinstance(e, EntityNotFoundError):
                raise
            raise GameError(f"Erreur lors de la récupération des détails de la partie: {str(e)}")

    async def get_quantum_game_info(
            self,
            db: AsyncSession,
            game_id: UUID
    ) -> Dict[str, Any]:
        """Récupère les informations quantiques d'une partie"""
        game = await self.game_repo.get_by_id(db, game_id)
        if not game:
            raise EntityNotFoundError("Partie non trouvée")

        return {
            "quantum_enabled": game.quantum_enabled,
            "quantum_solution_generated": bool(game.quantum_data and "solution_generation" in game.quantum_data),
            "quantum_hints_available": game.quantum_enabled,
            "quantum_config": game.get_quantum_config() if hasattr(game, 'get_quantum_config') else {},
            "quantum_statistics": game.quantum_data.get("statistics", {}) if game.quantum_data else {}
        }

    # === MÉTHODES PRIVÉES ===

    def _get_difficulty_config(self, difficulty) -> Dict[str, int]:
        """Récupère la configuration d'une difficulté"""
        #  Gestion des Enums et des strings
        difficulty_value = difficulty.value if hasattr(difficulty, 'value') else difficulty

        configs = {
            "easy": {"colors": 4, "length": 3, "attempts": 15},
            "medium": {"colors": 6, "length": 4, "attempts": 12},
            "hard": {"colors": 8, "length": 5, "attempts": 10},
            "expert": {"colors": 10, "length": 6, "attempts": 8},
            "quantum": {"colors": 12, "length": 7, "attempts": 6}
        }
        return configs.get(difficulty_value, configs["medium"])

    async def _generate_unique_room_code(self, db: AsyncSession) -> str:
        """Génère un code de room unique"""
        for _ in range(10):  # Essayer 10 fois
            code = generate_room_code()
            existing = await self.game_repo.get_by_room_code(db, code)
            if not existing:
                return code

        # Si on n'arrive pas à générer un code unique, utiliser un UUID
        return str(uuid4())[:8].upper()

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
            status=ParticipationStatus.WAITING.value
        )

        db.add(participation)
        await db.commit()
        await db.refresh(participation)

        return participation

    def _generate_solution(self, length: int, colors: int) -> List[int]:
        """Génère une solution aléatoire"""
        import random
        return [random.randint(1, colors) for _ in range(length)]

game_service = GameService()
logger.info("🎯 GameService initialisé et prêt")
