"""
Service de gestion des jeux pour Quantum Mastermind
Logique métier pour les parties, tentatives et scoring
CORRECTION: Synchronisé avec les modèles et schémas corrigés
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
        Crée une nouvelle partie (méthode originale corrigée)

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

            # VÉRIFICATION MODIFIÉE: Plus explicite sur les parties actives
            active_participations = await self.participation_repo.get_user_active_participations(
                db, creator_id
            )

            if active_participations:
                # Récupérer les informations des parties actives
                active_games_info = []
                for participation in active_participations:
                    active_games_info.append(f"Room: {participation.game.room_code}")

                games_list = ", ".join(active_games_info)
                raise GameError(
                    f"Vous participez déjà à des parties actives ({games_list}). "
                    "Quittez d'abord ces parties avant d'en créer une nouvelle."
                )

            # Configuration de difficulté CORRECTE
            difficulty_config = self._get_difficulty_config(game_data.difficulty)

            # Utiliser les valeurs de difficulty_config ou celles du game_data si spécifiées
            combination_length = getattr(game_data, 'combination_length', difficulty_config["length"])
            available_colors = getattr(game_data, 'available_colors', difficulty_config["colors"])
            max_attempts = difficulty_config["attempts"]

            # Génération du code de room unique
            room_code = game_data.room_code or await self._generate_unique_room_code(db)

            # Création de l'objet Game
            game = Game(
                room_code=room_code,
                game_type=game_data.game_type,
                game_mode=game_data.game_mode,
                status=GameStatus.WAITING,
                difficulty=game_data.difficulty,
                combination_length=combination_length,
                available_colors=available_colors,
                max_attempts=max_attempts,
                time_limit=game_data.time_limit,
                max_players=game_data.max_players,
                is_private=game_data.is_private,
                allow_spectators=game_data.allow_spectators,
                creator_id=creator_id,
                solution=generate_solution(combination_length, available_colors),
                settings=getattr(game_data, 'settings', {})
            )

            # Ajout à la base de données
            db.add(game)
            await db.commit()
            await db.refresh(game)

            # Ajouter TOUJOURS le créateur comme participant
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
                "combination_length": combination_length,
                "available_colors": available_colors,
                "created_at": game.created_at.isoformat(),
                "message": "Partie créée avec succès - vous avez été automatiquement ajouté à la partie"
            }

        except Exception as e:
            await db.rollback()
            if isinstance(e, (ValidationError, GameError)):
                raise
            raise GameError(f"Erreur lors de la création de la partie: {str(e)}")

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

    async def create_game_with_auto_leave(
            self,
            db: AsyncSession,
            game_data: GameCreate,
            creator_id: UUID,
            auto_leave: bool = False
    ) -> Dict[str, Any]:
        """
        Crée une nouvelle partie avec option auto-leave des parties actives

        Args:
            db: Session de base de données
            game_data: Données de création de la partie
            creator_id: ID du créateur
            auto_leave: Si True, quitte automatiquement les parties actives

        Returns:
            Informations de la partie créée avec détails des actions effectuées

        Raises:
            ValidationError: Si les données sont invalides
            GameError: Si la création échoue
        """
        try:
            # 1. Vérifier d'abord si l'utilisateur est dans des parties actives
            active_participations = await self.participation_repo.get_user_active_participations(
                db, creator_id
            )

            leave_result = None

            if active_participations:
                if auto_leave:
                    # Option auto_leave activée : quitter automatiquement
                    try:
                        leave_result = await self.leave_all_active_games(db, creator_id)
                    except EntityNotFoundError:
                        # Pas de parties actives trouvées (race condition), continuer
                        pass
                else:
                    # Option auto_leave désactivée : lever une erreur informative
                    active_game = active_participations[0].game
                    raise GameError(
                        f"Vous participez déjà à une partie active (Room: {active_game.room_code}). "
                        "Quittez d'abord cette partie ou utilisez auto_leave=true pour la quitter automatiquement."
                    )

            # 2. Continuer avec la création normale de la partie
            creation_result = await self.create_game(db, game_data, creator_id)

            # 3. Combiner les résultats si auto_leave a été utilisé
            if leave_result:
                return {
                    **creation_result,
                    "auto_leave_performed": True,
                    "leave_summary": leave_result["summary"],
                    "message": f"{creation_result['message']} (Après avoir quitté {leave_result['summary']['total_left']} partie(s) active(s))"
                }
            else:
                return {
                    **creation_result,
                    "auto_leave_performed": False
                }

        except Exception as e:
            await db.rollback()
            if isinstance(e, (ValidationError, GameError)):
                raise
            raise GameError(f"Erreur lors de la création de la partie avec auto-leave: {str(e)}")

    # 2. MODIFICATION DE LA MÉTHODE join_game
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
            GameError: Si le joueur est déjà dans une autre partie
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
                if current_game_participation and current_game_participation.status == ParticipationStatus.DISCONNECTED:
                    current_game_participation.status = ParticipationStatus.WAITING
                    current_game_participation.left_at = None
                    await db.commit()
                    return {
                        "message": "Reconnexion réussie à la partie",
                        "participation_id": current_game_participation.id,
                        "game_id": game_id,
                        "join_order": current_game_participation.join_order
                    }

                # Si c'est la même partie et que le joueur est déjà actif
                if current_game_participation:
                    raise GameError("Vous participez déjà à cette partie")

            # Récupération de la partie avec participants
            game = await self.game_repo.get_game_with_full_details(db, game_id)
            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            # Vérifications standard
            if game.is_full:
                raise GameFullError(
                    "Partie complète",
                    game_id=game_id,
                    max_players=game.max_players,
                    current_players=game.current_players_count
                )

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
                "message": "Vous avez rejoint la partie avec succès",
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

    async def get_user_current_game(
            self,
            db: AsyncSession,
            user_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Récupère la partie active actuelle d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur

        Returns:
            Informations de la partie active ou None
        """
        try:
            active_participations = await self.participation_repo.get_user_active_participations(
                db, user_id
            )

            if not active_participations:
                return None

            # Prendre la première participation active (un utilisateur ne devrait avoir qu'une seule partie active)
            participation = active_participations[0]
            game = participation.game

            return {
                "game_id": game.id,
                "room_code": game.room_code,
                "game_type": game.game_type,
                "game_mode": game.game_mode,
                "status": game.status,
                "participation_status": participation.status,
                "joined_at": participation.joined_at.isoformat() if participation.joined_at else None
            }

        except Exception as e:
            raise GameError(f"Erreur lors de la récupération de la partie active: {str(e)}")

    async def make_attempt(
            self,
            db: AsyncSession,
            game_id: UUID,
            player_id: UUID,
            attempt_data: AttemptCreate
    ) -> AttemptResult:
        """
        Effectue une tentative dans une partie avec gestion d'élimination

        Args:
            db: Session de base de données
            game_id: ID de la partie
            player_id: ID du joueur
            attempt_data: Données de la tentative

        Returns:
            Résultat de la tentative

        Raises:
            EntityNotFoundError: Si la partie ou le joueur n'existe pas
            GameError: Si la tentative n'est pas autorisée
            ValidationError: Si les données sont invalides
        """
        try:
            # Récupération de la partie avec tous les détails
            game = await self.game_repo.get_game_with_full_details(db, game_id)
            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            # Vérifications de base
            if game.status != GameStatus.ACTIVE:
                raise GameError("Cette partie n'est pas active")

            # Vérification de la participation
            participation = game.get_participation(player_id)
            if not participation or participation.status not in [ParticipationStatus.ACTIVE]:
                raise GameError("Vous ne participez pas activement à cette partie")

            # 🔥 VÉRIFICATION: Joueur déjà éliminé ou terminé
            if participation.status in [ParticipationStatus.ELIMINATED, ParticipationStatus.FINISHED]:
                raise GameError("Vous ne pouvez plus jouer (éliminé ou partie terminée)")

            # Vérification du nombre de tentatives
            current_attempts = await self.attempt_repo.count_player_attempts(
                db, game_id, player_id
            )

            # 🔥 CORRECTION: On peut jouer tant qu'on n'a pas DÉPASSÉ max_attempts
            # Si max_attempts = 6, on peut faire les tentatives 1,2,3,4,5,6 mais pas la 7ème
            if game.max_attempts and current_attempts >= game.max_attempts:
                raise GameError(f"Nombre maximum de tentatives atteint ({game.max_attempts})")

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

            # 🔥 NOUVELLE LOGIQUE: Gestion des résultats de tentative
            game_finished = False
            player_eliminated = False

            if result["is_winning"]:
                # ✅ VICTOIRE: Marquer comme gagnant et terminé
                participation.is_winner = True
                participation.status = ParticipationStatus.FINISHED
                participation.finished_at = datetime.now(timezone.utc)
                print(f"🏆 Joueur {player_id} a gagné la partie {game_id}")

                # TODO: Broadcast WebSocket de victoire
                # await broadcast_player_won(game_id, player_id, participation.player.username, participation.attempts_made)

            else:
                # ❌ ÉCHEC: Vérifier si éliminé
                if game.max_attempts and participation.attempts_made >= game.max_attempts:
                    # Joueur éliminé - a utilisé toutes ses tentatives sans gagner
                    participation.status = ParticipationStatus.ELIMINATED
                    participation.is_eliminated = True
                    participation.finished_at = datetime.now(timezone.utc)
                    player_eliminated = True
                    print(
                        f"💀 Joueur {player_id} éliminé (max tentatives atteintes: {participation.attempts_made}/{game.max_attempts})")

                    # TODO: Broadcast WebSocket d'élimination
                    # await broadcast_player_eliminated(game_id, player_id, participation.player.username, participation.attempts_made, game.max_attempts)

            # 🔥 VÉRIFICATION: La partie doit-elle se terminer ?
            game_finished = await self._check_and_finish_game(db, game)

            await db.commit()
            await db.refresh(attempt)

            # Obtenir des informations contextuelles pour le résultat
            participations = [p for p in game.participations if p.role == "player"]
            active_players = len([p for p in participations if p.status == ParticipationStatus.ACTIVE])
            eliminated_players = len([p for p in participations if p.status == ParticipationStatus.ELIMINATED])
            winners_count = len([p for p in participations if p.status == ParticipationStatus.FINISHED])

            # Construire le résultat enrichi
            return AttemptResult(
                attempt_id=attempt.id,
                attempt_number=attempt.attempt_number,
                correct_positions=attempt.correct_positions,
                correct_colors=attempt.correct_colors,
                is_winning=attempt.is_correct,
                score=attempt.attempt_score,
                game_finished=game_finished,
                solution=game.solution if (attempt.is_correct or game_finished) else None,
                quantum_hint_used=attempt.used_quantum_hint,
                time_taken=attempt.time_taken,
                remaining_attempts=(
                    max(0, game.max_attempts - participation.attempts_made) if game.max_attempts else None
                )
            )

        except Exception as e:
            await db.rollback()
            if isinstance(e, (EntityNotFoundError, GameError, ValidationError)):
                raise
            raise GameError(f"Erreur lors de la tentative: {str(e)}")

    async def _check_and_finish_game(
            self,
            db: AsyncSession,
            game: Game
    ) -> bool:
        """
        Vérifie si la partie doit se terminer et la termine si nécessaire

        Args:
            db: Session de base de données
            game: Instance de la partie

        Returns:
            True si la partie a été terminée, False sinon
        """
        try:
            # Récupérer toutes les participations actives
            participations = [p for p in game.participations if p.role == "player"]

            if not participations:
                return False

            # Compter les statuts
            finished_count = len([p for p in participations if p.status == ParticipationStatus.FINISHED])
            eliminated_count = len([p for p in participations if p.status == ParticipationStatus.ELIMINATED])
            active_count = len([p for p in participations if p.status == ParticipationStatus.ACTIVE])

            total_players = len(participations)
            completed_players = finished_count + eliminated_count

            print(
                f"📊 Partie {game.id}: {finished_count} gagnants, {eliminated_count} éliminés, {active_count} actifs sur {total_players}")

            # 🔥 CONDITIONS DE FIN DE PARTIE
            should_finish = False
            finish_reason = ""

            if game.game_mode == GameMode.SINGLE:
                # Mode solo: terminer dès qu'il y a un gagnant OU que le joueur est éliminé
                if finished_count > 0:
                    should_finish = True
                    finish_reason = "Victoire en mode solo"
                elif eliminated_count > 0:
                    should_finish = True
                    finish_reason = "Élimination en mode solo"

            else:
                # Mode multijoueur: terminer quand tous les joueurs sont soit finished soit eliminated
                if completed_players == total_players:
                    should_finish = True
                    finish_reason = f"Tous les joueurs ont terminé ({finished_count} gagnants, {eliminated_count} éliminés)"

            # 🔥 TERMINER LA PARTIE SI NÉCESSAIRE
            if should_finish:
                game.status = GameStatus.FINISHED
                game.finished_at = datetime.now(timezone.utc)

                # Mettre à jour les participations encore actives (edge case)
                for participation in participations:
                    if participation.status == ParticipationStatus.ACTIVE:
                        participation.status = ParticipationStatus.ELIMINATED
                        participation.is_eliminated = True
                        participation.finished_at = datetime.now(timezone.utc)

                print(f"🏁 Partie {game.id} terminée: {finish_reason}")
                return True

            return False

        except Exception as e:
            print(f"🚨 Erreur lors de la vérification de fin de partie: {str(e)}")
            return False

    async def get_game_status_summary(
            self,
            db: AsyncSession,
            game_id: UUID
    ) -> Dict[str, Any]:
        """
        Obtient un résumé du statut de la partie

        Args:
            db: Session de base de données
            game_id: ID de la partie

        Returns:
            Résumé du statut
        """
        try:
            game = await self.game_repo.get_game_with_full_details(db, game_id)
            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            participations = [p for p in game.participations if p.role == "player"]

            return {
                "game_id": str(game_id),
                "status": game.status,
                "total_players": len(participations),
                "finished_players": len([p for p in participations if p.status == ParticipationStatus.FINISHED]),
                "eliminated_players": len([p for p in participations if p.status == ParticipationStatus.ELIMINATED]),
                "active_players": len([p for p in participations if p.status == ParticipationStatus.ACTIVE]),
                "winners": [
                    {
                        "user_id": str(p.player_id),
                        "username": p.player.username if p.player else "Unknown",
                        "score": p.score,
                        "attempts": p.attempts_made
                    }
                    for p in participations if p.is_winner
                ],
                "max_attempts": game.max_attempts,
                "is_finished": game.status == GameStatus.FINISHED
            }

        except Exception as e:
            raise GameError(f"Erreur lors de la récupération du statut: {str(e)}")

    async def leave_all_active_games(
            self,
            db: AsyncSession,
            player_id: UUID
    ) -> Dict[str, Any]:
        """
        Quitte toutes les parties actives de l'utilisateur avec gestion intelligente

        Args:
            db: Session de base de données
            player_id: ID du joueur

        Returns:
            Dictionnaire avec les détails des parties quittées et modifiées

        Raises:
            EntityNotFoundError: Si aucune participation active n'est trouvée
            GameError: En cas d'erreur lors du traitement
        """
        try:
            # 1. Récupération de toutes les participations actives de l'utilisateur
            participations_stmt = select(GameParticipation).join(Game).where(
                GameParticipation.player_id == player_id,
                Game.status.in_(['waiting', 'starting', 'active', 'paused']),
                GameParticipation.status != ParticipationStatus.DISCONNECTED
            ).options(selectinload(GameParticipation.game))

            result = await db.execute(participations_stmt)
            active_participations = result.scalars().all()

            if not active_participations:
                raise EntityNotFoundError(
                    "Aucune partie active trouvée. Vous ne participez actuellement à aucune partie."
                )

            left_games = []
            cancelled_games = []
            maintained_games = []

            # 2. Traitement de chaque participation
            for participation in active_participations:
                game = participation.game

                # Mettre le joueur en disconnected
                participation.status = ParticipationStatus.DISCONNECTED
                participation.left_at = datetime.now(timezone.utc)

                # Récupérer toutes les autres participations de cette partie
                other_participations_stmt = select(GameParticipation).where(
                    GameParticipation.game_id == game.id,
                    GameParticipation.player_id != player_id,
                    GameParticipation.status != ParticipationStatus.DISCONNECTED
                )

                other_result = await db.execute(other_participations_stmt)
                other_participations = other_result.scalars().all()

                game_info = {
                    "game_id": str(game.id),
                    "room_code": game.room_code,
                    "game_type": game.game_type,
                    "original_status": game.status
                }

                # 3. Logique de décision pour la partie
                if not other_participations:
                    # Cas 1: L'utilisateur est seul dans la partie
                    game.status = GameStatus.CANCELLED
                    game.finished_at = datetime.now(timezone.utc)

                    # ✅ CORRECTION : Synchroniser les statuts
                    await self.game_repo.sync_participation_status(db, game.id)

                    cancelled_games.append({
                        **game_info,
                        "action": "cancelled",
                        "reason": "Joueur seul dans la partie"
                    })
                else:
                    # Cas 2: D'autres joueurs sont présents
                    # Vérifier les statuts des autres joueurs
                    other_statuses = [p.status for p in other_participations]
                    valid_statuses = [
                        ParticipationStatus.WAITING,
                        ParticipationStatus.READY,
                        ParticipationStatus.ACTIVE,
                        ParticipationStatus.ELIMINATED
                    ]

                    all_others_have_valid_status = all(status in valid_statuses for status in other_statuses)

                    if all_others_have_valid_status:
                        # Ne rien faire à la partie
                        maintained_games.append({
                            **game_info,
                            "action": "maintained",
                            "reason": f"Autres joueurs actifs ({len(other_participations)} joueurs restants)",
                            "remaining_players": len(other_participations)
                        })
                    else:
                        # Annuler la partie
                        game.status = GameStatus.CANCELLED
                        game.finished_at = datetime.now(timezone.utc)

                        # ✅ CORRECTION : Synchroniser les statuts
                        await self.game_repo.sync_participation_status(db, game.id)

                        cancelled_games.append({
                            **game_info,
                            "action": "cancelled",
                            "reason": f"Autres joueurs non-actifs (statuts: {other_statuses})"
                        })

                left_games.append(game_info)

            # 4. Sauvegarder les modifications
            await db.commit()

            # 5. Retourner le résumé des actions
            return {
                "message": f"Vous avez quitté {len(left_games)} partie(s) active(s)",
                "summary": {
                    "total_left": len(left_games),
                    "games_cancelled": len(cancelled_games),
                    "games_maintained": len(maintained_games)
                },
                "details": {
                    "left_games": left_games,
                    "cancelled_games": cancelled_games,
                    "maintained_games": maintained_games
                }
            }

        except Exception as e:
            await db.rollback()
            if isinstance(e, EntityNotFoundError):
                raise
            raise GameError(f"Erreur lors de l'abandon des parties actives: {str(e)}")

    # 5. MÉTHODE POUR FORCER LA SORTIE D'UNE PARTIE (ADMIN)
    async def force_leave_all_games(
            self,
            db: AsyncSession,
            user_id: UUID,
            admin_id: UUID
    ) -> List[str]:
        """
        Force un utilisateur à quitter toutes ses parties actives (fonction admin)

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur à faire sortir
            admin_id: ID de l'administrateur

        Returns:
            Liste des codes de room des parties quittées

        Raises:
            AuthorizationError: Si l'admin n'a pas les permissions
        """
        try:
            # Vérifier que l'admin a les permissions (cette vérification devrait être faite en amont)
            admin_user = await self.user_repo.get_by_id(db, admin_id)  # Supposons qu'il y ait un user_repo
            if not admin_user or not admin_user.is_superuser:
                raise AuthorizationError("Seuls les administrateurs peuvent forcer la sortie")

            active_participations = await self.participation_repo.get_user_active_participations(
                db, user_id
            )

            left_games = []
            current_time = datetime.now(timezone.utc)

            for participation in active_participations:
                participation.status = ParticipationStatus.DISCONNECTED
                participation.left_at = current_time
                left_games.append(participation.game.room_code)

            await db.commit()

            return left_games

        except Exception as e:
            await db.rollback()
            if isinstance(e, AuthorizationError):
                raise
            raise GameError(f"Erreur lors de la sortie forcée: {str(e)}")

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

    def _generate_solution(self, length: int, colors: int) -> List[int]:
        """
        Génère une solution aléatoire

        Args:
            length: Longueur de la combinaison
            colors: Nombre de couleurs disponibles

        Returns:
            Liste d'entiers représentant la solution
        """
        import random
        return [random.randint(1, colors) for _ in range(length)]


# Instance globale du service de jeu
game_service = GameService()