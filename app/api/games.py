"""
Routes de gestion des jeux pour Quantum Mastermind
Création de parties, gameplay, statistiques, recherche
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_database, get_current_active_user, get_current_verified_user,
    get_current_superuser, validate_game_access, validate_game_modification,
    get_pagination_params, get_search_params, create_http_exception_from_error,
    PaginationParams, SearchParams
)
from app.models.game import GameType, GameMode, GameStatus
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.game import (
    GameCreate, GameUpdate, GameJoin, AttemptCreate,
    GameInfo, GameFull, GameList, AttemptResult, SolutionReveal
)
from app.schemas.quantum import QuantumHint
from app.services.game import game_service
from app.services.quantum import quantum_service
from app.utils.exceptions import (
    EntityNotFoundError, GameError, GameNotActiveError,
    GameFullError, ValidationError
)

# Configuration du router
router = APIRouter(prefix="/games", tags=["Jeux"])


# =====================================================
# ROUTES SPÉCIFIQUES - DOIVENT ÊTRE EN PREMIER
# =====================================================
# CORRECTION CRITIQUE : Ces routes doivent être AVANT /{game_id}

@router.post(
    "/create",
    response_model=Dict[str, Any],
    summary="Créer une partie",
    description="Crée une nouvelle partie de Quantum Mastermind"
)
async def create_game(
        game_data: GameCreate,
        current_user: User = Depends(get_current_verified_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Crée une nouvelle partie de Quantum Mastermind

    - **game_type**: Type de jeu (classic, quantum, hybrid, tournament)
    - **game_mode**: Mode de jeu (solo, multiplayer, ranked, training)
    - **difficulty**: Niveau de difficulté (easy, medium, hard, expert, quantum)
    """
    try:
        created_game = await game_service.create_game(
            db, game_data, current_user.id
        )
        return created_game

    except (ValidationError, GameError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la création de la partie"
        )


@router.get(
    "/search",
    response_model=GameList,
    summary="Rechercher des parties",
    description="Recherche des parties selon des critères"
)
async def search_games(
        pagination: PaginationParams = Depends(get_pagination_params),
        search: SearchParams = Depends(get_search_params),
        game_type: Optional[GameType] = Query(None, description="Type de jeu"),
        game_mode: Optional[GameMode] = Query(None, description="Mode de jeu"),
        status: Optional[GameStatus] = Query(None, description="Statut"),
        is_public: bool = Query(True, description="Afficher uniquement les parties publiques"),
        current_user: Optional[User] = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> GameList:
    """
    Recherche des parties selon des critères

    - **game_type**: Type de jeu à filtrer
    - **game_mode**: Mode de jeu à filtrer
    - **status**: Statut à filtrer
    - **is_public**: Afficher uniquement les parties publiques
    """
    try:
        games = await game_service.search_games(
            db, pagination, search,
            game_type=game_type, game_mode=game_mode,
            status=status, is_public=is_public,
            user_id=current_user.id if current_user else None
        )
        return games

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la recherche de parties"
        )


@router.get(
    "/my-games",
    response_model=GameList,
    summary="Mes parties",
    description="Récupère les parties de l'utilisateur connecté"
)
async def get_my_games(
        pagination: PaginationParams = Depends(get_pagination_params),
        status: Optional[GameStatus] = Query(None, description="Statut de la partie"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> GameList:
    """
    Récupère les parties de l'utilisateur connecté

    Inclut les parties créées et celles auxquelles il participe
    """
    try:
        games = await game_service.get_user_games(
            db, current_user.id, pagination, status
        )
        return games

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération de vos parties"
        )


@router.get(
    "/public",
    response_model=GameList,
    summary="Parties publiques",
    description="Récupère les parties publiques ouvertes"
)
async def get_public_games(
        pagination: PaginationParams = Depends(get_pagination_params),
        db: AsyncSession = Depends(get_database)
) -> GameList:
    """
    Récupère les parties publiques ouvertes

    Accessible sans authentification
    """
    try:
        games = await game_service.get_public_games(db, pagination)
        return games

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des parties publiques"
        )


@router.get(
    "/stats/leaderboard",
    response_model=Dict[str, Any],
    summary="Classement général",
    description="Récupère le classement des meilleurs joueurs"
)
async def get_leaderboard(
        game_type: Optional[GameType] = Query(None, description="Type de jeu"),
        time_period: str = Query("all", description="Période (all, month, week)"),
        limit: int = Query(10, ge=1, le=100, description="Nombre de joueurs"),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Récupère le classement des meilleurs joueurs

    - **game_type**: Filtrer par type de jeu
    - **time_period**: Période (all, month, week)
    - **limit**: Nombre de joueurs dans le classement
    """
    try:
        leaderboard = await game_service.get_leaderboard(
            db, game_type=game_type, time_period=time_period, limit=limit
        )
        return leaderboard

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération du classement"
        )


# =====================================================
# ROUTES AVEC PARAMÈTRES UUID - À LA FIN
# =====================================================
# CORRECTION CRITIQUE : Ces routes doivent être EN DERNIER

@router.get(
    "/{game_id}",
    response_model=GameFull,
    summary="Détails d'une partie",
    description="Récupère les détails complets d'une partie"
)
async def get_game(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database),
        _: bool = Depends(validate_game_access)
) -> GameFull:
    """
    Récupère les détails complets d'une partie

    Inclut l'état actuel, les joueurs, l'historique des coups

    Args:
        game_id: UUID de la partie à récupérer
        current_user: Utilisateur authentifié
        db: Session de base de données

    Returns:
        GameFull: Détails complets de la partie

    Raises:
        404: Partie non trouvée ou accès interdit
        500: Erreur serveur
    """
    try:
        # CORRECTION: Appel corrigé du service
        game = await game_service.get_game_details(db, game_id, current_user.id)
        return game

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except GameError as e:
        # AJOUT: Gestion spécifique des erreurs de jeu
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        # AMÉLIORATION: Logging de l'erreur pour debug
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erreur lors de la récupération de la partie {game_id}: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération de la partie"
        )
@router.put(
    "/{game_id}",
    response_model=GameInfo,
    summary="Modifier une partie",
    description="Met à jour les paramètres d'une partie"
)
async def update_game(
        game_id: UUID,
        game_update: GameUpdate,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database),
        _: bool = Depends(validate_game_modification)
) -> GameInfo:
    """
    Met à jour les paramètres d'une partie

    Seul le créateur de la partie ou un admin peut la modifier
    """
    try:
        updated_game = await game_service.update_game(
            db, game_id, game_update, current_user.id
        )
        return updated_game

    except (EntityNotFoundError, ValidationError, GameError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la mise à jour de la partie"
        )


@router.delete(
    "/{game_id}",
    response_model=MessageResponse,
    summary="Supprimer une partie",
    description="Supprime définitivement une partie"
)
async def delete_game(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database),
        _: bool = Depends(validate_game_modification)
) -> MessageResponse:
    """
    Supprime définitivement une partie

    Attention: Cette action est irréversible !
    """
    try:
        await game_service.delete_game(db, game_id, current_user.id)
        return MessageResponse(
            message="Partie supprimée avec succès",
            details={"game_id": str(game_id)}
        )

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la suppression de la partie"
        )


@router.post(
    "/{game_id}/join",
    response_model=Dict[str, Any],
    summary="Rejoindre une partie",
    description="Rejoint une partie existante"
)
async def join_game(
        game_id: UUID,
        join_data: GameJoin,
        current_user: User = Depends(get_current_verified_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Rejoint une partie existante

    - **password**: Mot de passe (si la partie est protégée)
    - **player_name**: Nom d'affichage du joueur (optionnel)
    """
    try:
        result = await game_service.join_game(
            db, game_id, current_user.id, join_data
        )
        return result

    except (EntityNotFoundError, GameFullError, GameNotActiveError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la participation à la partie"
        )


@router.post(
    "/{game_id}/leave",
    response_model=MessageResponse,
    summary="Quitter une partie",
    description="Quitte une partie en cours"
)
async def leave_game(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Quitte une partie en cours

    L'utilisateur sera retiré de la liste des participants
    """
    try:
        await game_service.leave_game(db, game_id, current_user.id)
        return MessageResponse(
            message="Vous avez quitté la partie",
            details={"game_id": str(game_id)}
        )

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'abandon de la partie"
        )


@router.post(
    "/{game_id}/start",
    response_model=Dict[str, Any],
    summary="Démarrer une partie",
    description="Démarre officiellement une partie"
)
async def start_game(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Démarre officiellement une partie

    Seul le créateur peut démarrer la partie
    """
    try:
        result = await game_service.start_game(db, game_id, current_user.id)
        return result

    except (EntityNotFoundError, GameError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du démarrage de la partie"
        )


@router.post(
    "/{game_id}/attempt",
    response_model=AttemptResult,
    summary="Faire une tentative",
    description="Soumet une tentative de solution"
)
async def make_attempt(
        game_id: UUID,
        attempt: AttemptCreate,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> AttemptResult:
    """
    Soumet une tentative de solution

    - **combination**: Combinaison proposée (liste de couleurs)
    - **use_quantum_hint**: Utiliser un hint quantique (optionnel)
    """
    try:
        result = await game_service.make_attempt(
            db, game_id, current_user.id, attempt
        )
        return result

    except (EntityNotFoundError, GameError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la tentative"
        )


@router.post(
    "/{game_id}/quantum-hint",
    response_model=QuantumHint,
    summary="Obtenir un hint quantique",
    description="Utilise l'informatique quantique pour obtenir un indice"
)
async def get_quantum_hint(
        game_id: UUID,
        hint_type: str = Query("grover", description="Type de hint quantique"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> QuantumHint:
    """
    Utilise l'informatique quantique pour obtenir un indice

    - **hint_type**: Type de hint (grover, superposition, entanglement)
    """
    try:
        hint = await quantum_service.generate_quantum_hint(
            db, game_id, current_user.id, hint_type
        )
        return hint

    except (EntityNotFoundError, GameError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la génération du hint quantique"
        )


@router.get(
    "/{game_id}/stats",
    response_model=Dict[str, Any],
    summary="Statistiques d'une partie",
    description="Récupère les statistiques détaillées d'une partie"
)
async def get_game_stats(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database),
        _: bool = Depends(validate_game_access)
) -> Dict[str, Any]:
    """
    Récupère les statistiques détaillées d'une partie

    Inclut les performances des joueurs, tentatives, temps
    """
    try:
        stats = await game_service.get_game_statistics(db, game_id)
        return stats

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des statistiques"
        )


@router.post(
    "/{game_id}/moderate",
    response_model=MessageResponse,
    summary="Modérer une partie",
    description="Effectue des actions de modération sur une partie"
)
async def moderate_game(
        game_id: UUID,
        action: str = Query(..., description="Action de modération"),
        reason: str = Query(..., description="Raison de l'action"),
        current_user: User = Depends(get_current_superuser),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Effectue des actions de modération sur une partie

    Actions disponibles:
    - pause: Mettre en pause
    - resume: Reprendre
    - terminate: Terminer
    - kick_player: Expulser un joueur
    - ban_player: Bannir un joueur

    - **action**: Action à effectuer
    - **reason**: Raison de l'action (obligatoire)
    """
    try:
        await game_service.moderate_game(
            db, game_id, action, reason, current_user.id
        )

        return MessageResponse(
            message=f"Action '{action}' effectuée sur la partie {game_id}",
            details={"action": action, "reason": reason, "moderator": str(current_user.id)}
        )

    except (EntityNotFoundError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'action de modération"
        )


@router.get(
    "/{game_id}/history",
    response_model=List[Dict[str, Any]],
    summary="Historique d'une partie",
    description="Récupère l'historique complet des actions d'une partie"
)
async def get_game_history(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database),
        _: bool = Depends(validate_game_access)
) -> List[Dict[str, Any]]:
    """
    Récupère l'historique complet des actions d'une partie

    Inclut toutes les tentatives, hints utilisés, événements
    """
    try:
        history = await game_service.get_game_history(db, game_id)
        return history

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération de l'historique"
        )


@router.get(
    "/{game_id}/solution",
    response_model=SolutionReveal,
    summary="Révéler la solution (DEBUG)",
    description="Révèle la solution pour debug (DEV uniquement)",
    include_in_schema=False  # Masquer en production
)
async def debug_reveal_solution(
        game_id: UUID,
        current_user: User = Depends(get_current_superuser),
        db: AsyncSession = Depends(get_database)
) -> SolutionReveal:
    """Route de debug pour révéler la solution (développement uniquement)"""

    # Vérification de l'environnement
    from app.core.config import settings
    if settings.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Route non disponible en production"
        )

    try:
        solution = await game_service.reveal_solution(db, game_id)
        return solution

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la révélation de la solution"
        )


@router.get(
    "/{game_id}/export",
    response_model=Dict[str, Any],
    summary="Exporter une partie",
    description="Exporte les données d'une partie au format JSON"
)
async def export_game(
        game_id: UUID,
        format: str = Query("json", description="Format d'export"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database),
        _: bool = Depends(validate_game_access)
) -> Dict[str, Any]:
    """
    Exporte les données d'une partie

    Formats supportés: json, csv (futur)
    """
    try:
        exported_data = await game_service.export_game(db, game_id, format)
        return exported_data

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'export de la partie"
        )