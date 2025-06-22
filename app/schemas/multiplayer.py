"""
Schémas Pydantic pour le multijoueur - Version complète pour cohérence avec le frontend
Tous les types attendus par le frontend React.js sont définis
COMPLET: Synchronisation parfaite avec les types TypeScript du frontend
"""
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ConfigDict


# =====================================================
# SCHÉMAS DE REQUÊTE (INPUT)
# =====================================================

class MultiplayerGameCreateRequest(BaseModel):
    """Requête de création d'une partie multijoueur"""
    model_config = ConfigDict(from_attributes=True)

    # Configuration de base
    game_type: str = Field(default="multi_mastermind", description="Type de partie")
    difficulty: str = Field(default="medium", description="Difficulté")
    max_players: int = Field(default=4, ge=2, le=8, description="Nombre max de joueurs")

    # Configuration du mastermind
    combination_length: int = Field(default=4, ge=3, le=8, description="Longueur de la combinaison")
    available_colors: int = Field(default=6, ge=3, le=15, description="Couleurs disponibles")
    max_attempts: int = Field(default=10, ge=5, le=20, description="Tentatives maximum")

    # Configuration multijoueur
    total_masterminds: int = Field(default=3, ge=1, le=10, description="Nombre de masterminds")

    # Options avancées
    quantum_enabled: bool = Field(default=False, description="Activer les fonctionnalités quantiques")
    items_enabled: bool = Field(default=True, description="Activer les objets")
    items_per_mastermind: int = Field(default=1, ge=0, le=3, description="Objets par mastermind")

    # Visibilité
    is_public: bool = Field(default=True, description="Partie publique")
    password: Optional[str] = Field(None, description="Mot de passe (optionnel)")

    # Solution personnalisée (optionnelle)
    solution: Optional[List[int]] = Field(None, description="Solution personnalisée")


class JoinGameRequest(BaseModel):
    """Requête pour rejoindre une partie"""
    model_config = ConfigDict(from_attributes=True)

    password: Optional[str] = Field(None, description="Mot de passe de la partie")
    as_spectator: bool = Field(default=False, description="Rejoindre en tant que spectateur")


class MultiplayerAttemptRequest(BaseModel):
    """Requête de soumission d'une tentative"""
    model_config = ConfigDict(from_attributes=True)

    combination: List[int] = Field(..., description="Combinaison proposée")
    mastermind_number: int = Field(default=1, description="Numéro du mastermind")
    time_taken: Optional[int] = Field(None, description="Temps pris en millisecondes")
    quantum_data: Optional[Dict[str, Any]] = Field(None, description="Données quantiques")


class ItemUseRequest(BaseModel):
    """Requête d'utilisation d'un objet"""
    model_config = ConfigDict(from_attributes=True)

    item_type: str = Field(..., description="Type d'objet à utiliser")
    target_user_id: Optional[str] = Field(None, description="Utilisateur cible (pour objets offensifs)")
    mastermind_number: Optional[int] = Field(None, description="Mastermind cible")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Paramètres additionnels")


class QuantumHintRequest(BaseModel):
    """Requête d'indice quantique"""
    model_config = ConfigDict(from_attributes=True)

    hint_type: str = Field(..., description="Type d'indice quantique")
    mastermind_number: int = Field(default=1, description="Numéro du mastermind")
    current_attempt: Optional[List[int]] = Field(None, description="Tentative actuelle")
    previous_attempts: Optional[List[List[int]]] = Field(None, description="Tentatives précédentes")


# =====================================================
# SCHÉMAS DE RÉPONSE (OUTPUT)
# =====================================================

class GameRoom(BaseModel):
    """Informations sur une room de jeu"""
    model_config = ConfigDict(from_attributes=True)

    # Identifiants
    room_code: str = Field(..., description="Code de la room")
    game_id: str = Field(..., description="ID de la partie de base")
    multiplayer_game_id: Optional[str] = Field(None, description="ID de la partie multijoueur")

    # Créateur
    creator: Optional[Dict[str, Any]] = Field(None, description="Informations du créateur")

    # Configuration
    status: str = Field(..., description="Status de la partie")
    game_type: str = Field(..., description="Type de partie multijoueur")
    difficulty: str = Field(..., description="Difficulté")

    # Paramètres de jeu
    max_players: int = Field(..., description="Nombre max de joueurs")
    players_count: int = Field(..., description="Nombre actuel de joueurs")
    total_masterminds: int = Field(..., description="Nombre total de masterminds")
    current_mastermind: int = Field(default=1, description="Mastermind actuel")

    # Options
    quantum_enabled: bool = Field(..., description="Quantique activé")
    items_enabled: bool = Field(default=True, description="Objets activés")
    has_password: bool = Field(default=False, description="Partie protégée par mot de passe")
    is_public: bool = Field(default=True, description="Partie publique")

    # Timestamps
    created_at: str = Field(..., description="Date de création")
    started_at: Optional[str] = Field(None, description="Date de démarrage")
    finished_at: Optional[str] = Field(None, description="Date de fin")

    # Joueurs
    players: Optional[List[Dict[str, Any]]] = Field(None, description="Liste des joueurs")


class PlayerProgress(BaseModel):
    """Progression d'un joueur"""
    model_config = ConfigDict(from_attributes=True)

    # Identifiants
    user_id: str = Field(..., description="ID de l'utilisateur")
    username: str = Field(..., description="Nom d'utilisateur")

    # Status
    status: str = Field(..., description="Status du joueur")
    is_finished: bool = Field(default=False, description="Joueur terminé")

    # Progression
    current_mastermind: int = Field(default=1, description="Mastermind actuel")
    completed_masterminds: int = Field(default=0, description="Masterminds complétés")

    # Scores
    total_score: int = Field(default=0, description="Score total")
    total_time: float = Field(default=0.0, description="Temps total")

    # Position
    finish_position: Optional[int] = Field(None, description="Position finale")
    finish_time: Optional[str] = Field(None, description="Temps de fin")

    # Objets
    collected_items: List[str] = Field(default_factory=list, description="Objets collectés")
    used_items: List[str] = Field(default_factory=list, description="Objets utilisés")


class AttemptResult(BaseModel):
    """Résultat d'une tentative"""
    model_config = ConfigDict(from_attributes=True)

    # Tentative
    attempt_number: int = Field(..., description="Numéro de la tentative")
    combination: List[int] = Field(..., description="Combinaison proposée")

    # Résultats
    exact_matches: int = Field(..., description="Correspondances exactes")
    position_matches: int = Field(..., description="Correspondances de couleur")
    is_winning: bool = Field(..., description="Tentative gagnante")

    # Score
    score: int = Field(..., description="Score de la tentative")
    total_score: int = Field(..., description="Score total du joueur")

    # Progression
    completed_masterminds: int = Field(..., description="Masterminds complétés")
    is_finished: bool = Field(default=False, description="Joueur terminé")

    # Timing
    time_taken: Optional[int] = Field(None, description="Temps pris")

    # Données quantiques
    quantum_data: Optional[Dict[str, Any]] = Field(None, description="Données quantiques")


class GameResults(BaseModel):
    """Résultats finaux d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    # Identifiants
    room_code: str = Field(..., description="Code de la room")
    game_id: str = Field(..., description="ID de la partie")

    # Status
    status: str = Field(..., description="Status final")
    finished_at: Optional[str] = Field(None, description="Date de fin")

    # Classement
    rankings: List[Dict[str, Any]] = Field(..., description="Classement final")

    # Statistiques globales
    game_stats: Dict[str, Any] = Field(..., description="Statistiques de la partie")

    # Détails des masterminds
    masterminds_results: Optional[List[Dict[str, Any]]] = Field(None, description="Résultats par mastermind")


class LobbyFilters(BaseModel):
    """Filtres pour le lobby"""
    model_config = ConfigDict(from_attributes=True)

    status: Optional[str] = Field(None, description="Status des parties")
    difficulty: Optional[str] = Field(None, description="Difficulté")
    game_type: Optional[str] = Field(None, description="Type de jeu")
    quantum_enabled: Optional[bool] = Field(None, description="Quantique activé")
    has_password: Optional[bool] = Field(None, description="Avec mot de passe")
    search_term: Optional[str] = Field(None, description="Terme de recherche")
    min_players: Optional[int] = Field(None, description="Minimum de joueurs")
    max_players: Optional[int] = Field(None, description="Maximum de joueurs")


class LobbyListResponse(BaseModel):
    """Réponse de la liste du lobby"""
    model_config = ConfigDict(from_attributes=True)

    rooms: List[GameRoom] = Field(..., description="Liste des rooms")
    pagination: Dict[str, Any] = Field(..., description="Informations de pagination")
    filters_applied: Optional[Dict[str, Any]] = Field(None, description="Filtres appliqués")


# =====================================================
# SCHÉMAS POUR WEBSOCKETS
# =====================================================

class WebSocketMessage(BaseModel):
    """Message WebSocket générique"""
    model_config = ConfigDict(from_attributes=True)

    type: str = Field(..., description="Type de message")
    data: Dict[str, Any] = Field(..., description="Données du message")
    timestamp: str = Field(..., description="Timestamp du message")
    user_id: Optional[str] = Field(None, description="ID de l'utilisateur")


class PlayerJoinedMessage(BaseModel):
    """Message de joueur qui rejoint"""
    model_config = ConfigDict(from_attributes=True)

    type: str = Field(default="player_joined", description="Type de message")
    user_id: str = Field(..., description="ID du joueur")
    username: str = Field(..., description="Nom du joueur")
    is_spectator: bool = Field(default=False, description="Spectateur")
    players_count: int = Field(..., description="Nombre total de joueurs")


class PlayerLeftMessage(BaseModel):
    """Message de joueur qui quitte"""
    model_config = ConfigDict(from_attributes=True)

    type: str = Field(default="player_left", description="Type de message")
    user_id: str = Field(..., description="ID du joueur")
    players_count: int = Field(..., description="Nombre total de joueurs")


class GameStartedMessage(BaseModel):
    """Message de démarrage de partie"""
    model_config = ConfigDict(from_attributes=True)

    type: str = Field(default="game_started", description="Type de message")
    started_at: str = Field(..., description="Timestamp de démarrage")
    current_mastermind: int = Field(default=1, description="Mastermind actuel")


class AttemptSubmittedMessage(BaseModel):
    """Message de tentative soumise"""
    model_config = ConfigDict(from_attributes=True)

    type: str = Field(default="attempt_submitted", description="Type de message")
    user_id: str = Field(..., description="ID du joueur")
    mastermind_number: int = Field(..., description="Numéro du mastermind")
    is_winning: bool = Field(..., description="Tentative gagnante")
    score: int = Field(..., description="Score obtenu")


class ChatMessage(BaseModel):
    """Message de chat"""
    model_config = ConfigDict(from_attributes=True)

    type: str = Field(default="chat_message", description="Type de message")
    user_id: str = Field(..., description="ID de l'expéditeur")
    username: str = Field(..., description="Nom de l'expéditeur")
    message: str = Field(..., description="Contenu du message")
    timestamp: str = Field(..., description="Timestamp")


# =====================================================
# SCHÉMAS POUR LES OBJETS ET EFFETS
# =====================================================

class GameItem(BaseModel):
    """Objet de jeu"""
    model_config = ConfigDict(from_attributes=True)

    item_type: str = Field(..., description="Type d'objet")
    name: str = Field(..., description="Nom de l'objet")
    description: str = Field(..., description="Description")
    rarity: str = Field(..., description="Rareté")
    is_offensive: bool = Field(..., description="Objet offensif")
    duration_seconds: Optional[int] = Field(None, description="Durée d'effet")
    effect_value: Optional[int] = Field(None, description="Valeur d'effet")


class EffectApplication(BaseModel):
    """Application d'un effet"""
    model_config = ConfigDict(from_attributes=True)

    effect_type: str = Field(..., description="Type d'effet")
    target_user_id: str = Field(..., description="Utilisateur cible")
    source_user_id: str = Field(..., description="Utilisateur source")
    duration_seconds: Optional[int] = Field(None, description="Durée")
    effect_value: Optional[int] = Field(None, description="Valeur")
    applied_at: str = Field(..., description="Timestamp d'application")


# =====================================================
# SCHÉMAS D'ERREUR PERSONNALISÉS
# =====================================================

class MultiplayerError(BaseModel):
    """Erreur multijoueur"""
    model_config = ConfigDict(from_attributes=True)

    error_type: str = Field(..., description="Type d'erreur")
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


# =====================================================
# SCHÉMAS DE STATISTIQUES
# =====================================================

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
    perfect_solutions: int = Field(0, description="Solutions parfaites")
    average_time_per_attempt: float = Field(0.0, description="Temps moyen par tentative")
    quantum_hints_used: int = Field(0, description="Indices quantiques utilisés")
    items_collected: int = Field(0, description="Objets collectés")
    items_used: int = Field(0, description="Objets utilisés")


# =====================================================
# SCHÉMAS POUR L'INTÉGRATION QUANTIQUE
# =====================================================

class QuantumHintResponse(BaseModel):
    """Réponse d'indice quantique"""
    model_config = ConfigDict(from_attributes=True)

    hint_type: str = Field(..., description="Type d'indice")
    cost: int = Field(..., description="Coût en points")
    result: Dict[str, Any] = Field(..., description="Résultat de l'indice")
    quantum_data: Dict[str, Any] = Field(..., description="Données quantiques brutes")
    success: bool = Field(..., description="Succès de l'opération")
    message: Optional[str] = Field(None, description="Message explicatif")


class QuantumSimulationRequest(BaseModel):
    """Requête de simulation quantique"""
    model_config = ConfigDict(from_attributes=True)

    circuit_type: str = Field(..., description="Type de circuit quantique")
    qubits: int = Field(..., description="Nombre de qubits")
    parameters: Dict[str, Any] = Field(..., description="Paramètres de simulation")
    shots: int = Field(default=1024, description="Nombre de mesures")


class QuantumSimulationResponse(BaseModel):
    """Réponse de simulation quantique"""
    model_config = ConfigDict(from_attributes=True)

    circuit_type: str = Field(..., description="Type de circuit")
    results: Dict[str, Any] = Field(..., description="Résultats de simulation")
    execution_time: float = Field(..., description="Temps d'exécution")
    backend_used: str = Field(..., description="Backend utilisé")
    success: bool = Field(..., description="Succès de la simulation")


# =====================================================
# TYPES UNION POUR FLEXIBILITÉ
# =====================================================

# Messages WebSocket unis
WebSocketMessageUnion = Union[
    PlayerJoinedMessage,
    PlayerLeftMessage,
    GameStartedMessage,
    AttemptSubmittedMessage,
    ChatMessage,
    WebSocketMessage
]

# Réponses API unies
ApiResponseUnion = Union[
    MultiplayerApiResponse,
    PaginatedResponse,
    Dict[str, Any]
]