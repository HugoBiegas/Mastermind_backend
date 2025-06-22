"""
Routes API pour le mode multijoueur - Version complète pour cohérence avec le frontend
Compatible avec les attentes du code React.js décrites dans le document
"""
import json
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
    """Route pour récupérer les détails d'une room (attendue par le frontend)"""
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
    summary="Lister les parties publiques",
    description="Récupère la liste des parties publiques pour le lobby"
)
async def get_public_multiplayer_rooms(
        page: int = Query(1, ge=1, description="Page"),
        limit: int = Query(20, ge=1, le=100, description="Limite par page"),
        # CORRECTION: Accepter les paramètres directs du frontend
        status: Optional[str] = Query(None, description="Status des parties"),
        difficulty: Optional[str] = Query(None, description="Difficulté"),
        game_type: Optional[str] = Query(None, description="Type de jeu"),
        quantum_enabled: Optional[bool] = Query(None, description="Quantique activé"),
        search_term: Optional[str] = Query(None, description="Terme de recherche"),
        # Garder aussi l'ancien paramètre pour compatibilité
        filters: Optional[str] = Query(None, description="Filtres JSON (legacy)"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Route pour lister les parties publiques (CORRIGÉE pour compatibilité frontend)
    Accepte les paramètres de requête directs envoyés par le frontend
    """
    try:
        # CORRECTION: Construire les filtres à partir des paramètres directs
        constructed_filters = {}

        if status:
            constructed_filters["status"] = status
        if difficulty:
            constructed_filters["difficulty"] = difficulty
        if game_type:
            constructed_filters["game_type"] = game_type
        if quantum_enabled is not None:
            constructed_filters["quantum_enabled"] = quantum_enabled
        if search_term:
            constructed_filters["search_term"] = search_term

        # Si des filtres JSON legacy sont fournis, les fusionner
        if filters:
            try:
                legacy_filters = json.loads(filters)
                constructed_filters.update(legacy_filters)
            except json.JSONDecodeError:
                # Ignorer les filtres JSON malformés
                pass

        # Convertir en JSON pour le service
        filters_json = json.dumps(constructed_filters) if constructed_filters else None

        result = await multiplayer_service.get_public_rooms(
            db, page=page, limit=limit, filters=filters_json
        )
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        # Log l'erreur pour debug
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erreur dans get_public_multiplayer_rooms: {str(e)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


# =====================================================
# GAMEPLAY MULTIJOUEUR
# =====================================================

@router.post(
    "/rooms/{room_code}/start",
    response_model=Dict[str, Any],
    summary="Démarrer la partie",
    description="Démarre une partie multijoueur"
)
async def start_multiplayer_game(
        room_code: str,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour démarrer la partie (attendue par le frontend)"""
    try:
        result = await multiplayer_service.start_game(db, room_code, current_user.id)
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
    summary="Soumettre une tentative",
    description="Soumet une tentative dans une partie multijoueur"
)
async def submit_multiplayer_attempt(
        room_code: str,
        attempt_data: MultiplayerAttemptRequest,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour soumettre une tentative (attendue par le frontend)"""
    try:
        result = await multiplayer_service.submit_attempt(
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


@router.get(
    "/rooms/{room_code}/state",
    response_model=Dict[str, Any],
    summary="État du jeu en temps réel",
    description="Récupère l'état actuel du jeu"
)
async def get_game_state(
        room_code: str,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour l'état du jeu en temps réel (attendue par le frontend)"""
    try:
        result = await multiplayer_service.get_game_state(db, room_code, current_user.id)
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
    "/rooms/{room_code}/players",
    response_model=Dict[str, Any],
    summary="Progression des joueurs",
    description="Récupère la progression de tous les joueurs"
)
async def get_players_progress(
        room_code: str,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour la progression des joueurs (attendue par le frontend)"""
    try:
        result = await multiplayer_service.get_players_progress(db, room_code, current_user.id)
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
    "/rooms/{room_code}/results",
    response_model=Dict[str, Any],
    summary="Résultats finaux",
    description="Récupère les résultats finaux de la partie"
)
async def get_game_results(
        room_code: str,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour les résultats finaux (attendue par le frontend)"""
    try:
        result = await multiplayer_service.get_game_results(db, room_code, current_user.id)
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


# =====================================================
# SYSTÈME D'OBJETS AVANCÉ
# =====================================================

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
# INDICES QUANTIQUES MULTIJOUEUR
# =====================================================

@router.post(
    "/rooms/{room_code}/quantum-hint",
    response_model=Dict[str, Any],
    summary="Demander un indice quantique",
    description="Demande un indice quantique dans une partie multijoueur"
)
async def get_quantum_hint(
        room_code: str,
        hint_request: QuantumHintRequest,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour les indices quantiques multijoueur (NOUVEAU)"""
    try:
        result = await multiplayer_service.get_quantum_hint(
            db, room_code, current_user.id, hint_request
        )
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération d'indice: {str(e)}"
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
                    room_code, str(user.id), message
                )

        except WebSocketDisconnect:
            # Déconnexion normale
            await multiplayer_ws_manager.remove_connection_from_room(
                room_code, user.id
            )

    except Exception as e:
        print(f"Erreur WebSocket: {e}")
        try:
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass


# =====================================================
# ROUTES DE COMPATIBILITÉ
# =====================================================

@router.get(
    "/health",
    response_model=Dict[str, str],
    summary="Santé du service multijoueur",
    description="Vérifie la santé du service multijoueur"
)
async def multiplayer_health():
    """Route de santé pour le multijoueur"""
    return {
        "status": "healthy",
        "service": "multiplayer",
        "websocket": "active" if multiplayer_ws_manager else "inactive"
    }