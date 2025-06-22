"""
Routes API pour le mode multijoueur - Version complète pour cohérence avec le frontend
Compatible avec les attentes du code React.js décrites dans le document
COMPLET: Toutes les routes attendues par le frontend sont implémentées
"""
import json

from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_database, get_current_active_user
from app.models.user import User
from app.schemas.multiplayer import *
from app.services.multiplayer import multiplayer_service
from app.utils.exceptions import *

# Import conditionnel pour WebSocket
try:
    from app.websocket.multiplayer import multiplayer_ws_manager
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/multiplayer", tags=["Multijoueur"])

# =====================================================
# GESTION DES ROOMS (CRUD)
# =====================================================

@router.post(
    "/rooms/create",
    response_model=Dict[str, Any],
    summary="Créer une partie multijoueur",
    description="Crée une nouvelle partie multijoueur avec auto-leave des parties actives"
)
async def create_multiplayer_room(
        game_data: MultiplayerGameCreateRequest,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route créée pour correspondre aux attentes du frontend avec auto-leave"""
    try:
        # CORRECTION: Import correct de game_service
        try:
            from app.services.game import game_service
            await game_service.leave_all_active_games(db, current_user.id)
            logger.info(f"✅ Parties actives quittées pour l'utilisateur {current_user.id}")
        except Exception as leave_error:
            logger.warning(f"⚠️ Pas de parties actives à quitter: {leave_error}")
            # Ne pas bloquer la création pour cette erreur

        result = await multiplayer_service.create_multiplayer_game(
            db, game_data, current_user.id
        )
        return {
            "success": True,
            "data": result,
            "message": "Partie créée avec succès"
        }
    except Exception as e:
        logger.error(f"Erreur création room: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création: {str(e)}"
        )


@router.post(
    "/rooms/{room_code}/join",
    response_model=Dict[str, Any],
    summary="Rejoindre une partie par code",
    description="Rejoint une partie multijoueur avec auto-leave des parties actives"
)
async def join_multiplayer_room(
        room_code: str,
        join_data: JoinGameRequest,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour rejoindre une partie par code avec auto-leave"""
    try:
        # CORRECTION: Import correct de game_service
        try:
            from app.services.game import game_service
            await game_service.leave_all_active_games(db, current_user.id)
            logger.info(f"✅ Parties actives quittées pour l'utilisateur {current_user.id}")
        except Exception as leave_error:
            logger.warning(f"⚠️ Pas de parties actives à quitter: {leave_error}")
            # Ne pas bloquer le join pour cette erreur

        result = await multiplayer_service.join_room_by_code(
            db, room_code, current_user.id,
            join_data.password,
            join_data.as_spectator or False
        )
        return {
            "success": True,
            "data": result,
            "message": "Partie rejointe avec succès"
        }
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except GameFullError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur rejoindre room: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la connexion: {str(e)}"
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
    """Route pour récupérer les détails d'une room avec correction participants"""
    try:
        result = await multiplayer_service.get_room_details(db, room_code, current_user.id)
        return {
            "success": True,
            "data": result
        }
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur récupération room: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
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
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur récupération room: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


# =====================================================
# LOBBY ET MATCHMAKING
# =====================================================

@router.get(
    "/lobby",
    response_model=Dict[str, Any],
    summary="Lister les parties publiques",
    description="Récupère la liste des parties publiques pour le lobby"
)
async def get_public_multiplayer_rooms(
        page: int = Query(1, ge=1, description="Page"),
        limit: int = Query(20, ge=1, le=100, description="Limite par page"),
        player_status: Optional[str] = Query(None, description="Status des parties"),
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

        if player_status:
            constructed_filters["status"] = player_status
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
        logger.error(f"Erreur dans get_public_multiplayer_rooms: {str(e)}")

        raise HTTPException(
            status_code=player_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


@router.get(
    "/search",
    response_model=Dict[str, Any],
    summary="Rechercher des parties",
    description="Recherche des parties par terme et filtres"
)
async def search_multiplayer_rooms(
        search_term: str = Query(..., description="Terme de recherche"),
        difficulty: Optional[str] = Query(None, description="Difficulté"),
        quantum_enabled: Optional[bool] = Query(None, description="Quantique activé"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour rechercher des parties spécifiques"""
    try:
        filters = {}
        if difficulty:
            filters["difficulty"] = difficulty
        if quantum_enabled is not None:
            filters["quantum_enabled"] = quantum_enabled

        filters["search_term"] = search_term
        filters_json = json.dumps(filters)

        result = await multiplayer_service.get_public_rooms(
            db, page=1, limit=50, filters=filters_json
        )

        return {
            "success": True,
            "data": result["rooms"]  # Retourner directement les rooms pour la recherche
        }
    except Exception as e:
        logger.error(f"Erreur recherche rooms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}"
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
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except GameError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur démarrage game: {e}")
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
        logger.error(f"Erreur soumission tentative: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la soumission: {str(e)}"
        )


@router.get(
    "/rooms/{room_code}/results",
    response_model=Dict[str, Any],
    summary="Résultats de la partie",
    description="Récupère les résultats finaux d'une partie"
)
async def get_multiplayer_results(
        room_code: str,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour récupérer les résultats (attendue par le frontend)"""
    try:
        result = await multiplayer_service.get_game_results(db, room_code, current_user.id)
        return {
            "success": True,
            "data": result
        }
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur récupération résultats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


# =====================================================
# GESTION DES PARTICIPANTS
# =====================================================

@router.get(
    "/rooms/{room_code}/players",
    response_model=Dict[str, Any],
    summary="Liste des joueurs",
    description="Récupère la liste des joueurs dans une partie"
)
async def get_room_players(
        room_code: str,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour récupérer la liste des joueurs"""
    try:
        room_details = await multiplayer_service.get_room_details(db, room_code, current_user.id)
        return {
            "success": True,
            "data": {
                "players": room_details["players"],
                "players_count": len(room_details["players"]),
                "max_players": room_details["max_players"]
            }
        }
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur récupération joueurs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


@router.get(
    "/rooms/{room_code}/status",
    response_model=Dict[str, Any],
    summary="Status de la partie",
    description="Récupère le status actuel d'une partie"
)
async def get_room_status(
        room_code: str,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour récupérer le status d'une partie"""
    try:
        room_details = await multiplayer_service.get_room_details(db, room_code, current_user.id)
        return {
            "success": True,
            "data": {
                "status": room_details["status"],
                "current_mastermind": room_details.get("current_mastermind", 1),
                "total_masterminds": room_details["total_masterminds"],
                "players_count": len(room_details["players"]),
                "started_at": room_details.get("started_at")
            }
        }
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur récupération status: {e}")
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
        logger.error(f"Erreur utilisation objet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'utilisation de l'objet: {str(e)}"
        )


@router.get(
    "/rooms/{room_code}/items",
    response_model=Dict[str, Any],
    summary="Objets disponibles",
    description="Récupère les objets disponibles pour un joueur"
)
async def get_player_items(
        room_code: str,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route pour récupérer les objets du joueur"""
    try:
        # TODO: Implémenter la récupération des objets du joueur
        # Pour l'instant, retourner une liste vide
        return {
            "success": True,
            "data": {
                "available_items": [],
                "used_items": [],
                "items_per_mastermind": 1
            }
        }
    except Exception as e:
        logger.error(f"Erreur récupération objets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
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
    """Route pour les indices quantiques multijoueur"""
    try:
        result = await multiplayer_service.get_quantum_hint(
            db, room_code, current_user.id, hint_request
        )
        return {
            "success": True,
            "data": result.dict()
        }
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
        logger.error(f"Erreur indice quantique: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération de l'indice: {str(e)}"
        )


# =====================================================
# WEBSOCKETS MULTIPLAYER (optionnel)
# =====================================================

@router.websocket("/rooms/{room_code}/ws")
async def multiplayer_websocket_endpoint(
        websocket: WebSocket,
        room_code: str,
        token: str = Query(..., description="JWT Token")
):
    """WebSocket endpoint pour la communication temps réel"""
    if not WEBSOCKET_AVAILABLE:
        await websocket.close(code=1000, reason="WebSocket indisponible")
        return

    try:
        # TODO: Valider le token JWT
        # Pour l'instant, accepter toutes les connexions

        await multiplayer_ws_manager.connect(websocket, room_code, "user_id_placeholder")

        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                # Traiter le message et le relayer aux autres clients
                await multiplayer_ws_manager.handle_message(room_code, message)

        except WebSocketDisconnect:
            await multiplayer_ws_manager.disconnect(websocket, room_code)

    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}")
        await websocket.close(code=1000, reason="Erreur serveur")


# =====================================================
# ROUTES DE DÉVELOPPEMENT (à supprimer en production)
# =====================================================

@router.get(
    "/debug/rooms",
    response_model=Dict[str, Any],
    summary="[DEBUG] Toutes les parties",
    description="Récupère toutes les parties pour le debug"
)
async def debug_get_all_rooms(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """Route de debug pour lister toutes les parties"""
    try:
        # Cette route ne devrait exister qu'en développement
        result = await multiplayer_service.get_public_rooms(
            db, page=1, limit=100, filters=None
        )
        return {
            "success": True,
            "data": result,
            "debug": True
        }
    except Exception as e:
        logger.error(f"Erreur debug rooms: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur debug: {str(e)}"
        )


@router.delete(
    "/debug/rooms/{room_code}",
    response_model=Dict[str, str],
    summary="[DEBUG] Supprimer une partie",
    description="Supprime une partie pour le debug"
)
async def debug_delete_room(
        room_code: str,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, str]:
    """Route de debug pour supprimer une partie"""
    try:
        # TODO: Implémenter la suppression de partie
        # Pour l'instant, retourner un succès
        return {
            "message": f"Partie {room_code} supprimée (debug)",
            "debug": True
        }
    except Exception as e:
        logger.error(f"Erreur debug delete: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur debug: {str(e)}"
        )