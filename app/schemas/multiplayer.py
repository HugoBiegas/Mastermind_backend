"""
Schémas Pydantic pour le mode multijoueur - Version complète
Compatible avec les structures attendues par le frontend React.js
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models.game import GameStatus, Difficulty
from app.models.multijoueur import MultiplayerGameType, ItemType, PlayerStatus


# =====================================================
# ÉNUMÉRATIONS ET TYPES DE BASE
# =====================================================

class QuantumHintType(str, Enum):
    """Types d'indices quantiques pour multijoueur"""
    GROVER = "grover"
    SUPERPOSITION = "superposition"
    ENTANGLEMENT = "entanglement"
    INTERFERENCE = "interference"


# =====================================================
# SCHÉMAS DE REQUÊTE (INPUT)
# =====================================================

class MultiplayerGameCreateRequest(BaseModel):
    """Requête de création de partie multijoueur - Structure exacte attendue par le frontend"""
    model_config = ConfigDict(from_attributes=True)

    # Informations de base
    name: Optional[str] = Field(None, description="Nom de la partie")
    game_type: MultiplayerGameType = Field(..., description="Type de partie multijoueur")
    difficulty: Difficulty = Field(..., description="Difficulté")

    # Configuration des joueurs
    max_players: int = Field(12, ge=2, le=50, description="Nombre maximum de joueurs")
    is_private: bool = Field(False, description="Partie privée")
    password: Optional[str] = Field(None, description="Mot de passe")

    # Options de jeu
    allow_spectators: bool = Field(True, description="Autoriser les spectateurs")
    enable_chat: bool = Field(True, description="Activer le chat")
    items_enabled: bool = Field(True, description="Objets activés")
    quantum_enabled: bool = Field(False, description="Mode quantique")

    # Configuration avancée
    total_masterminds: Optional[int] = Field(3, ge=1, le=10, description="Nombre total de masterminds")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str], info) -> Optional[str]:
        """Valide le mot de passe si la partie est privée"""
        is_private = info.data.get('is_private', False)
        if is_private and not v:
            raise ValueError("Un mot de passe est requis pour les parties privées")
        return v


class JoinGameRequest(BaseModel):
    """Requête pour rejoindre une partie"""
    model_config = ConfigDict(from_attributes=True)

    password: Optional[str] = Field(None, description="Mot de passe")
    as_spectator: Optional[bool] = Field(False, description="Rejoindre en tant que spectateur")


class MultiplayerAttemptRequest(BaseModel):
    """Requête de tentative multijoueur"""
    model_config = ConfigDict(from_attributes=True)

    mastermind_number: int = Field(..., ge=1, description="Numéro du mastermind")
    combination: List[int] = Field(..., description="Combinaison proposée")
    use_quantum_hint: Optional[bool] = Field(False, description="Utiliser un indice quantique")
    hint_type: Optional[QuantumHintType] = Field(None, description="Type d'indice quantique")

    @field_validator('combination')
    @classmethod
    def validate_combination(cls, v: List[int]) -> List[int]:
        """Valide la combinaison"""
        if len(v) != 4:
            raise ValueError("La combinaison doit contenir exactement 4 couleurs")
        if not all(1 <= color <= 6 for color in v):
            raise ValueError("Les couleurs doivent être entre 1 et 6")
        return v


class ItemUseRequest(BaseModel):
    """Requête d'utilisation d'objet"""
    model_config = ConfigDict(from_attributes=True)

    item_type: ItemType = Field(..., description="Type d'objet")
    target_players: Optional[List[str]] = Field(None, description="Joueurs ciblés")
    target_mastermind: Optional[int] = Field(None, description="Mastermind ciblé")
    effect_duration: Optional[int] = Field(None, description="Durée de l'effet en secondes")


class QuantumHintRequest(BaseModel):
    """Requête d'indice quantique multijoueur"""
    model_config = ConfigDict(from_attributes=True)

    hint_type: QuantumHintType = Field(..., description="Type d'indice")
    target_positions: Optional[List[int]] = Field(None, description="Positions ciblées")
    quantum_shots: Optional[int] = Field(1024, ge=100, le=8192, description="Nombre de shots quantiques")
    max_cost: Optional[int] = Field(None, description="Coût maximum acceptable")


class ChatMessageRequest(BaseModel):
    """Requête de message de chat"""
    model_config = ConfigDict(from_attributes=True)

    content: str = Field(..., min_length=1, max_length=500, description="Contenu du message")
    message_type: Optional[str] = Field("text", description="Type de message")


# =====================================================
# SCHÉMAS DE RÉPONSE (OUTPUT)
# =====================================================

class PlayerProgress(BaseModel):
    """Progression d'un joueur - Structure exacte attendue par le frontend"""
    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom d'utilisateur")
    status: PlayerStatus = Field(..., description="Statut du joueur")
    score: int = Field(0, description="Score actuel")
    current_mastermind: int = Field(1, description="Mastermind actuel")
    attempts_count: int = Field(0, description="Nombre de tentatives")
    completed_masterminds: int = Field(0, description="Masterminds complétés")

    # Objets et effets
    items: List[Dict[str, Any]] = Field(default_factory=list, description="Objets possédés")
    active_effects: List[Dict[str, Any]] = Field(default_factory=list, description="Effets actifs")

    # Métadonnées
    is_host: bool = Field(False, description="Est l'hôte")
    join_order: int = Field(0, description="Ordre d'arrivée")
    is_finished: bool = Field(False, description="A terminé la partie")
    finish_time: Optional[str] = Field(None, description="Temps de fin")

    # Temps
    total_time: float = Field(0.0, description="Temps total de jeu")
    average_time_per_attempt: Optional[float] = Field(None, description="Temps moyen par tentative")


class GameMastermind(BaseModel):
    """Mastermind dans une partie"""
    model_config = ConfigDict(from_attributes=True)

    number: int = Field(..., description="Numéro du mastermind")
    combination_length: int = Field(4, description="Longueur de la combinaison")
    available_colors: int = Field(6, description="Nombre de couleurs")
    max_attempts: int = Field(12, description="Tentatives maximum")
    is_current: bool = Field(False, description="Mastermind actuel")
    is_completed: bool = Field(False, description="Mastermind complété")
    completed_by: List[str] = Field(default_factory=list, description="Complété par")

    # Solution (cachée sauf conditions spéciales)
    solution: Optional[List[int]] = Field(None, description="Solution (non exposée)")

    # Timing
    started_at: Optional[str] = Field(None, description="Démarré à")
    completed_at: Optional[str] = Field(None, description="Complété à")


class ActiveEffect(BaseModel):
    """Effet actif sur un joueur"""
    model_config = ConfigDict(from_attributes=True)

    effect_id: str = Field(..., description="ID de l'effet")
    effect_type: ItemType = Field(..., description="Type d'effet")
    source_player: str = Field(..., description="Joueur source")
    target_player: str = Field(..., description="Joueur cible")
    duration_remaining: Optional[int] = Field(None, description="Durée restante en secondes")
    effect_value: Optional[float] = Field(None, description="Valeur de l'effet")
    created_at: str = Field(..., description="Créé à")
    expires_at: Optional[str] = Field(None, description="Expire à")


class MultiplayerGame(BaseModel):
    """Partie multijoueur - Structure exacte attendue par le frontend"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de la room")
    game_type: MultiplayerGameType = Field(..., description="Type de partie")
    difficulty: Difficulty = Field(..., description="Difficulté")
    status: GameStatus = Field(..., description="Statut de la partie")

    # Configuration
    max_players: int = Field(..., description="Joueurs maximum")
    current_players: int = Field(0, description="Joueurs actuels")
    is_private: bool = Field(False, description="Partie privée")
    items_enabled: bool = Field(True, description="Objets activés")
    quantum_enabled: bool = Field(False, description="Mode quantique")
    allow_spectators: bool = Field(True, description="Spectateurs autorisés")
    enable_chat: bool = Field(True, description="Chat activé")

    # Progression
    current_mastermind: int = Field(1, description="Mastermind actuel")
    total_masterminds: int = Field(3, description="Total de masterminds")
    masterminds: List[GameMastermind] = Field(default_factory=list, description="Liste des masterminds")

    # Participants
    players: List[PlayerProgress] = Field(default_factory=list, description="Liste des joueurs")
    spectators: List[Dict[str, Any]] = Field(default_factory=list, description="Spectateurs")

    # Créateur
    creator: Dict[str, str] = Field(..., description="Créateur de la partie")

    # Timestamps
    created_at: str = Field(..., description="Date de création")
    started_at: Optional[str] = Field(None, description="Date de début")
    finished_at: Optional[str] = Field(None, description="Date de fin")
    estimated_finish: Optional[str] = Field(None, description="Fin estimée")

    # Jeu de base (pour compatibilité avec le frontend)
    base_game: Optional[Dict[str, Any]] = Field(None, description="Jeu de base")

    # Effets actifs
    active_effects: List[ActiveEffect] = Field(default_factory=list, description="Effets actifs")


class PublicGameListing(BaseModel):
    """Listing public des parties pour le lobby"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de la room")
    name: Optional[str] = Field(None, description="Nom de la partie")
    game_type: MultiplayerGameType = Field(..., description="Type de partie")
    difficulty: Difficulty = Field(..., description="Difficulté")
    status: GameStatus = Field(..., description="Statut")

    # Compteurs
    current_players: int = Field(..., description="Joueurs actuels")
    max_players: int = Field(..., description="Joueurs maximum")

    # Configuration visible
    is_private: bool = Field(..., description="Partie privée")
    quantum_enabled: bool = Field(..., description="Mode quantique")
    items_enabled: bool = Field(..., description="Objets activés")

    # Créateur
    creator: Dict[str, str] = Field(..., description="Créateur")

    # Timing
    created_at: str = Field(..., description="Date de création")
    estimated_duration: Optional[int] = Field(None, description="Durée estimée en minutes")


class MultiplayerAttemptResponse(BaseModel):
    """Réponse de tentative multijoueur"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="ID de la tentative")
    mastermind_number: int = Field(..., description="Numéro du mastermind")
    combination: List[int] = Field(..., description="Combinaison soumise")
    exact_matches: int = Field(..., description="Correspondances exactes")
    position_matches: int = Field(..., description="Correspondances de position")
    is_winning: bool = Field(..., description="Tentative gagnante")
    score: int = Field(..., description="Score obtenu")
    attempt_number: int = Field(..., description="Numéro de la tentative")

    # Quantique
    quantum_calculated: bool = Field(False, description="Calculé quantiquement")
    quantum_probabilities: Optional[Dict[str, Any]] = Field(None, description="Probabilités quantiques")
    quantum_hint_used: bool = Field(False, description="Indice quantique utilisé")

    # Statut du joueur après la tentative
    player_status: PlayerStatus = Field(..., description="Statut du joueur")

    # Timing
    time_taken: Optional[float] = Field(None, description="Temps pris pour la tentative")
    timestamp: str = Field(..., description="Timestamp de la tentative")


class QuantumHintResponse(BaseModel):
    """Réponse d'indice quantique multijoueur"""
    model_config = ConfigDict(from_attributes=True)

    hint_type: str = Field(..., description="Type d'indice utilisé")
    hint_data: Dict[str, Any] = Field(..., description="Données de l'indice")
    quantum_probability: float = Field(..., description="Probabilité quantique")
    cost: int = Field(..., description="Coût de l'indice")
    success: bool = Field(..., description="Succès de l'opération")

    # Métadonnées
    algorithm_used: Optional[str] = Field(None, description="Algorithme utilisé")
    execution_time: Optional[float] = Field(None, description="Temps d'exécution")
    error_message: Optional[str] = Field(None, description="Message d'erreur")


# =====================================================
# SCHÉMAS D'ÉVÉNEMENTS WEBSOCKET
# =====================================================

class WebSocketEventBase(BaseModel):
    """Base pour tous les événements WebSocket"""
    model_config = ConfigDict(from_attributes=True)

    type: str = Field(..., description="Type d'événement")
    data: Dict[str, Any] = Field(..., description="Données de l'événement")
    timestamp: float = Field(..., description="Timestamp de l'événement")
    game_id: str = Field(..., description="ID de la partie")


class PlayerJoinedEvent(BaseModel):
    """Événement : joueur rejoint"""
    model_config = ConfigDict(from_attributes=True)

    username: str = Field(..., description="Nom d'utilisateur")
    players_count: int = Field(..., description="Nombre de joueurs")
    player_data: PlayerProgress = Field(..., description="Données du joueur")


class PlayerLeftEvent(BaseModel):
    """Événement : joueur quitte"""
    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom d'utilisateur")
    players_count: int = Field(..., description="Nombre de joueurs")
    reason: Optional[str] = Field(None, description="Raison du départ")


class GameStartedEvent(BaseModel):
    """Événement : partie démarrée"""
    model_config = ConfigDict(from_attributes=True)

    game_id: str = Field(..., description="ID de la partie")
    current_mastermind: int = Field(..., description="Mastermind actuel")
    total_masterminds: int = Field(..., description="Total masterminds")
    started_at: float = Field(..., description="Timestamp de démarrage")


class AttemptMadeEvent(BaseModel):
    """Événement : tentative effectuée"""
    model_config = ConfigDict(from_attributes=True)

    player_id: str = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom d'utilisateur")
    mastermind_number: int = Field(..., description="Numéro du mastermind")
    attempt_result: MultiplayerAttemptResponse = Field(..., description="Résultat de la tentative")
    is_winning: bool = Field(..., description="Tentative gagnante")


class ItemUsedEvent(BaseModel):
    """Événement : objet utilisé"""
    model_config = ConfigDict(from_attributes=True)

    player_id: str = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom d'utilisateur")
    item_type: ItemType = Field(..., description="Type d'objet")
    target_players: Optional[List[str]] = Field(None, description="Joueurs ciblés")
    effects: List[ActiveEffect] = Field(default_factory=list, description="Effets appliqués")


class GameFinishedEvent(BaseModel):
    """Événement : partie terminée"""
    model_config = ConfigDict(from_attributes=True)

    game_id: str = Field(..., description="ID de la partie")
    winner: Optional[str] = Field(None, description="Gagnant")
    final_standings: List[PlayerProgress] = Field(..., description="Classement final")
    game_stats: Dict[str, Any] = Field(..., description="Statistiques de la partie")
    finished_at: float = Field(..., description="Timestamp de fin")


class ChatMessageEvent(BaseModel):
    """Événement : message de chat"""
    model_config = ConfigDict(from_attributes=True)

    message_id: str = Field(..., description="ID du message")
    player_id: str = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom d'utilisateur")
    content: str = Field(..., description="Contenu du message")
    message_type: str = Field("text", description="Type de message")
    sent_at: float = Field(..., description="Timestamp d'envoi")


class ErrorEvent(BaseModel):
    """Événement : erreur"""
    model_config = ConfigDict(from_attributes=True)

    message: str = Field(..., description="Message d'erreur")
    code: Optional[str] = Field(None, description="Code d'erreur")
    user_id: str = Field(..., description="ID de l'utilisateur concerné")


# =====================================================
# STRUCTURE DE RÉPONSE API STANDARDISÉE
# =====================================================

class MultiplayerApiResponse(BaseModel):
    """Réponse API standardisée pour le multijoueur"""
    model_config = ConfigDict(from_attributes=True)

    success: bool = Field(..., description="Succès de l'opération")
    data: Any = Field(..., description="Données de réponse")
    message: Optional[str] = Field(None, description="Message informatif")
    error: Optional[str] = Field(None, description="Message d'erreur")
    timestamp: str = Field(..., description="Timestamp de la réponse")


class PaginatedResponse(BaseModel):
    """Réponse paginée"""
    model_config = ConfigDict(from_attributes=True)

    items: List[Any] = Field(..., description="Éléments de la page")
    total: int = Field(..., description="Total d'éléments")
    page: int = Field(..., description="Page actuelle")
    per_page: int = Field(..., description="Éléments par page")
    pages: int = Field(..., description="Nombre total de pages")
    has_next: bool = Field(..., description="Page suivante disponible")
    has_prev: bool = Field(..., description="Page précédente disponible")


class GameStats(BaseModel):
    """Statistiques de partie"""
    model_config = ConfigDict(from_attributes=True)

    total_duration: float = Field(..., description="Durée totale en secondes")
    total_attempts: int = Field(..., description="Total de tentatives")
    average_attempts_per_player: float = Field(..., description="Moyenne de tentatives par joueur")
    quantum_hints_used: int = Field(0, description="Indices quantiques utilisés")
    items_used: int = Field(0, description="Objets utilisés")
    effects_applied: int = Field(0, description="Effets appliqués")
    chat_messages: int = Field(0, description="Messages de chat")


class PlayerGameStats(BaseModel):
    """Statistiques d'un joueur pour une partie"""
    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom d'utilisateur")
    final_score: int = Field(..., description="Score final")
    final_position: int = Field(..., description="Position finale")
    total_attempts: int = Field(..., description="Total de tentatives")
    successful_attempts: int = Field(..., description="Tentatives réussies")
    quantum_hints_used: int = Field(0, description="Indices quantiques utilisés")
    items_used: int = Field(0, description="Objets utilisés")
    average_time_per_attempt: float = Field(..., description="Temps moyen par tentative")
    total_time: float = Field(..., description="Temps total de jeu")


# =====================================================
# SCHÉMAS DE VALIDATION
# =====================================================

class RoomCodeValidation(BaseModel):
    """Validation d'un code de room"""
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool = Field(..., description="Code valide")
    exists: bool = Field(..., description="Room existe")
    is_joinable: bool = Field(..., description="Peut être rejoint")
    requires_password: bool = Field(..., description="Mot de passe requis")
    current_players: int = Field(..., description="Joueurs actuels")
    max_players: int = Field(..., description="Joueurs maximum")
    status: GameStatus = Field(..., description="Statut de la partie")


class PlayerValidation(BaseModel):
    """Validation d'un joueur"""
    model_config = ConfigDict(from_attributes=True)

    can_join: bool = Field(..., description="Peut rejoindre")
    can_spectate: bool = Field(..., description="Peut observer")
    already_in_game: bool = Field(..., description="Déjà dans une partie")
    reason: Optional[str] = Field(None, description="Raison si refusé")


# =====================================================
# EXPORTS
# =====================================================

__all__ = [
    # Requêtes
    "MultiplayerGameCreateRequest", "JoinGameRequest", "MultiplayerAttemptRequest",
    "ItemUseRequest", "QuantumHintRequest", "ChatMessageRequest",

    # Réponses principales
    "PlayerProgress", "GameMastermind", "MultiplayerGame", "PublicGameListing",
    "MultiplayerAttemptResponse", "QuantumHintResponse",

    # Événements WebSocket
    "WebSocketEventBase", "PlayerJoinedEvent", "PlayerLeftEvent", "GameStartedEvent",
    "AttemptMadeEvent", "ItemUsedEvent", "GameFinishedEvent", "ChatMessageEvent", "ErrorEvent",

    # Structures communes
    "ActiveEffect", "MultiplayerApiResponse", "PaginatedResponse",
    "GameStats", "PlayerGameStats",

    # Validation
    "RoomCodeValidation", "PlayerValidation",

    # Énumérations
    "QuantumHintType"
]