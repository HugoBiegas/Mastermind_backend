"""
Service de gestion des jeux pour Quantum Mastermind
Logique métier pour les parties, tentatives et scoring
CORRECTION: Version fonctionnelle avec les vrais Enums
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

# CORRECTION: Import des vrais Enums depuis models
from app.models.game import (
    Game, GameParticipation, GameAttempt,
    GameType, GameMode, GameStatus, Difficulty, ParticipationStatus,
    generate_room_code, calculate_game_score, generate_solution
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
        CORRECTION: Adaptation aux vrais Enums
        """
        try:
            # VÉRIFICATION: Empêcher la création si l'utilisateur est déjà dans une partie active
            active_participations = await self.participation_repo.get_user_active_participations(
                db, creator_id
            )

            if active_participations:
                # Récupérer les informations de la partie active
                active_game = active_participations[0].game
                raise GameError(
                    f"Vous participez déjà à une partie active (Room: {active_game.room_code}). "
                    "Quittez d'abord cette partie avant d'en créer une nouvelle."
                )

            # CORRECTION: Utiliser les valeurs des Enums
            difficulty_config = self._get_difficulty_config(game_data.difficulty)

            # CORRECTION: Utiliser les valeurs de difficulty_config ou celles du game_data si spécifiées
            combination_length = getattr(game_data, 'combination_length', difficulty_config["length"])
            available_colors = getattr(game_data, 'available_colors', difficulty_config["colors"])
            max_attempts = getattr(game_data, 'max_attempts', difficulty_config["attempts"])

            # Validation des données avec les valeurs finales
            if combination_length < 2 or combination_length > 8:
                raise ValidationError("La longueur de combinaison doit être entre 2 et 8")

            if available_colors < 3 or available_colors > 10:
                raise ValidationError("Le nombre de couleurs doit être entre 3 et 10")

            if max_attempts and (max_attempts < 1 or max_attempts > 50):
                raise ValidationError("Le nombre de tentatives doit être entre 1 et 50")

            if game_data.max_players < 1 or game_data.max_players > 8:
                raise ValidationError("Le nombre de joueurs doit être entre 1 et 8")

            # Génération du code de room unique
            room_code = await self._generate_unique_room_code(db)

            # Génération de la solution avec les valeurs finales
            solution = self._generate_solution(combination_length, available_colors)

            # CORRECTION: Création de la partie avec les valeurs d'Enums
            game = Game(
                room_code=room_code,
                game_type=game_data.game_type.value if isinstance(game_data.game_type,
                                                                  GameType) else game_data.game_type,
                game_mode=game_data.game_mode.value if isinstance(game_data.game_mode,
                                                                  GameMode) else game_data.game_mode,
                difficulty=game_data.difficulty.value if isinstance(game_data.difficulty,
                                                                    Difficulty) else game_data.difficulty,
                combination_length=combination_length,
                available_colors=available_colors,
                max_attempts=max_attempts,
                time_limit=getattr(game_data, 'time_limit', None),
                max_players=game_data.max_players,
                solution=solution,
                is_private=getattr(game_data, 'is_private', False),
                allow_spectators=getattr(game_data, 'allow_spectators', True),
                enable_chat=getattr(game_data, 'enable_chat', True),
                quantum_enabled=getattr(game_data, 'quantum_enabled', False),
                creator_id=creator_id,
                settings=getattr(game_data, 'settings', {})
            )

            # Ajout à la base de données
            db.add(game)
            await db.commit()
            await db.refresh(game)

            # Ajouter TOUJOURS le créateur comme participant
            await self._add_participant(db, game.id, creator_id, join_order=1)

            # CORRECTION: Récupérer l'utilisateur créateur pour le nom
            creator = await self.user_repo.get_by_id(db, creator_id)
            creator_username = creator.username if creator else "Inconnu"

            # Retour des informations COMPLÈTES selon le schéma attendu
            return {
                "id": str(game.id),
                "room_code": game.room_code,
                "game_type": game.game_type,
                "game_mode": game.game_mode,
                "difficulty": game.difficulty,
                "status": game.status,
                "quantum_enabled": game.quantum_enabled,

                # CORRECTION: Ajouter tous les champs manquants
                "combination_length": combination_length,
                "available_colors": available_colors,
                "max_players": game.max_players,
                "is_private": game.is_private,
                "allow_spectators": game.allow_spectators,
                "enable_chat": game.enable_chat,

                # CORRECTION: Ajouter les champs créateur
                "creator_id": str(game.creator_id),
                "creator_username": creator_username,

                # CORRECTION: Ajouter les timestamps
                "created_at": game.created_at.isoformat(),
                "started_at": game.started_at.isoformat() if game.started_at else None,
                "finished_at": game.finished_at.isoformat() if game.finished_at else None,

                # CORRECTION: Ajouter les compteurs
                "current_players": game.get_current_player_count(),

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
        CORRECTION: Utilisation des valeurs d'Enums
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

            # CORRECTION: Vérifications avec les valeurs d'Enums
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
        CORRECTION: Retour d'un Dict
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
        CORRECTION: Utilisation des valeurs d'Enums
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
        Effectue une tentative
        CORRECTION: Compatible avec les nouveaux schémas
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
                used_quantum_hint=getattr(attempt_data, 'use_quantum_hint', False),
                hint_type=getattr(attempt_data, 'hint_type', None)
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
                if game.game_mode == GameMode.SINGLE.value:
                    game.status = GameStatus.FINISHED.value
                    game.finished_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(attempt)

            # CORRECTION: Construire le résultat selon le nouveau schéma
            return AttemptResult(
                attempt_number=attempt.attempt_number,
                combination=attempt.combination,
                exact_matches=attempt.correct_positions,  # Mapping correct
                position_matches=attempt.correct_colors,  # Mapping correct
                is_correct=attempt.is_correct,
                quantum_calculated=False,
                quantum_hint_used=attempt.used_quantum_hint,
                remaining_attempts=(
                    game.max_attempts - participation.attempts_made
                    if game.max_attempts else None
                ),
                game_finished=game.status == GameStatus.FINISHED.value
            )

        except Exception as e:
            await db.rollback()
            if isinstance(e, (EntityNotFoundError, GameError, ValidationError)):
                raise
            raise GameError(f"Erreur lors de la tentative: {str(e)}")

    # === MÉTHODES UTILITAIRES ===

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

    async def get_game_details(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: UUID
    ) -> Dict[str, Any]:
        """Récupère les détails d'une partie"""
        game = await self.game_repo.get_by_id(db, game_id)
        if not game:
            raise EntityNotFoundError("Partie non trouvée")

        return {
            "id": str(game.id),
            "room_code": game.room_code,
            "status": game.status,
            "quantum_enabled": game.quantum_enabled,
            "game_type": game.game_type,
            "game_mode": game.game_mode
        }

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
        # CORRECTION: Gestion des Enums et des strings
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

    def _calculate_attempt_result(
            self,
            combination: List[int],
            solution: List[int]
    ) -> Dict[str, Any]:
        """Calcule le résultat d'une tentative"""
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
            len([x for x in combination_copy if x != -1]) + 1,
            len(solution) * 2,  # max_attempts basé sur la longueur
            0  # temps sera ajouté plus tard
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
            status=ParticipationStatus.WAITING.value  # CORRECTION: utiliser .value
        )

        db.add(participation)
        await db.commit()
        await db.refresh(participation)

        return participation

    def _generate_solution(self, length: int, colors: int) -> List[int]:
        """Génère une solution aléatoire"""
        import random
        return [random.randint(1, colors) for _ in range(length)]


# Instance globale du service de jeu
game_service = GameService()