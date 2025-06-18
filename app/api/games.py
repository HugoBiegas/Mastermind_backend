"""
Routes de gestion des jeux pour Quantum Mastermind
MODIFIÉ: Intégration complète des fonctionnalités quantiques
"""
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_database, get_current_active_user, get_current_verified_user,
    get_current_superuser, validate_game_access, get_pagination_params, get_search_params,
    create_http_exception_from_error,get_game_service,
    PaginationParams, SearchParams
)
from app.models.game import GameType, GameMode, GameStatus
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.game import (
    GameCreate, GameJoin, AttemptCreate,
    GameFull, GameList, AttemptResult, SolutionReveal,
    QuantumGameInfo, QuantumHintRequest, QuantumHintResponse, GameCreateResponse
)
from app.services.quantum import quantum_service
from app.utils.exceptions import (
    EntityNotFoundError, GameError, GameNotActiveError,
    GameFullError, ValidationError, AuthorizationError
)

# Configuration du router
router = APIRouter(prefix="/games", tags=["Jeux"])


# =====================================================
# ROUTES SPÉCIFIQUES - DOIVENT ÊTRE EN PREMIER
# =====================================================

@router.post(
    "/create",
    response_model=GameCreateResponse,  # CORRECTION: Utiliser le bon schéma
    summary="Créer une nouvelle partie",
    description="Crée une nouvelle partie avec option auto-leave"
)
async def create_game(
        game_data: GameCreate,
        auto_leave: bool = Query(False, description="Quitter automatiquement les parties actives"),
        current_user: User = Depends(get_current_verified_user),
        db: AsyncSession = Depends(get_database),
        game_service = Depends(get_game_service)
) -> GameCreateResponse:  # CORRECTION: Type de retour précis
    """
    Crée une nouvelle partie

    CORRECTION: Retour avec schéma validé
    """
    try:
        #  Appeler la méthode appropriée selon auto_leave
        if auto_leave:
            result = await game_service.create_game_with_auto_leave(
                db, game_data, current_user.id, auto_leave=True
            )
        else:
            result = await game_service.create_game(db, game_data, current_user.id)

        #  Valider et retourner selon le schéma
        return GameCreateResponse(**result)

    except (ValidationError, GameError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        print(f"Erreur création partie: {e}")  # Pour debug
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création de la partie: {str(e)}"
        )


@router.get(
    "/search",
    response_model=GameList,
    summary="Rechercher des parties",
    description="Recherche des parties selon des critères avec filtre quantique"
)
async def search_games(
        pagination: PaginationParams = Depends(get_pagination_params),
        search: SearchParams = Depends(get_search_params),
        game_type: Optional[GameType] = Query(None, description="Type de jeu"),
        game_mode: Optional[GameMode] = Query(None, description="Mode de jeu"),
        status: Optional[GameStatus] = Query(None, description="Statut"),
        is_public: bool = Query(True, description="Afficher uniquement les parties publiques"),
        quantum_only: bool = Query(False, description="Parties quantiques uniquement"),  # NOUVEAU
        current_user: Optional[User] = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database),
        game_service = Depends(get_game_service)
) -> GameList:
    """
    Recherche des parties selon des critères

    NOUVEAU: Filtre par mode quantique
    - **quantum_only**: Afficher uniquement les parties quantiques
    """
    try:
        games = await game_service.search_games(
            db, pagination, search,
            game_type=game_type, game_mode=game_mode,
            status=status, is_public=is_public,
            quantum_only=quantum_only,  # NOUVEAU
            user_id=current_user.id if current_user else None
        )
        return games

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la recherche de parties"
        )


@router.get(
    "/my-current-game",
    response_model=Optional[Dict[str, Any]],
    summary="Récupérer ma partie active",
    description="Récupère la partie actuellement active de l'utilisateur connecté"
)
async def get_my_current_game(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database),
        game_service = Depends(get_game_service)
) -> Optional[Dict[str, Any]]:
    """Récupère la partie active de l'utilisateur"""
    try:
        current_game = await game_service.get_user_current_game(db, current_user.id)
        return current_game

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération de la partie active"
        )


@router.post(
    "/leave-all-active",
    response_model=Dict[str, Any],
    summary="Quitter toutes les parties actives",
    description="Quitte toutes les parties actives de l'utilisateur connecté"
)
async def leave_all_active_games(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database),
        game_service = Depends(get_game_service)
) -> Dict[str, Any]:
    """
    Quitte toutes les parties actives de l'utilisateur

    Logique appliquée :
    - Trouve toutes les parties avec status 'waiting', 'starting', 'active', 'paused'
    - Met le status du joueur à 'disconnected'
    - Annule la partie si l'utilisateur est seul
    - Annule la partie si tous les autres joueurs ont des status non-actifs
    """
    try:
        result = await game_service.leave_all_active_games(db, current_user.id)
        return result

    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except GameError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'abandon des parties actives"
        )


# =====================================================
# NOUVELLES ROUTES QUANTIQUES
# =====================================================

@router.get(
    "/{game_id}/quantum-info",
    response_model=QuantumGameInfo,
    summary="Informations quantiques d'une partie",
    description="Récupère les informations quantiques détaillées d'une partie"
)
async def get_quantum_game_info(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database),
        _: bool = Depends(validate_game_access),
        game_service = Depends(get_game_service)
) -> QuantumGameInfo:
    """
    Récupère les informations quantiques détaillées d'une partie

    NOUVEAU: Endpoint spécifique aux données quantiques
    """
    try:
        quantum_info = await game_service.get_quantum_game_info(db, game_id)
        return QuantumGameInfo(**quantum_info)

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des informations quantiques"
        )


@router.post(
    "/{game_id}/quantum-hint",
    response_model=QuantumHintResponse,
    summary="Demander un hint quantique",
    description="Demande un hint quantique pour aider à résoudre la partie"
)
async def request_quantum_hint(
        game_id: UUID,
        hint_request: QuantumHintRequest,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database),
        _: bool = Depends(validate_game_access),
        game_service = Depends(get_game_service)
) -> QuantumHintResponse:
    """
    Demande un hint quantique pour aider à résoudre la partie

    NOUVEAU: Génération de hints avec algorithmes quantiques
    """
    try:
        # Vérifier que la partie est active et quantique
        game = await game_service.get_game_details(db, game_id, current_user.id)

        if not game.quantum_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Les hints quantiques ne sont disponibles que pour les parties quantiques"
            )

        if game.status != GameStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La partie doit être active pour demander un hint"
            )

        # Générer le hint quantique
        hint_data = await quantum_service.generate_quantum_hint(
            db=db,
            game_id=game_id,
            player_id=current_user.id,
            hint_type=hint_request.hint_type
        )

        # Calculer le coût
        hint_costs = {
            "grover": 50,
            "superposition": 25,
            "entanglement": 35,
            "basic": 10
        }
        cost = hint_costs.get(hint_request.hint_type, 10)

        # Enregistrer l'utilisation du hint (si nécessaire)
        # await game_service.record_quantum_hint_usage(db, game_id, current_user.id, hint_request.hint_type, cost)

        return QuantumHintResponse(
            message=hint_data["message"],
            type=hint_data["type"],
            confidence=hint_data["confidence"],
            algorithm=hint_data.get("algorithm", "unknown"),
            qubits=hint_data.get("qubits", 1),
            execution_time=hint_data.get("execution_time", 0.0),
            cost=cost,
            quantum_data=hint_data
        )

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération du hint quantique: {str(e)}"
        )


@router.get(
    "/quantum/backend-status",
    response_model=Dict[str, Any],
    summary="État du backend quantique",
    description="Vérifie l'état et les capacités du backend quantique"
)
async def get_quantum_backend_status(
        current_user: User = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Vérifie l'état et les capacités du backend quantique

    NOUVEAU: Diagnostic du système quantique
    """
    try:
        backend_status = await quantum_service.test_quantum_backend()
        quantum_info = quantum_service.get_quantum_info()

        return {
            "backend_status": backend_status,
            "quantum_capabilities": quantum_info,
            "available_features": [
                "quantum_solution_generation",
                "quantum_hints_calculation",
                "hamming_distance_computation",
                "superposition_analysis"
            ]
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la vérification du backend quantique: {str(e)}"
        )


# =====================================================
# ROUTES DE JEU MODIFIÉES AVEC SUPPORT QUANTIQUE
# =====================================================

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
        db: AsyncSession = Depends(get_database),
        game_service = Depends(get_game_service)
) -> Dict[str, Any]:
    """Rejoint une partie existante"""
    try:
        result = await game_service.join_game(db, game_id, current_user.id, join_data)
        return result

    except (EntityNotFoundError, GameError, GameFullError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la participation à la partie"
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
        db: AsyncSession = Depends(get_database),
        game_service = Depends(get_game_service)
) -> Dict[str, Any]:
    """Démarre officiellement une partie"""
    try:
        result = await game_service.start_game(db, game_id, current_user.id)
        return result

    except (EntityNotFoundError, GameError, AuthorizationError) as e:
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
        db: AsyncSession = Depends(get_database),
        game_service = Depends(get_game_service)
) -> AttemptResult:
    """Soumet une tentative de solution"""
    try:
        result = await game_service.make_attempt(db, game_id, current_user.id, attempt)
        return result

    except (EntityNotFoundError, GameNotActiveError, ValidationError, GameError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du traitement de la tentative"
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
        db: AsyncSession = Depends(get_database),
        game_service = Depends(get_game_service)
) -> MessageResponse:
    """Quitte une partie en cours"""
    try:
        result = await game_service.leave_game(db, game_id, current_user.id)
        return MessageResponse(message=result["message"])

    except (EntityNotFoundError, GameError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'abandon de la partie"
        )


@router.get(
    "/leaderboard",
    response_model=Dict[str, Any],
    summary="Classement général",
    description="Récupère le classement des meilleurs joueurs avec scores quantiques"
)
async def get_leaderboard(
        game_type: Optional[GameType] = Query(None, description="Type de jeu"),
        time_period: str = Query("all", description="Période (all, month, week)"),
        limit: int = Query(10, ge=1, le=100, description="Nombre de joueurs"),
        include_quantum: bool = Query(True, description="Inclure les scores quantiques"),  # NOUVEAU
        db: AsyncSession = Depends(get_database),
        game_service = Depends(get_game_service)
) -> Dict[str, Any]:
    """
    Récupère le classement des meilleurs joueurs

    MODIFIÉ: Inclut les scores quantiques
    """
    try:
        leaderboard = await game_service.get_leaderboard(
            db, game_type=game_type, time_period=time_period,
            limit=limit, include_quantum=include_quantum
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

@router.get(
    "/{game_id}",
    response_model=GameFull,
    summary="Détails d'une partie",
    description="Récupère les détails complets d'une partie avec informations quantiques"
)
async def get_game(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database),
        _: bool = Depends(validate_game_access),
        game_service = Depends(get_game_service)
) -> GameFull:
    """
    Récupère les détails complets d'une partie

    MODIFIÉ: Inclut les informations quantiques
    """
    try:
        game = await game_service.get_game_details(db, game_id, current_user.id)
        return game

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération de la partie"
        )


@router.get(
    "/{game_id}/export",
    response_model=Dict[str, Any],
    summary="Exporter une partie",
    description="Exporte les données d'une partie au format JSON avec données quantiques"
)
async def export_game(
        game_id: UUID,
        format: str = Query("json", description="Format d'export"),
        include_quantum: bool = Query(True, description="Inclure les données quantiques"),  # NOUVEAU
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database),
        _: bool = Depends(validate_game_access),
        game_service = Depends(get_game_service)
) -> Dict[str, Any]:
    """
    Exporte les données d'une partie

    MODIFIÉ: Option d'inclure les données quantiques
    """
    try:
        exported_data = await game_service.export_game(
            db, game_id, format, include_quantum=include_quantum
        )
        return exported_data

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'export de la partie"
        )


# =====================================================
# ROUTES DEBUG ET ADMIN
# =====================================================

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
        db: AsyncSession = Depends(get_database),
        game_service = Depends(get_game_service)
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


@router.post(
    "/admin/force-leave/{user_id}",
    response_model=Dict[str, Any],
    summary="Forcer la sortie (ADMIN)",
    description="Force un utilisateur à quitter toutes ses parties actives"
)
async def admin_force_leave_all_games(
        user_id: UUID,
        current_user: User = Depends(get_current_superuser),
        db: AsyncSession = Depends(get_database),
        game_service = Depends(get_game_service)
) -> Dict[str, Any]:
    """Force un utilisateur à quitter toutes ses parties actives (Admin uniquement)"""
    try:
        result = await game_service.leave_all_active_games(db, user_id)
        return {
            "message": f"Utilisateur {user_id} forcé à quitter toutes ses parties",
            "admin_action": True,
            **result
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la force de sortie"
        )