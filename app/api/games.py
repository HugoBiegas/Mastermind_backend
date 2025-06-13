"""
Routes de gestion des jeux pour Quantum Mastermind
Création de parties, gameplay, statistiques, recherche
"""
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_database, get_current_active_user, get_current_verified_user,
    get_pagination_params, get_search_params, create_http_exception_from_error,
    PaginationParams, SearchParams
)
from app.models.user import User
from app.models.game import GameType, GameMode, GameStatus, Difficulty
from app.services.game import game_service
from app.services.quantum import quantum_service
from app.schemas.game import (
    GameCreate, GameUpdate, GameJoin, AttemptCreate,
    GameInfo, GameFull, GamePublic, GameList, GameSearch,
    AttemptResult, SolutionHint, SolutionReveal
)
from app.schemas.quantum import QuantumHint
from app.schemas.auth import MessageResponse
from app.utils.exceptions import (
    EntityNotFoundError, GameError, GameNotActiveError,
    GameFullError, ValidationError
)

# Configuration du router
router = APIRouter(prefix="/games", tags=["Jeux"])


# === ROUTES DE CRÉATION ET GESTION DES PARTIES ===

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
    - **difficulty**: Niveau de difficulté (easy, normal, hard, expert)
    - **max_attempts**: Nombre maximum de tentatives (1-20)
    - **time_limit**: Limite de temps en secondes (optionnel)
    - **max_players**: Nombre maximum de joueurs (1-8)
    - **room_code**: Code de room personnalisé (optionnel)
    - **is_private**: Partie privée
    - **password**: Mot de passe pour rejoindre (optionnel)
    - **settings**: Paramètres personnalisés
    """
    try:
        game_info = await game_service.create_game(
            db, game_data, creator_id=current_user.id
        )
        return game_info

    except ValidationError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la création de la partie"
        )


@router.post(
    "/join",
    response_model=Dict[str, Any],
    summary="Rejoindre une partie",
    description="Rejoint une partie existante avec un code de room"
)
async def join_game(
        join_data: GameJoin,
        current_user: User = Depends(get_current_verified_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Rejoint une partie existante

    - **room_code**: Code de la room à rejoindre
    - **password**: Mot de passe si requis
    - **player_name**: Nom d'affichage personnalisé (optionnel)
    """
    try:
        join_info = await game_service.join_game(
            db, join_data, user_id=current_user.id
        )
        return join_info

    except (EntityNotFoundError, GameFullError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la tentative de rejoindre la partie"
        )


@router.post(
    "/{game_id}/start",
    response_model=MessageResponse,
    summary="Démarrer une partie",
    description="Démarre une partie (hôte uniquement)"
)
async def start_game(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Démarre une partie (accessible uniquement à l'hôte)

    - **game_id**: ID de la partie à démarrer
    """
    try:
        result = await game_service.start_game(
            db, game_id, user_id=current_user.id
        )
        return MessageResponse(**result)

    except (EntityNotFoundError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du démarrage de la partie"
        )


# === ROUTES DE GAMEPLAY ===

@router.post(
    "/{game_id}/attempt",
    response_model=Dict[str, Any],
    summary="Faire une tentative",
    description="Effectue une tentative dans la partie"
)
async def make_attempt(
        game_id: UUID,
        attempt_data: AttemptCreate,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Effectue une tentative de solution dans la partie

    - **guess**: Tentative (4 couleurs)
    - **use_quantum_measurement**: Utiliser une mesure quantique
    - **measured_position**: Position à mesurer (0-3, optionnel)
    """
    try:
        result = await game_service.make_attempt(
            db, game_id, current_user.id, attempt_data
        )
        return result

    except (EntityNotFoundError, GameNotActiveError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'exécution de la tentative"
        )


@router.get(
    "/{game_id}/state",
    response_model=Dict[str, Any],
    summary="État de la partie",
    description="Récupère l'état actuel de la partie"
)
async def get_game_state(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Récupère l'état complet de la partie

    Inclut :
    - Informations de la partie
    - Liste des joueurs
    - Historique des tentatives (pour le joueur actuel)
    - Statut de progression
    """
    try:
        game_state = await game_service.get_game_state(
            db, game_id, user_id=current_user.id
        )
        return game_state

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération de l'état de la partie"
        )


@router.get(
    "/{game_id}/quantum-hint",
    response_model=QuantumHint,
    summary="Indice quantique",
    description="Obtient un indice quantique pour la partie"
)
async def get_quantum_hint(
        game_id: UUID,
        hint_type: str = Query(..., description="Type d'indice (grover, measurement, superposition)"),
        position: int = Query(None, ge=0, le=3, description="Position pour l'indice (0-3)"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> QuantumHint:
    """
    Obtient un indice quantique pour aider à résoudre la partie

    Types d'indices disponibles :
    - **grover**: Utilise l'algorithme de Grover pour révéler une couleur
    - **measurement**: Effectue une mesure quantique directe
    - **superposition**: Révèle les états de superposition
    - **entanglement**: Informe sur les intrications

    - **hint_type**: Type d'indice désiré
    - **position**: Position concernée (optionnel selon le type)
    """
    try:
        hint = await game_service.get_quantum_hint(
            db, game_id, current_user.id, hint_type, position
        )
        return hint

    except (EntityNotFoundError, ValidationError) as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la génération de l'indice quantique"
        )


# === ROUTES DE CONSULTATION ===

@router.get(
    "/{game_id}",
    response_model=GameInfo,
    summary="Informations de partie",
    description="Récupère les informations d'une partie"
)
async def get_game_info(
        game_id: UUID,
        db: AsyncSession = Depends(get_database)
) -> GameInfo:
    """
    Récupère les informations publiques d'une partie

    - **game_id**: ID de la partie
    """
    try:
        game_state = await game_service.get_game_state(db, game_id)
        return GameInfo(**game_state)

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des informations de la partie"
        )


@router.get(
    "/room/{room_code}",
    response_model=GameInfo,
    summary="Partie par code room",
    description="Récupère une partie par son code de room"
)
async def get_game_by_room_code(
        room_code: str,
        db: AsyncSession = Depends(get_database)
) -> GameInfo:
    """
    Récupère une partie par son code de room

    - **room_code**: Code de la room
    """
    try:
        # Utilisation du service pour trouver la partie par room_code
        from app.repositories.game import GameRepository

        game_repo = GameRepository()
        game = await game_repo.get_by_room_id(db, room_code, with_players=True)

        if not game:
            raise EntityNotFoundError("Partie non trouvée")

        return GameInfo.from_orm(game)

    except EntityNotFoundError as e:
        raise create_http_exception_from_error(e)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération de la partie"
        )


# === ROUTES DE RECHERCHE ET LISTING ===

@router.get(
    "/",
    response_model=List[Dict[str, Any]],
    summary="Parties actives",
    description="Liste les parties actives disponibles"
)
async def get_active_games(
        game_type: GameType = Query(None, description="Type de jeu"),
        has_slots: bool = Query(False, description="Seulement les parties avec places libres"),
        limit: int = Query(50, ge=1, le=100, description="Nombre maximum de parties"),
        db: AsyncSession = Depends(get_database)
) -> List[Dict[str, Any]]:
    """
    Récupère la liste des parties actives

    - **game_type**: Filtrer par type de jeu (optionnel)
    - **has_slots**: Seulement les parties avec places libres
    - **limit**: Nombre maximum de parties (max 100)
    """
    try:
        games = await game_service.get_active_games(
            db, game_type=game_type, has_slots=has_slots, limit=limit
        )
        return games

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des parties actives"
        )


@router.post(
    "/search",
    response_model=Dict[str, Any],
    summary="Rechercher des parties",
    description="Recherche des parties avec critères avancés"
)
async def search_games(
        search_criteria: GameSearch,
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Recherche des parties avec critères avancés

    - **game_type**: Type de jeu
    - **game_mode**: Mode de jeu
    - **status**: Statut de la partie
    - **difficulty**: Niveau de difficulté
    - **has_slots**: Parties avec places libres
    - **created_by**: Créateur de la partie
    - **sort_by**: Champ de tri
    - **sort_order**: Ordre de tri
    - **page**: Numéro de page
    - **page_size**: Taille de la page
    """
    try:
        results = await game_service.search_games(db, search_criteria)
        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la recherche de parties"
        )


@router.get(
    "/my-games",
    response_model=List[Dict[str, Any]],
    summary="Mes parties",
    description="Récupère les parties de l'utilisateur connecté"
)
async def get_my_games(
        status: GameStatus = Query(None, description="Filtrer par statut"),
        limit: int = Query(20, ge=1, le=100, description="Nombre maximum de parties"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> List[Dict[str, Any]]:
    """
    Récupère les parties de l'utilisateur connecté

    - **status**: Filtrer par statut de partie (optionnel)
    - **limit**: Nombre maximum de parties
    """
    try:
        games = await game_service.get_user_games(
            db, current_user.id, status=status, limit=limit
        )
        return games

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération de vos parties"
        )


# === ROUTES DE STATISTIQUES ===

@router.get(
    "/stats/global",
    response_model=Dict[str, Any],
    summary="Statistiques globales",
    description="Récupère les statistiques globales des jeux"
)
async def get_global_game_statistics(
        period_days: int = Query(30, ge=1, le=365, description="Période en jours"),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Récupère les statistiques globales des jeux

    - **period_days**: Période en jours pour les statistiques
    """
    try:
        from app.repositories.game import GameRepository

        game_repo = GameRepository()
        stats = await game_repo.get_game_statistics(db, period_days=period_days)
        return stats

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des statistiques globales"
        )


@router.get(
    "/stats/user/{user_id}",
    response_model=Dict[str, Any],
    summary="Statistiques utilisateur jeux",
    description="Récupère les statistiques de jeu d'un utilisateur"
)
async def get_user_game_statistics(
        user_id: UUID,
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Récupère les statistiques de jeu d'un utilisateur

    - **user_id**: ID de l'utilisateur
    """
    try:
        from app.repositories.game import GameRepository

        game_repo = GameRepository()
        stats = await game_repo.get_user_game_stats(db, user_id)
        return stats

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des statistiques utilisateur"
        )


# === ROUTES QUANTIQUES ===

@router.post(
    "/quantum/generate-solution",
    response_model=Dict[str, Any],
    summary="Générer solution quantique",
    description="Génère une solution quantique pour test/développement"
)
async def generate_quantum_solution(
        difficulty: Difficulty = Query(Difficulty.NORMAL, description="Niveau de difficulté"),
        seed: str = Query(None, description="Seed pour reproductibilité"),
        current_user: User = Depends(get_current_verified_user)
) -> Dict[str, Any]:
    """
    Génère une solution quantique (pour développement et tests)

    - **difficulty**: Niveau de difficulté
    - **seed**: Seed pour la reproductibilité (optionnel)
    """
    try:
        solution = await quantum_service.generate_quantum_mastermind_solution(
            difficulty=difficulty.value, seed=seed
        )

        return {
            "classical_solution": solution.classical_solution,
            "quantum_encoding": solution.quantum_encoding,
            "entanglement_map": solution.entanglement_map,
            "superposition_states": solution.superposition_states,
            "generation_seed": solution.generation_seed
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la génération de la solution quantique"
        )


@router.post(
    "/quantum/analyze-attempt",
    response_model=Dict[str, Any],
    summary="Analyser tentative quantique",
    description="Analyse une tentative avec les données quantiques"
)
async def analyze_quantum_attempt(
        attempt: List[str] = Query(..., description="Tentative à analyser"),
        game_id: UUID = Query(..., description="ID de la partie"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> Dict[str, Any]:
    """
    Analyse une tentative avec les algorithmes quantiques

    - **attempt**: Tentative à analyser (4 couleurs)
    - **game_id**: ID de la partie pour le contexte
    """
    try:
        # TODO: Récupérer la solution quantique de la partie
        # Pour l'instant, génération d'une solution factice
        solution = await quantum_service.generate_quantum_mastermind_solution()

        analysis = await quantum_service.analyze_quantum_attempt(solution, attempt)
        return analysis

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'analyse quantique de la tentative"
        )


# === ROUTES D'ADMINISTRATION (pour les modérateurs) ===

@router.put(
    "/admin/{game_id}",
    response_model=MessageResponse,
    summary="Modérer une partie",
    description="Actions de modération sur une partie"
)
async def moderate_game(
        game_id: UUID,
        action: str = Query(..., description="Action de modération"),
        reason: str = Query(..., description="Raison de l'action"),
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> MessageResponse:
    """
    Effectue des actions de modération sur une partie

    Actions disponibles :
    - pause: Mettre en pause
    - resume: Reprendre
    - terminate: Terminer
    - kick_player: Expulser un joueur
    - ban_player: Bannir un joueur

    - **action**: Action à effectuer
    - **reason**: Raison de l'action (obligatoire)
    """
    # Vérification des permissions (admin ou modérateur)
    if not current_user.is_superuser:
        # TODO: Ajouter un système de modérateurs
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissions de modération requises"
        )

    try:
        # TODO: Implémenter les actions de modération
        return MessageResponse(
            message=f"Action '{action}' effectuée sur la partie {game_id}",
            details={"action": action, "reason": reason, "moderator": str(current_user.id)}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'action de modération"
        )


# === ROUTES DE DEBUG (à désactiver en production) ===

if False:  # Activer uniquement en développement
    @router.get(
        "/debug/{game_id}/solution",
        summary="Solution de debug",
        description="Révèle la solution pour debug (DEV uniquement)"
    )
    async def debug_reveal_solution(
            game_id: UUID,
            current_user: User = Depends(get_current_active_user),
            db: AsyncSession = Depends(get_database)
    ) -> Dict[str, Any]:
        """Route de debug pour révéler la solution (développement uniquement)"""
        try:
            from app.repositories.game import GameRepository

            game_repo = GameRepository()
            game = await game_repo.get_by_id(db, game_id)

            if not game:
                raise EntityNotFoundError("Partie non trouvée")

            return {
                "game_id": str(game_id),
                "classical_solution": game.classical_solution,
                "quantum_solution": game.quantum_solution,
                "solution_hash": game.solution_hash,
                "debug_mode": True
            }

        except Exception as e:
            return {"error": str(e)}