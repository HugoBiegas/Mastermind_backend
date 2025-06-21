"""
Routes API pour le mode multijoueur - Version corrigée pour cohérence avec le frontend
Compatible avec les attentes du code React.js
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.api.deps import get_database, get_current_active_user
from app.models.user import User
from app.schemas.multiplayer import *
from app.services.multiplayer import multiplayer_service
from app.websocket.multiplayer import multiplayer_ws_manager
from app.utils.exceptions import *

router = APIRouter(prefix="/multiplayer", tags=["Multijoueur"])

# =====================================================
# ROUTES POUR COHÉRENCE AVEC LE FRONTEND
# =====================================================

@router.post(
    "/rooms/create",
    response_model=Dict[str, Any],
    summary="Créer une partie multijoueur",
    description="Crée une nouvelle partie multijoueur (route attendue par le frontend)"
)
async def create_multiplayer_room(
        game_data: MultiplayerGameCreateRequest,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route créée pour correspondre aux attentes du frontend"""
    try:
        result = await multiplayer_service.create_multiplayer_game(
            db, game_data, current_user.id
        )
        return {
            "success": True,
            "data": result,
            "message": "Partie créée avec succès"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création: {str(e)}"
        )


@router.post(
    "/rooms/{room_code}/join",
    response_model=Dict[str, Any],
    summary="Rejoindre une partie par code",
    description="Rejoint une partie multijoueur avec un code de room"
)
async def join_multiplayer_room(
        room_code: str,
        join_data: JoinGameRequest,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour rejoindre une partie par code (attendue par le frontend)"""
    try:
        result = await multiplayer_service.join_room_by_code(
            db, room_code, current_user.id, join_data.password, join_data.as_spectator
        )
        return {
            "success": True,
            "data": result,
            "message": "Partie rejointe avec succès"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la connexion: {str(e)}"
        )


@router.post(
    "/rooms/{room_code}/leave",
    response_model=Dict[str, str],
    summary="Quitter une partie",
    description="Quitte une partie multijoueur"
)
async def leave_multiplayer_room(
        room_code: str,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, str]:
    """Route pour quitter une partie (attendue par le frontend)"""
    try:
        await multiplayer_service.leave_room_by_code(db, room_code, current_user.id)
        return {"message": "Partie quittée avec succès"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la sortie: {str(e)}"
        )


@router.get(
    "/rooms/{room_code}",
    response_model=Dict[str, Any],
    summary="Détails d'une partie",
    description="Récupère les détails d'une partie par code de room"
)
async def get_multiplayer_room(
        room_code: str,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour récupérer les détails d'une partie"""
    try:
        result = await multiplayer_service.get_room_details(db, room_code, current_user.id)
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


@router.get(
    "/lobby",
    response_model=Dict[str, Any],
    summary="Lister les parties publiques avec filtres",
    description="Récupère les parties publiques pour le lobby (route attendue par le frontend)"
)
async def get_lobby_games(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=50),
        game_type: Optional[str] = Query(None),
        difficulty: Optional[str] = Query(None),
        max_players: Optional[int] = Query(None),
        has_password: Optional[bool] = Query(None),
        allow_spectators: Optional[bool] = Query(None),
        quantum_enabled: Optional[bool] = Query(None),
        status: Optional[str] = Query(None),
        search_term: Optional[str] = Query(None),
        has_slots: Optional[bool] = Query(None),
        sort_by: Optional[str] = Query("created_at"),
        sort_order: Optional[str] = Query("desc"),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour récupérer les parties publiques avec filtres"""
    try:
        filters = {
            "game_type": game_type,
            "difficulty": difficulty,
            "max_players": max_players,
            "has_password": has_password,
            "allow_spectators": allow_spectators,
            "quantum_enabled": quantum_enabled,
            "status": status,
            "search_term": search_term,
            "has_slots": has_slots,
            "sort_by": sort_by,
            "sort_order": sort_order
        }
        # Filtrer les valeurs nulles
        filters = {k: v for k, v in filters.items() if v is not None}

        result = await multiplayer_service.get_public_games_with_filters(
            db, page, limit, filters
        )
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des parties: {str(e)}"
        )


@router.post(
    "/rooms/{room_code}/start",
    response_model=Dict[str, Any],
    summary="Démarrer une partie",
    description="Démarre une partie multijoueur (créateur uniquement)"
)
async def start_multiplayer_room(
        room_code: str,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour démarrer une partie"""
    try:
        result = await multiplayer_service.start_room(db, room_code, current_user.id)
        return {
            "success": True,
            "data": result,
            "message": "Partie démarrée"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du démarrage: {str(e)}"
        )


@router.post(
    "/rooms/{room_code}/attempt",
    response_model=Dict[str, Any],
    summary="Faire une tentative",
    description="Soumet une tentative pour le mastermind actuel"
)
async def make_multiplayer_attempt(
        room_code: str,
        attempt_data: MultiplayerAttemptRequest,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour faire une tentative dans une partie"""
    try:
        result = await multiplayer_service.make_attempt_by_room_code(
            db, room_code, current_user.id, attempt_data
        )
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la tentative: {str(e)}"
        )


@router.post(
    "/rooms/{room_code}/use-item",
    response_model=Dict[str, Any],
    summary="Utiliser un objet",
    description="Utilise un objet dans une partie multijoueur"
)
async def use_multiplayer_item(
        room_code: str,
        item_data: ItemUseRequest,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour utiliser un objet"""
    try:
        result = await multiplayer_service.use_item_in_room(
            db, room_code, current_user.id, item_data
        )
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'utilisation de l'objet: {str(e)}"
        )


# =====================================================
# WEBSOCKET POUR TEMPS RÉEL
# =====================================================

@router.websocket("/ws/{room_code}")
async def websocket_endpoint(
        websocket: WebSocket,
        room_code: str,
        token: str = Query(..., description="JWT token"),
        db: AsyncSession = Depends(get_database)
):
    """Endpoint WebSocket pour les parties multijoueur"""
    try:
        # Vérifier l'authentification
        user = await multiplayer_service.authenticate_websocket_user(token)
        if not user:
            await websocket.close(code=1008, reason="Invalid token")
            return

        # Accepter la connexion
        await websocket.accept()

        # Ajouter à la room
        await multiplayer_ws_manager.add_connection_to_room(
            room_code, websocket, user.id, user.username
        )

        try:
            while True:
                # Écouter les messages
                message = await websocket.receive_text()
                await multiplayer_ws_manager.handle_message(
                    room_code, user.id, message, db
                )

        except WebSocketDisconnect:
            # Gérer la déconnexion
            await multiplayer_ws_manager.remove_connection_from_room(
                room_code, user.id
            )

    except Exception as e:
        await websocket.close(code=1011, reason=f"Server error: {str(e)}")


# =====================================================
# ROUTES STATISTIQUES ET LEADERBOARD
# =====================================================

@router.get(
    "/stats/global",
    response_model=Dict[str, Any],
    summary="Statistiques globales",
    description="Récupère les statistiques globales du multijoueur"
)
async def get_global_stats(
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour récupérer les statistiques globales"""
    try:
        result = await multiplayer_service.get_global_statistics(db)
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des statistiques: {str(e)}"
        )


@router.get(
    "/leaderboard",
    response_model=Dict[str, Any],
    summary="Classement des joueurs",
    description="Récupère le classement des meilleurs joueurs"
)
async def get_leaderboard(
        limit: int = Query(50, ge=1, le=100),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour récupérer le leaderboard"""
    try:
        result = await multiplayer_service.get_leaderboard(db, limit)
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération du classement: {str(e)}"
        )