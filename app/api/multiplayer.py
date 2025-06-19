"""
Routes API pour le mode multijoueur de Quantum Mastermind
Création de parties, lobby, système d'objets, progression temps réel
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.api.deps import (
    get_database, get_current_active_user,
    get_pagination_params, create_http_exception_from_error,
    PaginationParams
)
from app.models.user import User
from app.models.game import Game, GameStatus, GameMode
from app.models.multijoueur import (
    MultiplayerGame, PlayerProgress, GameMastermind,
    PlayerLeaderboard, MultiplayerGameType, ItemType, PlayerStatus
)
from app.schemas.multiplayer import (
    MultiplayerGameCreate, MultiplayerGameResponse,
    PublicGameListing, JoinGameRequest, JoinGameResponse,
    MultiplayerAttemptRequest, MultiplayerAttemptResponse,
    ItemUseRequest, ItemUseResponse, PlayerProgressResponse,
    LeaderboardResponse, PlayerStatsResponse, GlobalStatsResponse
)
from app.services.multiplayer import multiplayer_service
from app.utils.exceptions import (
    EntityNotFoundError, GameError, ValidationError,
    AuthorizationError, GameNotActiveError
)

# Configuration du router
router = APIRouter(prefix="/multiplayer", tags=["Multijoueur"])


# =====================================================
# GESTION DES PARTIES MULTIJOUEUR
# =====================================================

@router.post(
    "/create",
    response_model=MultiplayerGameResponse,
    summary="Créer une partie multijoueur",
    description="Crée une nouvelle partie multijoueur avec configuration personnalisée"
)
async def create_multiplayer_game(
        game_data: MultiplayerGameCreate,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> MultiplayerGameResponse:
    """
    Crée une nouvelle partie multijoueur

    - **game_type**: Type de partie (multi_mastermind uniquement pour le moment)
    - **difficulty**: Difficulté (easy, medium, hard, expert)
    - **total_masterminds**: Nombre de masterminds (3, 6, 9, 12)
    - **max_players**: Nombre maximum de joueurs (max 12)
    - **is_private**: Partie privée avec mot de passe
    - **items_enabled**: Système d'objets activé
    """
    try:
        result = await multiplayer_service.create_multiplayer_game(
            db, game_data, current_user.id
        )
        return MultiplayerGameResponse(**result)

    except (ValidationError, GameError) as e:
        raise create_http_exception_from_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création de la partie: {str(e)}"
        )


@router.get(
    "/public-games",
    response_model=Dict[str, Any],
    summary="Lister les parties publiques",
    description="Récupère la liste des parties publiques avec pagination et filtres"
)
async def get_public_games(
        page: int = Query(1, ge=1, description="Page"),
        limit: int = Query(10, ge=1, le=50, description="Limite par page"),
        difficulty: Optional[str] = Query(None, description="Filtrer par difficulté"),
        max_players: Optional[int] = Query(None, ge=2, le=12, description="Filtrer par nombre max de joueurs"),
        has_slots: Optional[bool] = Query(None, description="Seulement les parties avec places libres"),
        sort_by: Optional[str] = Query("created_at", description="Trier par champ"),
        sort_order: Optional[str] = Query("desc", regex="^(asc|desc)$", description="Ordre de tri"),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Récupère les parties publiques avec filtres et pagination"""
    try:
        result = await multiplayer_service.get_public_games(
            db, page, limit, difficulty, max_players, has_slots, sort_by, sort_order
        )
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des parties: {str(e)}"
        )


@router.post(
    "/join/{game_id}",
    response_model=JoinGameResponse,
    summary="Rejoindre une partie",
    description="Rejoint une partie multijoueur existante"
)
async def join_multiplayer_game(
        game_id: UUID,
        join_data: JoinGameRequest,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> JoinGameResponse:
    """Rejoint une partie multijoueur"""
    try:
        result = await multiplayer_service.join_multiplayer_game(
            db, game_id, current_user.id, join_data.password
        )
        return JoinGameResponse(**result)

    except (EntityNotFoundError, GameError, AuthorizationError) as e:
        raise create_http_exception_from_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la connexion: {str(e)}"
        )


@router.post(
    "/leave/{game_id}",
    response_model=Dict[str, str],
    summary="Quitter une partie",
    description="Quitte une partie multijoueur en cours"
)
async def leave_multiplayer_game(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, str]:
    """Quitte une partie multijoueur"""
    try:
        await multiplayer_service.leave_multiplayer_game(
            db, game_id, current_user.id
        )
        return {"message": "Partie quittée avec succès"}

    except (EntityNotFoundError, AuthorizationError) as e:
        raise create_http_exception_from_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la sortie: {str(e)}"
        )


@router.get(
    "/game/{game_id}",
    response_model=MultiplayerGameResponse,
    summary="Détails d'une partie",
    description="Récupère les détails complets d'une partie multijoueur"
)
async def get_multiplayer_game(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> MultiplayerGameResponse:
    """Récupère les détails d'une partie multijoueur"""
    try:
        result = await multiplayer_service.get_multiplayer_game(
            db, game_id, current_user.id
        )
        return MultiplayerGameResponse(**result)

    except (EntityNotFoundError, AuthorizationError) as e:
        raise create_http_exception_from_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


# =====================================================
# GAMEPLAY MULTIJOUEUR
# =====================================================

@router.post(
    "/attempt/{game_id}",
    response_model=MultiplayerAttemptResponse,
    summary="Faire une tentative",
    description="Soumet une tentative pour le mastermind actuel"
)
async def make_multiplayer_attempt(
        game_id: UUID,
        attempt_data: MultiplayerAttemptRequest,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> MultiplayerAttemptResponse:
    """Fait une tentative dans une partie multijoueur"""
    try:
        result = await multiplayer_service.make_attempt(
            db, game_id, current_user.id,
            attempt_data.mastermind_number, attempt_data.combination
        )
        return MultiplayerAttemptResponse(**result)

    except (EntityNotFoundError, GameError, ValidationError) as e:
        raise create_http_exception_from_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la tentative: {str(e)}"
        )


@router.get(
    "/current-mastermind/{game_id}",
    response_model=Dict[str, Any],
    summary="Mastermind actuel",
    description="Récupère le mastermind actuellement actif"
)
async def get_current_mastermind(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Récupère le mastermind actuel"""
    try:
        result = await multiplayer_service.get_current_mastermind(
            db, game_id, current_user.id
        )
        return result

    except (EntityNotFoundError, AuthorizationError) as e:
        raise create_http_exception_from_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


# =====================================================
# SYSTÈME D'OBJETS BONUS/MALUS
# =====================================================

@router.post(
    "/use-item/{game_id}",
    response_model=ItemUseResponse,
    summary="Utiliser un objet",
    description="Utilise un objet bonus ou malus pendant la partie"
)
async def use_item(
        game_id: UUID,
        item_data: ItemUseRequest,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> ItemUseResponse:
    """Utilise un objet dans une partie multijoueur"""
    try:
        result = await multiplayer_service.use_item(
            db, game_id, current_user.id,
            item_data.item_type, item_data.target_players
        )
        return ItemUseResponse(**result)

    except (EntityNotFoundError, GameError, ValidationError) as e:
        raise create_http_exception_from_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'utilisation de l'objet: {str(e)}"
        )


@router.get(
    "/my-items/{game_id}",
    response_model=Dict[str, List[Dict[str, Any]]],
    summary="Mes objets",
    description="Récupère les objets collectés et utilisés du joueur"
)
async def get_player_items(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, List[Dict[str, Any]]]:
    """Récupère les objets du joueur"""
    try:
        result = await multiplayer_service.get_player_items(
            db, game_id, current_user.id
        )
        return result

    except (EntityNotFoundError, AuthorizationError) as e:
        raise create_http_exception_from_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


@router.get(
    "/available-items",
    response_model=Dict[str, Dict[str, Any]],
    summary="Objets disponibles",
    description="Liste tous les objets disponibles dans le jeu"
)
async def get_available_items() -> Dict[str, Dict[str, Any]]:
    """Récupère la liste des objets disponibles"""
    try:
        result = await multiplayer_service.get_available_items()
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


# =====================================================
# PROGRESSION ET CLASSEMENTS
# =====================================================

@router.get(
    "/my-progress/{game_id}",
    response_model=PlayerProgressResponse,
    summary="Ma progression",
    description="Récupère la progression du joueur actuel"
)
async def get_my_progress(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> PlayerProgressResponse:
    """Récupère la progression du joueur"""
    try:
        result = await multiplayer_service.get_player_progress(
            db, game_id, current_user.id
        )
        return PlayerProgressResponse(**result)

    except (EntityNotFoundError, AuthorizationError) as e:
        raise create_http_exception_from_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


@router.get(
    "/all-progress/{game_id}",
    response_model=List[PlayerProgressResponse],
    summary="Progression de tous les joueurs",
    description="Récupère la progression de tous les joueurs de la partie"
)
async def get_all_players_progress(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> List[PlayerProgressResponse]:
    """Récupère la progression de tous les joueurs"""
    try:
        result = await multiplayer_service.get_all_players_progress(
            db, game_id, current_user.id
        )
        return [PlayerProgressResponse(**progress) for progress in result]

    except (EntityNotFoundError, AuthorizationError) as e:
        raise create_http_exception_from_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


@router.get(
    "/leaderboard/{game_id}",
    response_model=List[LeaderboardResponse],
    summary="Classement de la partie",
    description="Récupère le classement final de la partie"
)
async def get_game_leaderboard(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> List[LeaderboardResponse]:
    """Récupère le classement de la partie"""
    try:
        result = await multiplayer_service.get_game_leaderboard(
            db, game_id, current_user.id
        )
        return [LeaderboardResponse(**entry) for entry in result]

    except (EntityNotFoundError, AuthorizationError) as e:
        raise create_http_exception_from_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


# =====================================================
# STATISTIQUES
# =====================================================

@router.get(
    "/stats/my-stats",
    response_model=PlayerStatsResponse,
    summary="Mes statistiques",
    description="Récupère les statistiques multijoueur du joueur"
)
async def get_my_stats(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> PlayerStatsResponse:
    """Récupère les statistiques du joueur"""
    try:
        result = await multiplayer_service.get_player_stats(
            db, current_user.id
        )
        return PlayerStatsResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


@router.get(
    "/stats/global",
    response_model=GlobalStatsResponse,
    summary="Statistiques globales",
    description="Récupère les statistiques globales du multijoueur"
)
async def get_global_stats(
        db: AsyncSession = Depends(get_database)
) -> GlobalStatsResponse:
    """Récupère les statistiques globales"""
    try:
        result = await multiplayer_service.get_global_stats(db)
        return GlobalStatsResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


# =====================================================
# UTILITAIRES
# =====================================================

@router.get(
    "/by-room-code/{room_code}",
    response_model=PublicGameListing,
    summary="Partie par code",
    description="Trouve une partie par son code de room"
)
async def get_game_by_room_code(
        room_code: str,
        db: AsyncSession = Depends(get_database)
) -> PublicGameListing:
    """Trouve une partie par code de room"""
    try:
        result = await multiplayer_service.get_game_by_room_code(db, room_code)
        return PublicGameListing(**result)

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}"
        )


@router.get(
    "/search",
    response_model=List[PublicGameListing],
    summary="Rechercher des parties",
    description="Recherche des parties par nom d'utilisateur ou critères"
)
async def search_games(
        q: str = Query(..., min_length=2, description="Terme de recherche"),
        db: AsyncSession = Depends(get_database)
) -> List[PublicGameListing]:
    """Recherche des parties"""
    try:
        result = await multiplayer_service.search_games(db, q)
        return [PublicGameListing(**game) for game in result]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}"
        )


@router.post(
    "/start/{game_id}",
    response_model=Dict[str, Any],
    summary="Démarrer une partie",
    description="Démarre une partie multijoueur (créateur uniquement)"
)
async def start_multiplayer_game(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Démarre une partie multijoueur"""
    try:
        result = await multiplayer_service.start_multiplayer_game(
            db, game_id, current_user.id
        )
        return result

    except (EntityNotFoundError, GameError, AuthorizationError) as e:
        raise create_http_exception_from_error(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du démarrage: {str(e)}"
        )