"""
Utilitaires pour le mode multijoueur
Fonctions d'aide pour la gestion des parties, scoring, validation, etc.
"""
import secrets
import string
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from app.models.game import GameStatus
from app.models.multijoueur import PlayerStatus, ItemType, MultiplayerGameType
from app.schemas.multiplayer import PlayerProgress, GameMastermind


class MultiplayerUtils:
    """Classe utilitaire pour les fonctionnalités multijoueur"""

    # =====================================================
    # CONFIGURATION DE DIFFICULTÉ
    # =====================================================

    @staticmethod
    def get_difficulty_config(difficulty: str) -> Dict[str, int]:
        """Récupère la configuration d'une difficulté (cohérent avec le frontend et le solo)"""
        configs = {
            "easy": {"colors": 4, "length": 3, "attempts": 15},
            "medium": {"colors": 6, "length": 4, "attempts": 12},
            "hard": {"colors": 8, "length": 5, "attempts": 10},
            "expert": {"colors": 10, "length": 6, "attempts": 8},
            "quantum": {"colors": 12, "length": 7, "attempts": 6}
        }
        return configs.get(difficulty.lower(), configs["medium"])

    @staticmethod
    def get_difficulty_description(difficulty: str) -> str:
        """Récupère la description d'une difficulté (cohérent avec le frontend)"""
        descriptions = {
            "easy": "Parfait pour débuter - 4 couleurs, 3 positions",
            "medium": "Difficulté standard - 6 couleurs, 4 positions",
            "hard": "Pour les experts - 8 couleurs, 5 positions",
            "expert": "Défi ultime - 10 couleurs, 6 positions",
            "quantum": "Mode quantique - 12 couleurs, 7 positions"
        }
        return descriptions.get(difficulty.lower(), descriptions["medium"])

    # =====================================================
    # GÉNÉRATION DE CODES ET IDENTIFIANTS
    # =====================================================

    @staticmethod
    def generate_room_code(length: int = 6) -> str:
        """Génère un code de room unique"""
        # Utiliser uniquement des lettres majuscules et des chiffres pour éviter la confusion
        chars = string.ascii_uppercase + string.digits
        # Exclure les caractères pouvant être confondus
        chars = chars.replace('0', '').replace('O', '').replace('1', '').replace('I')

        return ''.join(secrets.choice(chars) for _ in range(length))

    @staticmethod
    def generate_player_id() -> str:
        """Génère un ID unique pour un joueur dans une partie"""
        return f"player_{int(time.time())}_{secrets.token_hex(4)}"

    @staticmethod
    def generate_effect_id() -> str:
        """Génère un ID unique pour un effet"""
        return f"effect_{int(time.time())}_{secrets.token_hex(4)}"

    @staticmethod
    def generate_message_id(user_id: str) -> str:
        """Génère un ID unique pour un message de chat"""
        return f"msg_{user_id}_{int(time.time())}_{secrets.token_hex(2)}"

    # =====================================================
    # VALIDATION
    # =====================================================

    @staticmethod
    def validate_room_code(room_code: str) -> bool:
        """Valide le format d'un code de room"""
        if not room_code or not isinstance(room_code, str):
            return False

        # Le code doit faire 6 caractères et contenir uniquement des lettres majuscules et chiffres
        if len(room_code) != 6:
            return False

        allowed_chars = set(string.ascii_uppercase + string.digits) - {'0', 'O', '1', 'I'}
        return all(c in allowed_chars for c in room_code)

    @staticmethod
    def validate_combination(combination: List[int], available_colors: int = None, combination_length: int = None) -> Tuple[bool, Optional[str]]:
        """Valide une combinaison de couleurs selon la configuration de difficulté"""
        if not isinstance(combination, list):
            return False, "La combinaison doit être une liste"

        # Valeurs par défaut si non spécifiées (difficulté medium)
        expected_length = combination_length or 4
        max_colors = available_colors or 6

        if len(combination) != expected_length:
            return False, f"La combinaison doit contenir exactement {expected_length} couleurs"

        for i, color in enumerate(combination):
            if not isinstance(color, int):
                return False, f"La couleur à la position {i+1} doit être un entier"

            if not (1 <= color <= max_colors):
                return False, f"La couleur {color} à la position {i+1} doit être entre 1 et {max_colors}"

        return True, None

    @staticmethod
    def validate_player_action(
        player_status: PlayerStatus,
        action: str,
        game_status: GameStatus
    ) -> Tuple[bool, Optional[str]]:
        """Valide qu'un joueur peut effectuer une action"""

        if game_status not in [GameStatus.IN_PROGRESS, GameStatus.WAITING]:
            return False, "La partie n'est pas en cours"

        if action == "submit_attempt":
            if player_status != PlayerStatus.PLAYING:
                return False, "Vous ne pouvez pas soumettre de tentative actuellement"

        elif action == "use_item":
            if player_status not in [PlayerStatus.PLAYING, PlayerStatus.MASTERMIND_COMPLETE]:
                return False, "Vous ne pouvez pas utiliser d'objet actuellement"

        elif action == "chat":
            if player_status == PlayerStatus.ELIMINATED:
                return False, "Vous ne pouvez pas chatter après élimination"

        return True, None

    # =====================================================
    # CALCULS DE SCORE ET CLASSEMENT
    # =====================================================

    @staticmethod
    def calculate_attempt_score(
        exact_matches: int,
        position_matches: int,
        is_winning: bool,
        attempt_number: int,
        difficulty: str = "medium",
        time_taken: Optional[float] = None,
        quantum_bonus: bool = False
    ) -> int:
        """Calcule le score d'une tentative selon la difficulté"""

        # Récupérer la configuration de difficulté pour le scoring
        difficulty_config = MultiplayerUtils.get_difficulty_config(difficulty)
        max_attempts = difficulty_config["attempts"]
        complexity = difficulty_config["length"] * difficulty_config["colors"]

        # Score de base proportionnel à la complexité
        base_score = int((exact_matches * 20 + position_matches * 8) * (complexity / 24))  # 24 = medium (4*6)

        # Bonus de victoire selon la difficulté
        if is_winning:
            difficulty_multiplier = MultiplayerConfig.DIFFICULTY_SCORE_MULTIPLIERS.get(difficulty, 1.0)
            victory_bonus = int(150 * difficulty_multiplier)
            base_score += victory_bonus

            # Bonus selon le nombre de tentatives (plus c'est rapide, mieux c'est)
            efficiency_ratio = (max_attempts - attempt_number + 1) / max_attempts
            if efficiency_ratio > 0.8:  # Moins de 20% des tentatives utilisées
                base_score += int(80 * difficulty_multiplier)
            elif efficiency_ratio > 0.6:  # Moins de 40% des tentatives utilisées
                base_score += int(50 * difficulty_multiplier)
            elif efficiency_ratio > 0.4:  # Moins de 60% des tentatives utilisées
                base_score += int(25 * difficulty_multiplier)

        # Bonus de vitesse (si temps fourni)
        if time_taken is not None:
            # Seuil de vitesse adapté à la difficulté
            speed_threshold = 20 + (difficulty_config["length"] * 5)  # Plus c'est complexe, plus de temps
            if time_taken < speed_threshold:
                speed_bonus = max(0, int((speed_threshold - time_taken) * 3))
                base_score += speed_bonus

        # Bonus quantique
        if quantum_bonus:
            base_score = int(base_score * 1.3)

        return max(0, base_score)

    @staticmethod
    def calculate_final_standings(players: List[PlayerProgress]) -> List[Dict[str, Any]]:
        """Calcule le classement final d'une partie"""

        # Trier par critères de victoire
        def sort_key(player):
            return (
                -player.completed_masterminds,  # Plus de masterminds complétés = mieux
                -player.score,                  # Plus de points = mieux
                player.total_time,              # Moins de temps = mieux
                player.join_order               # Arrivé plus tôt = mieux en cas d'égalité
            )

        sorted_players = sorted(players, key=sort_key)

        standings = []
        for i, player in enumerate(sorted_players, 1):
            standings.append({
                "position": i,
                "user_id": player.user_id,
                "username": player.username,
                "score": player.score,
                "completed_masterminds": player.completed_masterminds,
                "total_time": player.total_time,
                "attempts_count": player.attempts_count,
                "is_winner": i == 1,
                "is_finished": player.is_finished
            })

        return standings

    @staticmethod
    def calculate_elo_changes(
        winner_elo: int,
        loser_elo: int,
        k_factor: int = 32
    ) -> Tuple[int, int]:
        """Calcule les changements ELO pour une partie 1v1"""

        # Probabilités de victoire
        prob_winner = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
        prob_loser = 1 - prob_winner

        # Nouveaux ratings
        new_winner_elo = winner_elo + k_factor * (1 - prob_winner)
        new_loser_elo = loser_elo + k_factor * (0 - prob_loser)

        return int(new_winner_elo), int(new_loser_elo)

    # =====================================================
    # GESTION DU TEMPS ET DURÉES
    # =====================================================

    @staticmethod
    def estimate_game_duration(
        total_masterminds: int,
        max_players: int,
        difficulty: str,
        quantum_enabled: bool = False
    ) -> int:
        """Estime la durée d'une partie en minutes selon la configuration de difficulté"""

        # Récupérer la configuration de difficulté
        difficulty_config = MultiplayerUtils.get_difficulty_config(difficulty)

        # Temps de base par mastermind selon la complexité de la difficulté
        base_time_map = {
            "easy": 2,     # Simple: 4 couleurs, 3 positions
            "medium": 4,   # Standard: 6 couleurs, 4 positions
            "hard": 6,     # Difficile: 8 couleurs, 5 positions
            "expert": 10,  # Expert: 10 couleurs, 6 positions
            "quantum": 15  # Quantique: 12 couleurs, 7 positions
        }

        base_time = base_time_map.get(difficulty.lower(), 4)

        # Facteur de complexité basé sur les paramètres réels
        complexity_factor = (
            (difficulty_config["length"] / 4) *     # Longueur de combinaison
            (difficulty_config["colors"] / 6) *     # Nombre de couleurs
            (15 / difficulty_config["attempts"])     # Difficulté inverse des tentatives
        )

        # Facteur de joueurs (plus de joueurs = plus long)
        player_factor = 1 + (max_players - 2) * 0.15

        # Facteur quantique (plus complexe)
        quantum_factor = 1.4 if quantum_enabled else 1.0

        # Temps d'attente et de coordination
        coordination_time = 1 + (max_players * 0.5)  # Plus de joueurs = plus de coordination

        total_time = (base_time * total_masterminds * complexity_factor * player_factor * quantum_factor) + coordination_time

        return max(5, int(total_time))  # Minimum 5 minutes

    @staticmethod
    def format_duration(seconds: float) -> str:
        """Formate une durée en secondes en format lisible"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            remaining_seconds = int(seconds % 60)
            return f"{minutes}m {remaining_seconds}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    @staticmethod
    def is_timeout_expired(start_time: datetime, timeout_minutes: int) -> bool:
        """Vérifie si un timeout a expiré"""
        if not start_time:
            return False

        now = datetime.now(timezone.utc)
        elapsed = now - start_time
        return elapsed.total_seconds() > (timeout_minutes * 60)

    # =====================================================
    # GESTION DES OBJETS ET EFFETS
    # =====================================================

    @staticmethod
    def calculate_item_cost(item_type: ItemType, rarity: str = "common") -> int:
        """Calcule le coût d'un objet"""

        base_costs = {
            ItemType.EXTRA_HINT: 30,
            ItemType.TIME_BONUS: 25,
            ItemType.SKIP_MASTERMIND: 100,
            ItemType.DOUBLE_SCORE: 50,
            ItemType.FREEZE_TIME: 40,
            ItemType.ADD_MASTERMIND: 80,
            ItemType.REDUCE_ATTEMPTS: 60,
            ItemType.SCRAMBLE_COLORS: 35
        }

        rarity_multipliers = {
            "common": 1.0,
            "rare": 1.5,
            "epic": 2.0,
            "legendary": 3.0
        }

        base_cost = base_costs.get(item_type, 50)
        multiplier = rarity_multipliers.get(rarity, 1.0)

        return int(base_cost * multiplier)

    @staticmethod
    def get_item_effect_duration(item_type: ItemType) -> Optional[int]:
        """Récupère la durée d'effet d'un objet en secondes"""

        durations = {
            ItemType.TIME_BONUS: 60,      # 1 minute
            ItemType.FREEZE_TIME: 30,     # 30 secondes
            ItemType.SCRAMBLE_COLORS: 45, # 45 secondes
            ItemType.DOUBLE_SCORE: 120,   # 2 minutes
            # Les autres sont instantanés
        }

        return durations.get(item_type)

    @staticmethod
    def can_use_item_on_target(
        item_type: ItemType,
        source_player: str,
        target_player: str,
        target_status: PlayerStatus
    ) -> Tuple[bool, Optional[str]]:
        """Vérifie si un objet peut être utilisé sur une cible"""

        # Objets personnels (bonus)
        if item_type in [ItemType.EXTRA_HINT, ItemType.TIME_BONUS, ItemType.SKIP_MASTERMIND, ItemType.DOUBLE_SCORE]:
            if source_player != target_player:
                return False, "Cet objet ne peut être utilisé que sur soi-même"

        # Objets d'attaque (malus)
        elif item_type in [ItemType.FREEZE_TIME, ItemType.REDUCE_ATTEMPTS, ItemType.SCRAMBLE_COLORS]:
            if source_player == target_player:
                return False, "Cet objet ne peut pas être utilisé sur soi-même"

            if target_status in [PlayerStatus.ELIMINATED, PlayerStatus.FINISHED]:
                return False, "Impossible d'utiliser cet objet sur un joueur éliminé ou terminé"

        return True, None

    # =====================================================
    # UTILITAIRES DE COMMUNICATION
    # =====================================================

    @staticmethod
    def format_websocket_message(
        event_type: str,
        data: Dict[str, Any],
        game_id: str,
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """Formate un message WebSocket standard"""

        return {
            "type": event_type,
            "data": data,
            "timestamp": timestamp or time.time(),
            "game_id": game_id
        }

    @staticmethod
    def sanitize_chat_message(content: str, max_length: int = 500) -> str:
        """Nettoie et valide un message de chat"""

        # Supprime les espaces en début/fin
        content = content.strip()

        # Limite la longueur
        if len(content) > max_length:
            content = content[:max_length]

        # Supprime les caractères de contrôle
        content = ''.join(char for char in content if ord(char) >= 32 or char in '\n\t')

        return content

    @staticmethod
    def mask_sensitive_data(data: Dict[str, Any], player_id: str) -> Dict[str, Any]:
        """Masque les données sensibles selon le contexte du joueur"""

        masked_data = data.copy()

        # Masquer les solutions des masterminds non complétés
        if "masterminds" in masked_data:
            for mastermind in masked_data["masterminds"]:
                if not mastermind.get("is_completed", False):
                    mastermind.pop("solution", None)

        # Masquer les données privées des autres joueurs
        if "players" in masked_data:
            for player in masked_data["players"]:
                if player.get("user_id") != player_id:
                    # Supprimer des données privées si nécessaire
                    player.pop("private_notes", None)

        return masked_data

    # =====================================================
    # STATISTIQUES ET MÉTRIQUES
    # =====================================================

    @staticmethod
    def calculate_player_efficiency(
        attempts_made: int,
        attempts_successful: int,
        time_taken: float,
        masterminds_completed: int
    ) -> float:
        """Calcule l'efficacité d'un joueur (0.0 à 1.0)"""

        if attempts_made == 0:
            return 0.0

        # Ratio de réussite
        success_ratio = attempts_successful / attempts_made

        # Efficacité temporelle (bonus si rapide)
        time_efficiency = max(0, 1 - (time_taken / 3600))  # Normaliser sur 1 heure

        # Bonus de progression
        progress_bonus = masterminds_completed * 0.1

        # Score combiné
        efficiency = (success_ratio * 0.5) + (time_efficiency * 0.3) + (progress_bonus * 0.2)

        return min(1.0, efficiency)

    @staticmethod
    def generate_game_summary(
        game_data: Dict[str, Any],
        final_standings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Génère un résumé de partie"""

        total_duration = game_data.get("total_duration", 0)
        total_players = len(final_standings)

        summary = {
            "game_id": game_data.get("id"),
            "room_code": game_data.get("room_code"),
            "game_type": game_data.get("game_type"),
            "difficulty": game_data.get("difficulty"),
            "duration": MultiplayerUtils.format_duration(total_duration),
            "total_players": total_players,
            "quantum_enabled": game_data.get("quantum_enabled", False),
            "items_enabled": game_data.get("items_enabled", False),
            "winner": final_standings[0] if final_standings else None,
            "completion_rate": len([p for p in final_standings if p.get("is_finished", False)]) / total_players if total_players > 0 else 0,
            "average_score": sum(p.get("score", 0) for p in final_standings) / total_players if total_players > 0 else 0,
            "created_at": game_data.get("created_at"),
            "finished_at": game_data.get("finished_at")
        }

        return summary

    # =====================================================
    # HELPERS POUR LES TESTS
    # =====================================================

    @staticmethod
    def create_mock_player(
        user_id: str = None,
        username: str = None,
        status: PlayerStatus = PlayerStatus.WAITING,
        score: int = 0
    ) -> PlayerProgress:
        """Crée un joueur fictif pour les tests"""

        return PlayerProgress(
            user_id=user_id or MultiplayerUtils.generate_player_id(),
            username=username or f"Player_{secrets.token_hex(2)}",
            status=status,
            score=score,
            current_mastermind=1,
            attempts_count=0,
            completed_masterminds=0,
            items=[],
            active_effects=[],
            is_host=False,
            join_order=0,
            is_finished=False,
            total_time=0.0
        )

    @staticmethod
    def create_mock_mastermind(
        number: int = 1,
        is_current: bool = False,
        is_completed: bool = False
    ) -> GameMastermind:
        """Crée un mastermind fictif pour les tests"""

        return GameMastermind(
            number=number,
            combination_length=4,
            available_colors=6,
            max_attempts=12,
            is_current=is_current,
            is_completed=is_completed,
            completed_by=[]
        )


# =====================================================
# CONSTANTES ET CONFIGURATION
# =====================================================

class MultiplayerConfig:
    """Configuration pour le multijoueur (cohérente avec les configurations de difficulté)"""

    # Limites par défaut basées sur la difficulté MEDIUM
    DEFAULT_MAX_PLAYERS = 12
    MIN_PLAYERS = 2
    MAX_PLAYERS = 50

    # Configuration par difficulté (cohérente avec le frontend)
    DIFFICULTY_CONFIGS = {
        "easy": {"colors": 4, "length": 3, "attempts": 15},
        "medium": {"colors": 6, "length": 4, "attempts": 12},
        "hard": {"colors": 8, "length": 5, "attempts": 10},
        "expert": {"colors": 10, "length": 6, "attempts": 8},
        "quantum": {"colors": 12, "length": 7, "attempts": 6}
    }

    # Limites générales basées sur la difficulté la plus complexe
    DEFAULT_COMBINATION_LENGTH = 4
    MIN_COMBINATION_LENGTH = 3
    MAX_COMBINATION_LENGTH = 7

    DEFAULT_AVAILABLE_COLORS = 6
    MIN_AVAILABLE_COLORS = 4
    MAX_AVAILABLE_COLORS = 12

    DEFAULT_MAX_ATTEMPTS = 12
    MIN_MAX_ATTEMPTS = 6
    MAX_MAX_ATTEMPTS = 15

    DEFAULT_MASTERMINDS = 3
    MIN_MASTERMINDS = 1
    MAX_MASTERMINDS = 10

    # Timeouts
    PLAYER_TIMEOUT_MINUTES = 5
    GAME_CREATION_TIMEOUT_MINUTES = 10
    RECONNECT_TIMEOUT_MINUTES = 2

    # Scoring adapté aux difficultés
    MAX_SCORE_PER_MASTERMIND = 200
    QUANTUM_SCORE_BONUS = 1.2
    SPEED_BONUS_THRESHOLD = 30  # secondes

    # Scoring par difficulté
    DIFFICULTY_SCORE_MULTIPLIERS = {
        "easy": 0.8,
        "medium": 1.0,
        "hard": 1.3,
        "expert": 1.6,
        "quantum": 2.0
    }

    # Items
    MAX_ITEMS_PER_PLAYER = 3
    ITEM_USAGE_COOLDOWN = 30  # secondes

    # Chat
    MAX_CHAT_MESSAGE_LENGTH = 500
    CHAT_RATE_LIMIT = 10  # messages par minute

    # WebSocket
    HEARTBEAT_INTERVAL = 30  # secondes
    MAX_RECONNECT_ATTEMPTS = 5
    PING_INTERVAL = 25  # secondes


# Instance des utilitaires (peut être utilisée directement)
multiplayer_utils = MultiplayerUtils()