"""
Schémas Pydantic pour la gestion des jeux
CORRECTION: Synchronisé avec les modèles SQLAlchemy
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, validator

from app.models.game import GameType, GameMode, GameStatus, Difficulty, ParticipationStatus


# === SCHÉMAS DE BASE ===

class GameCreate(BaseModel):
    """Schéma pour créer une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_type: GameType = Field(default=GameType.CLASSIC, description="Type de jeu")
    game_mode: GameMode = Field(default=GameMode.SINGLE, description="Mode de jeu")
    difficulty: Difficulty = Field(default=Difficulty.MEDIUM, description="Difficulté")

    max_attempts: Optional[int] = Field(default=12, ge=1, le=50, description="Tentatives max")
    time_limit: Optional[int] = Field(default=None, ge=60, le=3600, description="Limite de temps (secondes)")
    max_players: int = Field(default=1, ge=1, le=8, description="Joueurs max")

    is_private: bool = Field(default=False, description="Partie privée")
    password: Optional[str] = Field(default=None, min_length=1, max_length=50, description="Mot de passe")
    room_code: Optional[str] = Field(default=None, min_length=4, max_length=10, description="Code personnalisé")

    allow_spectators: bool = Field(default=True, description="Autoriser les spectateurs")
    enable_chat: bool = Field(default=True, description="Activer le chat")
    quantum_enabled: bool = Field(default=False, description="Fonctionnalités quantiques")

    settings: Optional[Dict[str, Any]] = Field(default=None, description="Paramètres avancés")


class GameJoin(BaseModel):
    """Schéma pour rejoindre une partie"""
    model_config = ConfigDict(from_attributes=True)

    password: Optional[str] = Field(default=None, description="Mot de passe de la partie")
    player_name: Optional[str] = Field(default=None, max_length=50, description="Nom d'affichage")


class GameUpdate(BaseModel):
    """Schéma pour modifier une partie"""
    model_config = ConfigDict(from_attributes=True)

    max_attempts: Optional[int] = Field(default=None, ge=1, le=50, description="Tentatives max")
    time_limit: Optional[int] = Field(default=None, ge=60, le=3600, description="Limite de temps")
    is_private: Optional[bool] = Field(default=None, description="Partie privée")
    password: Optional[str] = Field(default=None, description="Mot de passe")
    allow_spectators: Optional[bool] = Field(default=None, description="Autoriser spectateurs")
    enable_chat: Optional[bool] = Field(default=None, description="Activer chat")
    settings: Optional[Dict[str, Any]] = Field(default=None, description="Paramètres")


def validate_combination(v):
    """Valide la combinaison"""
    if not all(isinstance(x, int) and 1 <= x <= 10 for x in v):
        raise ValueError("Chaque couleur doit être un entier entre 1 et 10")
    return v


class AttemptCreate(BaseModel):
    """Schéma pour créer une tentative"""
    model_config = ConfigDict(from_attributes=True)

    combination: List[int] = Field(..., description="Combinaison proposée")
    use_quantum_hint: bool = Field(default=False, description="Utiliser un hint quantique")
    hint_type: Optional[str] = Field(default=None, description="Type de hint quantique")


# === SCHÉMAS D'INFORMATION ===

class ParticipantInfo(BaseModel):
    """Information sur un participant - CORRECTION: player_id au lieu de user_id"""
    model_config = ConfigDict(from_attributes=True)

    # CORRECTION: Mapping depuis player_id vers user_id pour l'API
    user_id: UUID = Field(..., description="ID de l'utilisateur", alias="player_id")
    username: str = Field(..., description="Nom d'utilisateur")
    avatar_url: Optional[str] = Field(None, description="Avatar")
    status: ParticipationStatus = Field(..., description="Statut de participation")
    score: int = Field(default=0, description="Score dans cette partie")
    attempts_made: int = Field(default=0, description="Tentatives utilisées", alias="attempts_made")
    is_ready: bool = Field(default=False, description="Prêt à jouer")
    role: str = Field(default="player", description="Rôle dans la partie")
    is_winner: bool = Field(default=False, description="Est le gagnant")
    join_order: int = Field(..., description="Ordre d'arrivée")

    # Ajout des champs manquants du modèle
    quantum_hints_used: int = Field(default=0, description="Hints quantiques utilisés")
    time_taken: Optional[int] = Field(None, description="Temps pris (secondes)")
    joined_at: datetime = Field(..., description="Date de participation")

    @classmethod
    def from_participation(cls, participation):
        """Crée un ParticipantInfo depuis une GameParticipation"""
        return cls(
            player_id=participation.player_id,  # Sera mappé vers user_id
            username=participation.player.username,
            avatar_url=participation.player.avatar_url,
            status=participation.status,
            score=participation.score,
            attempts_made=participation.attempts_made,
            is_ready=participation.is_ready,
            role=participation.role,
            is_winner=participation.is_winner,
            join_order=participation.join_order,
            quantum_hints_used=participation.quantum_hints_used,
            time_taken=participation.time_taken,
            joined_at=participation.joined_at
        )


class AttemptInfo(BaseModel):
    """Information sur une tentative - CORRECTION: player_id au lieu de user_id"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la tentative")
    attempt_number: int = Field(..., description="Numéro de tentative")
    # CORRECTION: Mapping depuis player_id vers user_id pour l'API
    user_id: UUID = Field(..., description="ID de l'utilisateur", alias="player_id")
    combination: List[int] = Field(..., description="Combinaison proposée")
    correct_positions: int = Field(..., description="Positions correctes")
    correct_colors: int = Field(..., description="Couleurs correctes")
    is_correct: bool = Field(..., description="Tentative gagnante", alias="is_correct")
    attempt_score: int = Field(default=0, description="Score de la tentative")
    time_taken: Optional[int] = Field(None, description="Temps pris (ms)")
    used_quantum_hint: bool = Field(default=False, description="Hint quantique utilisé")
    hint_type: Optional[str] = Field(None, description="Type de hint")
    created_at: datetime = Field(..., description="Horodatage", alias="created_at")

    # Propriété calculée pour la compatibilité
    @property
    def timestamp(self) -> datetime:
        """Alias pour created_at"""
        return self.created_at

    @property
    def is_winning(self) -> bool:
        """Alias pour is_correct"""
        return self.is_correct


class GameInfo(BaseModel):
    """Informations de base d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de la room")
    game_type: GameType = Field(..., description="Type de jeu")
    game_mode: GameMode = Field(..., description="Mode de jeu")
    status: GameStatus = Field(..., description="Statut")
    difficulty: Difficulty = Field(..., description="Difficulté")

    max_attempts: Optional[int] = Field(None, description="Tentatives max")
    time_limit: Optional[int] = Field(None, description="Limite de temps")
    max_players: int = Field(..., description="Joueurs max")
    current_players: int = Field(..., description="Joueurs actuels")

    is_private: bool = Field(..., description="Partie privée")
    quantum_enabled: bool = Field(..., description="Quantique activé")

    creator_id: UUID = Field(..., description="ID du créateur")
    created_at: datetime = Field(..., description="Date de création")
    started_at: Optional[datetime] = Field(None, description="Date de début")
    finished_at: Optional[datetime] = Field(None, description="Date de fin")


class GamePublic(BaseModel):
    """Vue publique d'une partie (pour la recherche)"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de room")
    game_type: GameType = Field(..., description="Type de jeu")
    game_mode: GameMode = Field(..., description="Mode de jeu")
    status: GameStatus = Field(..., description="Statut")
    difficulty: Difficulty = Field(..., description="Difficulté")

    current_players: int = Field(..., description="Joueurs actuels")
    max_players: int = Field(..., description="Max joueurs")

    created_at: datetime = Field(..., description="Date de création")
    creator_username: str = Field(..., description="Créateur")
    is_joinable: bool = Field(..., description="Peut être rejoint")


class GameFull(BaseModel):
    """Vue complète d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    # Informations de base
    id: UUID = Field(..., description="ID de la partie")
    room_code: str = Field(..., description="Code de room")
    game_type: GameType = Field(..., description="Type de jeu")
    game_mode: GameMode = Field(..., description="Mode de jeu")
    status: GameStatus = Field(..., description="Statut")
    difficulty: Difficulty = Field(..., description="Difficulté")

    # Paramètres
    combination_length: int = Field(..., description="Longueur de la combinaison")
    available_colors: int = Field(..., description="Couleurs disponibles")
    max_attempts: Optional[int] = Field(None, description="Tentatives max")
    time_limit: Optional[int] = Field(None, description="Limite de temps")
    max_players: int = Field(..., description="Joueurs max")
    is_private: bool = Field(..., description="Partie privée")

    # Timing
    created_at: datetime = Field(..., description="Date de création")
    started_at: Optional[datetime] = Field(None, description="Date de début")
    finished_at: Optional[datetime] = Field(None, description="Date de fin")

    # Relations
    creator_id: UUID = Field(..., description="ID du créateur")
    participants: List[ParticipantInfo] = Field(default_factory=list, description="Participants")
    attempts: List[AttemptInfo] = Field(default_factory=list, description="Tentatives")

    # Solution (si révélée)
    solution: Optional[List[int]] = Field(None, description="Solution")

    # Paramètres avancés
    settings: Dict[str, Any] = Field(default_factory=dict, description="Paramètres")
    quantum_data: Optional[Dict[str, Any]] = Field(None, description="Données quantiques")

    # Propriétés calculées
    @property
    def current_players(self) -> int:
        """Nombre de joueurs actuels"""
        if not self.participants:
            return 0
        return len([p for p in self.participants if p.status != ParticipationStatus.DISCONNECTED])

    @property
    def duration(self) -> Optional[int]:
        """Durée en secondes"""
        if not self.started_at:
            return None
        end_time = self.finished_at or datetime.now(timezone.utc)
        return int((end_time - self.started_at).total_seconds())

    @property
    def current_turn(self) -> Optional[UUID]:
        """Tour actuel (pour les jeux au tour par tour)"""
        # Logique pour déterminer le tour actuel
        return None


# === SCHÉMAS DE GAMEPLAY ===

class AttemptResult(BaseModel):
    """Résultat d'une tentative"""
    model_config = ConfigDict(from_attributes=True)

    attempt_id: UUID = Field(..., description="ID de la tentative")
    attempt_number: int = Field(..., description="Numéro de tentative")
    correct_positions: int = Field(..., description="Positions correctes (pegs noirs)")
    correct_colors: int = Field(..., description="Couleurs correctes (pegs blancs)")
    is_winning: bool = Field(..., description="Tentative gagnante")
    score: int = Field(..., description="Score obtenu")

    time_taken: Optional[int] = Field(None, description="Temps pris (ms)")
    game_finished: bool = Field(default=False, description="Partie terminée")
    solution: Optional[List[int]] = Field(None, description="Solution (si gagnant)")

    quantum_hint_used: bool = Field(default=False, description="Hint quantique utilisé")
    remaining_attempts: Optional[int] = Field(None, description="Tentatives restantes")


class SolutionHint(BaseModel):
    """Indice sur la solution"""
    model_config = ConfigDict(from_attributes=True)

    hint_type: str = Field(..., description="Type d'indice")
    message: str = Field(..., description="Message d'indice")
    positions: Optional[List[int]] = Field(None, description="Positions concernées")
    colors: Optional[List[int]] = Field(None, description="Couleurs concernées")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Niveau de confiance")


class SolutionReveal(BaseModel):
    """Révélation de la solution (debug)"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    solution: List[int] = Field(..., description="Solution complète")
    revealed_by: UUID = Field(..., description="ID de l'utilisateur qui révèle")
    revealed_at: datetime = Field(..., description="Date de révélation")


# === SCHÉMAS DE RECHERCHE ===

class GameSearch(BaseModel):
    """Paramètres de recherche de parties"""
    model_config = ConfigDict(from_attributes=True)

    game_type: Optional[GameType] = Field(None, description="Type de jeu")
    game_mode: Optional[GameMode] = Field(None, description="Mode de jeu")
    status: Optional[GameStatus] = Field(None, description="Statut")
    difficulty: Optional[Difficulty] = Field(None, description="Difficulté")
    min_players: Optional[int] = Field(None, description="Minimum de joueurs")
    max_players: Optional[int] = Field(None, description="Maximum de joueurs")
    creator_id: Optional[UUID] = Field(None, description="ID du créateur")
    room_code: Optional[str] = Field(None, description="Code de room")
    public_only: bool = Field(default=True, description="Parties publiques seulement")


class GameList(BaseModel):
    """Liste paginée de parties"""
    model_config = ConfigDict(from_attributes=True)

    games: List[GamePublic] = Field(..., description="Liste des parties")
    total: int = Field(..., description="Nombre total de parties")
    page: int = Field(..., description="Page actuelle")
    per_page: int = Field(..., description="Éléments par page")
    pages: int = Field(..., description="Nombre total de pages")


# === SCHÉMAS DE STATISTIQUES ===

class GameStatistics(BaseModel):
    """Statistiques d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    total_attempts: int = Field(..., description="Total des tentatives")
    average_attempts_per_player: float = Field(..., description="Tentatives moyennes par joueur")
    fastest_solution: Optional[int] = Field(None, description="Solution la plus rapide (ms)")
    best_score: int = Field(..., description="Meilleur score")
    quantum_hints_used: int = Field(default=0, description="Indices quantiques utilisés")
    completion_rate: float = Field(..., description="Taux de complétion")
    average_time_per_attempt: Optional[float] = Field(None, description="Temps moyen par tentative")


class PlayerGameStats(BaseModel):
    """Statistiques d'un joueur dans une partie"""
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID = Field(..., description="ID de l'utilisateur")
    game_id: UUID = Field(..., description="ID de la partie")
    attempts_made: int = Field(..., description="Tentatives effectuées")
    best_attempt: Optional[int] = Field(None, description="Meilleure tentative")
    total_time: Optional[int] = Field(None, description="Temps total (ms)")
    score: int = Field(..., description="Score obtenu")
    rank: int = Field(..., description="Classement dans la partie")
    quantum_hints_used: int = Field(default=0, description="Hints quantiques utilisés")
    is_winner: bool = Field(..., description="A gagné la partie")


# === SCHÉMAS D'EXPORT ===

class GameExport(BaseModel):
    """Export d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game: GameFull = Field(..., description="Données de la partie")
    export_format: str = Field(..., description="Format d'export")
    exported_at: datetime = Field(..., description="Date d'export")
    exported_by: UUID = Field(..., description="Exporté par")


class GameReplay(BaseModel):
    """Replay d'une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    events: List[Dict[str, Any]] = Field(..., description="Événements chronologiques")
    duration: int = Field(..., description="Durée totale (secondes)")
    created_at: datetime = Field(..., description="Date de création du replay")


# === SCHÉMAS D'ADMINISTRATION ===

def validate_action(v):
    allowed_actions = ['pause', 'resume', 'terminate', 'kick_player', 'ban_player', 'warn_player']
    if v not in allowed_actions:
        raise ValueError(f"Action invalide. Actions valides: {allowed_actions}")
    return v


class GameModerationAction(BaseModel):
    """Action de modération sur une partie"""
    model_config = ConfigDict(from_attributes=True)

    action: str = Field(..., description="Action effectuée")
    reason: str = Field(..., description="Raison de l'action")
    moderator_id: UUID = Field(..., description="ID du modérateur")
    target_user_id: Optional[UUID] = Field(None, description="Utilisateur ciblé")
    executed_at: datetime = Field(..., description="Date d'exécution")


class GameAuditLog(BaseModel):
    """Log d'audit pour une partie"""
    model_config = ConfigDict(from_attributes=True)

    game_id: UUID = Field(..., description="ID de la partie")
    action: str = Field(..., description="Action effectuée")
    user_id: UUID = Field(..., description="ID de l'utilisateur")
    timestamp: datetime = Field(..., description="Horodatage")
    details: Dict[str, Any] = Field(..., description="Détails de l'action")
    ip_address: Optional[str] = Field(None, description="Adresse IP")


# === SCHÉMAS DE VALIDATION ===

class GameValidation(BaseModel):
    """Validation des données de jeu"""
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool = Field(..., description="Données valides")
    errors: List[str] = Field(default_factory=list, description="Erreurs détectées")
    warnings: List[str] = Field(default_factory=list, description="Avertissements")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions")


class SolutionValidation(BaseModel):
    """Validation d'une solution"""
    model_config = ConfigDict(from_attributes=True)

    is_valid_solution: bool = Field(..., description="Solution valide")
    combination: List[int] = Field(..., description="Combinaison validée")
    matches_constraints: bool = Field(..., description="Respecte les contraintes")
    difficulty_appropriate: bool = Field(..., description="Appropriée à la difficulté")


# === RÉSOLUTION DES RÉFÉRENCES FORWARD ===

# Mise à jour des références forward pour les modèles imbriqués
GameFull.model_rebuild()
ParticipantInfo.model_rebuild()
AttemptInfo.model_rebuild()


# === EXPORTS ===

__all__ = [
    # Création et modification
    "GameCreate", "GameJoin", "GameUpdate",

    # Gameplay
    "AttemptCreate", "AttemptResult", "SolutionHint", "SolutionReveal",

    # Information
    "GameInfo", "GamePublic", "GameFull", "ParticipantInfo", "AttemptInfo",

    # Recherche
    "GameSearch", "GameList",

    # Statistiques
    "GameStatistics", "PlayerGameStats",

    # Export
    "GameExport", "GameReplay",

    # Administration
    "GameModerationAction", "GameAuditLog",

    # Validation
    "GameValidation", "SolutionValidation"
]