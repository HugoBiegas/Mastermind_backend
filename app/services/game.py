"""
Service de jeu pour Quantum Mastermind
Gestion des parties, joueurs, tentatives et logique de jeu
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
import random
import hashlib
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import token_generator
from app.models.game import (
    Game, GamePlayer, GameAttempt, GameStatus, GameType,
    GameMode, PlayerStatus, Difficulty
)
from app.repositories.game import GameRepository, GamePlayerRepository, GameAttemptRepository
from app.schemas.game import (
    GameCreate, GameUpdate, GameJoin, AttemptCreate,
    GameSearch, SolutionHint
)
from app.utils.exceptions import (
    EntityNotFoundError, ValidationError, GameError,
    GameFullError, GameNotActiveError
)


class GameService:
    """Service pour la gestion des jeux"""

    def __init__(self):
        self.game_repo = GameRepository()
        self.player_repo = GamePlayerRepository()
        self.attempt_repo = GameAttemptRepository()

    # === MÉTHODES DE CRÉATION ET GESTION DES PARTIES ===

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
        # Génération du code de room unique
        room_code = game_data.room_code or await self._generate_unique_room_code(db)

        # Vérification de l'unicité
        if not await self.game_repo.is_room_id_available(db, room_code):
            raise ValidationError("Code de room déjà utilisé")

        # Génération de la solution selon le type de jeu
        solution_data = await self._generate_game_solution(game_data.game_type, game_data.difficulty)

        # Création de la partie
        game_dict = game_data.dict(exclude={'room_code'})
        game_dict.update({
            'room_id': room_code,
            'created_by': creator_id,
            'status': GameStatus.WAITING,
            'classical_solution': solution_data['classical_solution'],
            'quantum_solution': solution_data.get('quantum_solution'),
            'solution_hash': solution_data['solution_hash'],
            'quantum_seed': solution_data.get('quantum_seed')
        })

        game = await self.game_repo.create(db, obj_in=game_dict, created_by=creator_id)

        # Ajout du créateur comme premier joueur
        await self._add_player_to_game(
            db, game.id, creator_id, f"Player_{creator_id.hex[:8]}", is_host=True
        )

        return {
            'game_id': game.id,
            'room_code': room_code,
            'game_type': game.game_type,
            'status': game.status,
            'max_players': game.max_players,
            'quantum_enabled': game.is_quantum_enabled
        }

    async def join_game(
            self,
            db: AsyncSession,
            join_data: GameJoin,
            user_id: UUID
    ) -> Dict[str, Any]:
        """
        Rejoint une partie existante

        Args:
            db: Session de base de données
            join_data: Données pour rejoindre
            user_id: ID de l'utilisateur

        Returns:
            Informations de la partie rejointe

        Raises:
            EntityNotFoundError: Si la partie n'existe pas
            GameFullError: Si la partie est pleine
            ValidationError: Si impossible de rejoindre
        """
        # Récupération de la partie
        game = await self.game_repo.get_by_room_id(
            db, join_data.room_code, with_players=True
        )
        if not game:
            raise EntityNotFoundError("Partie non trouvée")

        # Vérifications
        join_check = await self.game_repo.can_user_join_game(db, game.id, user_id)
        if not join_check['can_join']:
            if 'complète' in join_check['reason']:
                raise GameFullError(join_check['reason'])
            else:
                raise ValidationError(join_check['reason'])

        # TODO: Vérifier le mot de passe si nécessaire
        # if game.password and join_data.password != game.password:
        #     raise ValidationError("Mot de passe incorrect")

        # Ajout du joueur
        player_name = join_data.player_name or f"Player_{user_id.hex[:8]}"
        join_order = len(game.players) + 1

        player = await self._add_player_to_game(
            db, game.id, user_id, player_name, join_order=join_order
        )

        return {
            'game_id': game.id,
            'player_id': player.id,
            'player_name': player.player_name,
            'join_order': player.join_order,
            'is_host': player.is_host,
            'current_players': len(game.players) + 1,
            'max_players': game.max_players
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
            user_id: ID de l'utilisateur (doit être l'hôte)

        Returns:
            Confirmation du démarrage

        Raises:
            EntityNotFoundError: Si la partie n'existe pas
            ValidationError: Si impossible de démarrer
        """
        game = await self.game_repo.get_game_with_full_details(db, game_id)
        if not game:
            raise EntityNotFoundError("Partie non trouvée")

        # Vérification des permissions
        host_player = next((p for p in game.players if p.is_host), None)
        if not host_player or host_player.user_id != user_id:
            raise ValidationError("Seul l'hôte peut démarrer la partie")

        # Vérifications d'état
        if game.status != GameStatus.WAITING:
            raise ValidationError("La partie ne peut plus être démarrée")

        if game.game_mode == GameMode.MULTIPLAYER and len(game.players) < 2:
            raise ValidationError("Au moins 2 joueurs requis pour le mode multijoueur")

        # Démarrage de la partie
        game.start_game()

        # Mise à jour du statut des joueurs
        for player in game.players:
            if player.status == PlayerStatus.JOINED:
                player.status = PlayerStatus.PLAYING

        await db.commit()

        return {
            'message': 'Partie démarrée avec succès',
            'started_at': game.started_at,
            'players_count': len(game.players)
        }

    # === MÉTHODES DE JEU ===

    async def make_attempt(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: UUID,
            attempt_data: AttemptCreate
    ) -> Dict[str, Any]:
        """
        Effectue une tentative dans la partie

        Args:
            db: Session de base de données
            game_id: ID de la partie
            user_id: ID de l'utilisateur
            attempt_data: Données de la tentative

        Returns:
            Résultat de la tentative

        Raises:
            EntityNotFoundError: Si la partie ou le joueur n'existe pas
            GameNotActiveError: Si la partie n'est pas active
            ValidationError: Si la tentative est invalide
        """
        # Récupération de la partie et du joueur
        game = await self.game_repo.get_by_id(db, game_id)
        if not game:
            raise EntityNotFoundError("Partie non trouvée")

        if game.status != GameStatus.ACTIVE:
            raise GameNotActiveError("La partie n'est pas active")

        player = await self.player_repo.get_player_in_game(db, game_id, user_id)
        if not player:
            raise EntityNotFoundError("Joueur non trouvé dans cette partie")

        if player.status != PlayerStatus.PLAYING:
            raise ValidationError("Vous ne pouvez pas jouer actuellement")

        # Vérification du nombre de tentatives
        attempts_count = await self.attempt_repo.count_player_attempts(db, game_id, player.id)
        if attempts_count >= game.max_attempts:
            raise ValidationError("Nombre maximum de tentatives atteint")

        # Validation de la tentative
        if not await self._validate_attempt(attempt_data.guess):
            raise ValidationError("Tentative invalide")

        # Traitement de la tentative
        attempt_number = attempts_count + 1
        result = await self._process_attempt(
            db, game, player, attempt_data, attempt_number
        )

        # Vérification de fin de partie
        if result['is_correct']:
            await self._handle_game_completion(db, game, player, won=True)
        elif attempt_number >= game.max_attempts:
            await self._handle_game_completion(db, game, player, won=False)

        return result

    async def get_game_state(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Récupère l'état actuel d'une partie

        Args:
            db: Session de base de données
            game_id: ID de la partie
            user_id: ID de l'utilisateur (pour les données personnalisées)

        Returns:
            État complet de la partie

        Raises:
            EntityNotFoundError: Si la partie n'existe pas
        """
        game = await self.game_repo.get_game_with_full_details(db, game_id)
        if not game:
            raise EntityNotFoundError("Partie non trouvée")

        # Informations de base
        game_state = {
            'game_id': game.id,
            'room_code': game.room_id,
            'status': game.status,
            'game_type': game.game_type,
            'game_mode': game.game_mode,
            'difficulty': game.difficulty,
            'max_attempts': game.max_attempts,
            'max_players': game.max_players,
            'created_at': game.created_at,
            'started_at': game.started_at,
            'finished_at': game.finished_at,
            'quantum_enabled': game.is_quantum_enabled,
            'players': []
        }

        # Informations des joueurs
        for player in game.players:
            player_info = {
                'player_id': player.id,
                'user_id': player.user_id,
                'player_name': player.player_name,
                'status': player.status,
                'is_host': player.is_host,
                'score': player.score,
                'attempts_count': player.attempts_count,
                'quantum_measurements_used': player.quantum_measurements_used
            }
            game_state['players'].append(player_info)

        # Informations spécifiques au joueur
        if user_id:
            player = await self.player_repo.get_player_in_game(db, game_id, user_id)
            if player:
                # Historique des tentatives du joueur
                attempts = await self.attempt_repo.get_player_attempts(
                    db, game_id, player.id
                )
                game_state['my_attempts'] = [
                    {
                        'attempt_number': attempt.attempt_number,
                        'guess': attempt.guess,
                        'result': attempt.result,
                        'is_correct': attempt.is_correct,
                        'time_taken': attempt.time_taken.total_seconds(),
                        'quantum_used': attempt.measurement_used
                    }
                    for attempt in attempts
                ]
                game_state['my_player_id'] = player.id

        return game_state

    async def get_quantum_hint(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: UUID,
            hint_type: str,
            position: Optional[int] = None
    ) -> SolutionHint:
        """
        Fournit un indice quantique

        Args:
            db: Session de base de données
            game_id: ID de la partie
            user_id: ID de l'utilisateur
            hint_type: Type d'indice ('grover', 'measurement', etc.)
            position: Position pour l'indice (optionnel)

        Returns:
            Indice quantique

        Raises:
            EntityNotFoundError: Si la partie n'existe pas
            ValidationError: Si l'indice n'est pas disponible
        """
        # Vérifications de base
        game = await self.game_repo.get_by_id(db, game_id)
        if not game:
            raise EntityNotFoundError("Partie non trouvée")

        if not game.is_quantum_enabled:
            raise ValidationError("Fonctionnalités quantiques non activées")

        player = await self.player_repo.get_player_in_game(db, game_id, user_id)
        if not player:
            raise EntityNotFoundError("Joueur non trouvé")

        # Génération de l'indice selon le type
        hint = await self._generate_quantum_hint(
            game, player, hint_type, position
        )

        # Mise à jour des statistiques du joueur
        if hint_type == 'grover':
            player.grover_hints_used += 1
        elif hint_type == 'measurement':
            player.quantum_measurements_used += 1

        await db.commit()

        return hint

    # === MÉTHODES DE RECHERCHE ===

    async def search_games(
            self,
            db: AsyncSession,
            search_criteria: GameSearch
    ) -> Dict[str, Any]:
        """
        Recherche des parties avec critères

        Args:
            db: Session de base de données
            search_criteria: Critères de recherche

        Returns:
            Résultats de recherche paginés
        """
        return await self.game_repo.search_games(db, search_criteria)

    async def get_active_games(
            self,
            db: AsyncSession,
            *,
            game_type: Optional[GameType] = None,
            has_slots: bool = False,
            limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Récupère les parties actives

        Args:
            db: Session de base de données
            game_type: Type de jeu à filtrer
            has_slots: Seulement les parties avec places libres
            limit: Nombre maximum de parties

        Returns:
            Liste des parties actives
        """
        games = await self.game_repo.get_active_games(
            db, game_type=game_type, has_slots=has_slots, limit=limit
        )

        return [
            {
                'game_id': game.id,
                'room_code': game.room_id,
                'game_type': game.game_type,
                'game_mode': game.game_mode,
                'difficulty': game.difficulty,
                'status': game.status,
                'current_players': len(game.players),
                'max_players': game.max_players,
                'created_at': game.created_at,
                'has_password': bool(game.settings and game.settings.get('password')),
                'quantum_enabled': game.is_quantum_enabled
            }
            for game in games
        ]

    async def get_user_games(
            self,
            db: AsyncSession,
            user_id: UUID,
            *,
            status: Optional[GameStatus] = None,
            limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Récupère les parties d'un utilisateur

        Args:
            db: Session de base de données
            user_id: ID de l'utilisateur
            status: Statut des parties à filtrer
            limit: Nombre maximum de parties

        Returns:
            Liste des parties de l'utilisateur
        """
        games = await self.game_repo.get_user_games(
            db, user_id, status=status, limit=limit
        )

        return [
            {
                'game_id': game.id,
                'room_code': game.room_id,
                'game_type': game.game_type,
                'status': game.status,
                'created_at': game.created_at,
                'started_at': game.started_at,
                'finished_at': game.finished_at,
                'my_player': next(
                    (p for p in game.players if p.user_id == user_id),
                    None
                )
            }
            for game in games
        ]

    # === MÉTHODES PRIVÉES ===

    async def _generate_unique_room_code(self, db: AsyncSession) -> str:
        """Génère un code de room unique"""
        max_attempts = 10
        for _ in range(max_attempts):
            code = token_generator.generate_room_code()
            if await self.game_repo.is_room_id_available(db, code):
                return code

        # Fallback avec timestamp si tous les codes sont pris
        import time
        return f"GAME{int(time.time()) % 100000:05d}"

    async def _generate_game_solution(
            self,
            game_type: GameType,
            difficulty: Difficulty
    ) -> Dict[str, Any]:
        """Génère la solution de la partie"""
        colors = ['red', 'blue', 'green', 'yellow', 'orange', 'purple']

        # Ajustement selon la difficulté
        if difficulty == Difficulty.EASY:
            colors = colors[:4]  # Seulement 4 couleurs
        elif difficulty == Difficulty.EXPERT:
            colors.extend(['black', 'white'])  # 8 couleurs

        # Génération de la solution classique
        solution = [random.choice(colors) for _ in range(4)]

        # Hash pour vérification
        solution_str = ''.join(solution)
        solution_hash = hashlib.sha256(solution_str.encode()).hexdigest()

        result = {
            'classical_solution': solution,
            'solution_hash': solution_hash
        }

        # Génération quantique si nécessaire
        if game_type in [GameType.QUANTUM, GameType.HYBRID]:
            quantum_seed = secrets.token_hex(16)
            result.update({
                'quantum_solution': {
                    'encoding': 'superposition',
                    'entangled_positions': [],
                    'measurement_probabilities': {}
                },
                'quantum_seed': quantum_seed
            })

        return result

    async def _add_player_to_game(
            self,
            db: AsyncSession,
            game_id: UUID,
            user_id: UUID,
            player_name: str,
            *,
            is_host: bool = False,
            join_order: Optional[int] = None
    ) -> GamePlayer:
        """Ajoute un joueur à une partie"""
        if join_order is None:
            join_order = 1

        player_data = {
            'game_id': game_id,
            'user_id': user_id,
            'player_name': player_name,
            'is_host': is_host,
            'join_order': join_order,
            'status': PlayerStatus.JOINED
        }

        return await self.player_repo.create(db, obj_in=player_data)

    async def _validate_attempt(self, guess: List[str]) -> bool:
        """Valide une tentative"""
        if len(guess) != 4:
            return False

        valid_colors = {
            'red', 'blue', 'green', 'yellow',
            'orange', 'purple', 'black', 'white'
        }

        return all(color in valid_colors for color in guess)

    async def _process_attempt(
            self,
            db: AsyncSession,
            game: Game,
            player: GamePlayer,
            attempt_data: AttemptCreate,
            attempt_number: int
    ) -> Dict[str, Any]:
        """Traite une tentative et retourne le résultat"""
        guess = attempt_data.guess
        solution = game.classical_solution

        # Calcul du résultat classique
        blacks = sum(1 for i, color in enumerate(guess) if color == solution[i])
        whites = 0

        # Comptage des couleurs pour les pions blancs
        guess_counts = {}
        solution_counts = {}

        for i, color in enumerate(guess):
            if color != solution[i]:  # Exclure les pions noirs
                guess_counts[color] = guess_counts.get(color, 0) + 1

        for i, color in enumerate(solution):
            if guess[i] != color:  # Exclure les pions noirs
                solution_counts[color] = solution_counts.get(color, 0) + 1

        for color, count in guess_counts.items():
            whites += min(count, solution_counts.get(color, 0))

        # Résultat de base
        result = {
            'blacks': blacks,
            'whites': whites
        }

        is_correct = blacks == 4
        start_time = datetime.utcnow()

        # Traitement quantique si demandé
        quantum_result = None
        if attempt_data.use_quantum_measurement and game.is_quantum_enabled:
            quantum_result = await self._process_quantum_measurement(
                game, attempt_data.measured_position
            )

        # Création de l'enregistrement de tentative
        attempt_dict = {
            'game_id': game.id,
            'player_id': player.id,
            'user_id': player.user_id,
            'attempt_number': attempt_number,
            'guess': guess,
            'result': result,
            'is_correct': is_correct,
            'time_taken': timedelta(seconds=5),  # TODO: Calculer le temps réel
            'measurement_used': attempt_data.use_quantum_measurement,
            'measured_position': attempt_data.measured_position,
            'quantum_result': quantum_result
        }

        attempt = await self.attempt_repo.create(db, obj_in=attempt_dict)

        # Mise à jour des statistiques du joueur
        player.attempts_count += 1
        if attempt_data.use_quantum_measurement:
            player.quantum_measurements_used += 1

        await db.commit()

        return {
            'attempt_id': attempt.id,
            'attempt_number': attempt_number,
            'guess': guess,
            'result': result,
            'is_correct': is_correct,
            'quantum_result': quantum_result,
            'score': self._calculate_attempt_score(result, quantum_result),
            'remaining_attempts': game.max_attempts - attempt_number
        }

    async def _process_quantum_measurement(
            self,
            game: Game,
            position: Optional[int]
    ) -> Dict[str, Any]:
        """Traite une mesure quantique"""
        if position is None or not (0 <= position <= 3):
            return {'error': 'Position de mesure invalide'}

        # Simulation de mesure quantique
        solution = game.classical_solution
        measured_color = solution[position]

        # Ajout de bruit quantique
        confidence = random.uniform(0.7, 0.95)

        return {
            'position': position,
            'measured_color': measured_color,
            'confidence': confidence,
            'quantum_state': 'collapsed',
            'bonus_points': 10
        }

    async def _generate_quantum_hint(
            self,
            game: Game,
            player: GamePlayer,
            hint_type: str,
            position: Optional[int]
    ) -> SolutionHint:
        """Génère un indice quantique"""
        solution = game.classical_solution

        if hint_type == 'grover' and position is not None:
            # Indice Grover pour une position spécifique
            correct_color = solution[position]
            return SolutionHint(
                hint_type=hint_type,
                position=position,
                color=correct_color,
                confidence=0.85,
                cost=50
            )

        elif hint_type == 'measurement':
            # Mesure quantique sur position aléatoire
            pos = random.randint(0, 3)
            return SolutionHint(
                hint_type=hint_type,
                position=pos,
                color=solution[pos],
                confidence=0.90,
                cost=25
            )

        else:
            return SolutionHint(
                hint_type='unknown',
                position=None,
                color=None,
                confidence=0.0,
                cost=0
            )

    def _calculate_attempt_score(
            self,
            result: Dict[str, int],
            quantum_result: Optional[Dict[str, Any]]
    ) -> int:
        """Calcule le score d'une tentative"""
        base_score = result['blacks'] * 10 + result['whites'] * 3

        quantum_bonus = 0
        if quantum_result and quantum_result.get('bonus_points'):
            quantum_bonus = quantum_result['bonus_points']

        return base_score + quantum_bonus

    async def _handle_game_completion(
            self,
            db: AsyncSession,
            game: Game,
            player: GamePlayer,
            won: bool
    ) -> None:
        """Gère la fin de partie pour un joueur"""
        player.finish(won=won)

        # Si c'est le premier à finir et qu'il a gagné, il gagne la partie
        if won and game.winner_id is None:
            game.finish_game(winner_id=player.user_id)

        # En mode solo, finir la partie complètement
        if game.game_mode == GameMode.SOLO:
            game.finish_game(winner_id=player.user_id if won else None)

        await db.commit()


# Instance globale du service
game_service = GameService()