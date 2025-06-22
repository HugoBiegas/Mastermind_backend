"""
Dépendances FastAPI pour Quantum Mastermind
Injection de dépendances pour l'authentification, base de données, etc.
CORRECTION: Implémentation complète des validations de jeu
"""
import hashlib
import time
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status, Request, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.user import User
from app.models.game import Game, GameParticipation, ParticipationStatus
from app.services.auth import auth_service
from app.utils.exceptions import (
    AuthenticationError, get_http_status_code, get_exception_details
)
from app.services.game import GameService

# === CONFIGURATION DE SÉCURITÉ ===

security = HTTPBearer(auto_error=False)


# === DÉPENDANCES DE BASE ===

async def get_database() -> AsyncSession:
    """
    Dépendance pour obtenir une session de base de données

    Returns:
        Session de base de données async
    """
    async for db in get_db():
        yield db


def get_game_service() -> GameService:
    """
    Dépendance pour obtenir une instance de GameService

    Returns:
        Instance de GameService
    """
    from app.services.game import GameService
    return GameService()

async def get_client_info(request: Request) -> Dict[str, Any]:
    """
    Extrait les informations client de la requête

    Args:
        request: Requête FastAPI

    Returns:
        Informations client (IP, User-Agent, etc.)
    """
    # Récupération de l'IP réelle (en tenant compte des proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    real_ip = request.headers.get("X-Real-IP")

    if forwarded_for:
        # Prendre la première IP de la liste
        client_ip = forwarded_for.split(",")[0].strip()
    elif real_ip:
        client_ip = real_ip
    else:
        client_ip = request.client.host if request.client else "unknown"

    return {
        'ip_address': client_ip,
        'user_agent': request.headers.get("User-Agent", "unknown"),
        'origin': request.headers.get("Origin"),
        'referer': request.headers.get("Referer"),
        'accept_language': request.headers.get("Accept-Language"),
        'request_id': request.headers.get("X-Request-ID")
    }


# === DÉPENDANCES D'AUTHENTIFICATION ===

async def get_current_user_token(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Extrait et valide le token Bearer de l'en-tête Authorization

    Args:
        credentials: Credentials HTTP Bearer

    Returns:
        Token JWT

    Raises:
        HTTPException: Si le token est manquant ou invalide
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification requis",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Schéma d'authentification invalide. Bearer requis",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return credentials.credentials


async def get_current_user(
        token: str = Depends(get_current_user_token),
        db: AsyncSession = Depends(get_database)
) -> User:
    """
    Récupère l'utilisateur actuel à partir du token JWT

    Args:
        token: Token JWT
        db: Session de base de données

    Returns:
        Utilisateur actuel

    Raises:
        HTTPException: Si le token est invalide ou l'utilisateur n'existe pas
    """
    try:
        user = await auth_service.get_current_user(db, token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide ou utilisateur introuvable",
                headers={"WWW-Authenticate": "Bearer"}
            )
        return user

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'authentification"
        )


async def get_current_user_optional(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        db: AsyncSession = Depends(get_database)
) -> Optional[User]:
    """
    Récupère l'utilisateur actuel (optionnel)

    Args:
        credentials: Credentials HTTP Bearer (optionnel)
        db: Session de base de données

    Returns:
        Utilisateur actuel ou None
    """
    if not credentials:
        return None

    try:
        user = await auth_service.get_current_user(db, credentials.credentials)
        return user
    except (AuthenticationError, Exception):
        return None


async def get_current_active_user(
        current_user: User = Depends(get_current_user)
) -> User:
    """
    Récupère l'utilisateur actuel s'il est actif

    Args:
        current_user: Utilisateur actuel

    Returns:
        Utilisateur actif

    Raises:
        HTTPException: Si l'utilisateur n'est pas actif
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte utilisateur désactivé"
        )
    return current_user


async def get_current_verified_user(
        current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Récupère l'utilisateur actuel s'il est vérifié

    Args:
        current_user: Utilisateur actuel

    Returns:
        Utilisateur vérifié

    Raises:
        HTTPException: Si l'utilisateur n'est pas vérifié
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email non vérifié. Vérifiez votre boîte de réception."
        )
    return current_user


async def get_current_superuser(
        current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Récupère l'utilisateur actuel s'il est superutilisateur

    Args:
        current_user: Utilisateur actuel

    Returns:
        Superutilisateur

    Raises:
        HTTPException: Si l'utilisateur n'est pas admin
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privilèges administrateur requis"
        )
    return current_user


# === DÉPENDANCES DE PAGINATION ===

class PaginationParams:
    """Paramètres de pagination"""

    def __init__(
            self,
            page: int = Query(default=1, ge=1, description="Numéro de page"),
            limit: int = Query(default=20, ge=1, le=100, description="Éléments par page")
    ):
        self.page = page
        self.limit = limit
        self.skip = (page - 1) * limit


async def get_pagination_params(
        page: int = Query(default=1, ge=1, description="Numéro de page"),
        limit: int = Query(default=20, ge=1, le=100, description="Éléments par page")
) -> PaginationParams:
    """
    Récupère les paramètres de pagination

    Args:
        page: Numéro de page
        limit: Nombre d'éléments par page

    Returns:
        Paramètres de pagination
    """
    return PaginationParams(page, limit)


# === DÉPENDANCES DE RECHERCHE ===

class SearchParams:
    """Paramètres de recherche"""

    def __init__(
            self,
            query: Optional[str] = Query(default=None, description="Terme de recherche"),
            sort_by: str = Query(default="created_at", description="Champ de tri"),
            sort_order: str = Query(default="desc", regex="^(asc|desc)$", description="Ordre de tri")
    ):
        self.query = query
        self.sort_by = sort_by
        self.sort_order = sort_order


async def get_search_params(
        query: Optional[str] = Query(default=None, description="Terme de recherche"),
        sort_by: str = Query(default="created_at", description="Champ de tri"),
        sort_order: str = Query(default="desc", regex="^(asc|desc)$", description="Ordre de tri")
) -> SearchParams:
    """
    Récupère les paramètres de recherche

    Args:
        query: Terme de recherche
        sort_by: Champ de tri
        sort_order: Ordre de tri

    Returns:
        Paramètres de recherche
    """
    return SearchParams(query, sort_by, sort_order)


# === DÉPENDANCES SPÉCIFIQUES AU JEU ===

async def validate_game_access(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> bool:
    """
    Valide que l'utilisateur peut accéder à une partie
    CORRECTION: Implémentation complète

    Args:
        game_id: ID de la partie
        current_user: Utilisateur actuel
        db: Session de base de données

    Returns:
        True si l'accès est autorisé

    Raises:
        HTTPException: Si l'accès est refusé
    """
    try:
        # Récupération de la partie
        stmt = select(Game).where(Game.id == game_id)
        result = await db.execute(stmt)
        game = result.scalar_one_or_none()

        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partie non trouvée"
            )

        # Accès autorisé si :
        # 1. L'utilisateur est le créateur
        if game.creator_id == current_user.id:
            return True

        # 2. L'utilisateur est admin
        if current_user.is_superuser:
            return True

        # 3. L'utilisateur participe à la partie
        participation_stmt = select(GameParticipation).where(
            GameParticipation.game_id == game_id,
            GameParticipation.player_id == current_user.id
        )
        participation_result = await db.execute(participation_stmt)
        participation = participation_result.scalar_one_or_none()

        if participation:
            return True

        # 4. La partie est publique et permet les spectateurs
        if not game.is_private and game.allow_spectators:
            return True

        # Accès refusé
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette partie"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la validation d'accès"
        )


async def validate_game_modification(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> bool:
    """
    Valide que l'utilisateur peut modifier une partie
    CORRECTION: Implémentation complète

    Args:
        game_id: ID de la partie
        current_user: Utilisateur actuel
        db: Session de base de données

    Returns:
        True si la modification est autorisée

    Raises:
        HTTPException: Si la modification est refusée
    """
    try:
        # Récupération de la partie
        stmt = select(Game).where(Game.id == game_id)
        result = await db.execute(stmt)
        game = result.scalar_one_or_none()

        if not game:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partie non trouvée"
            )

        # Modification autorisée si :
        # 1. L'utilisateur est le créateur
        if game.creator_id == current_user.id:
            return True

        # 2. L'utilisateur est admin
        if current_user.is_superuser:
            return True

        # Modification refusée
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le créateur ou un admin peut modifier cette partie"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la validation de modification"
        )


async def validate_game_participation(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> GameParticipation:
    """
    Valide que l'utilisateur participe activement à une partie

    Args:
        game_id: ID de la partie
        current_user: Utilisateur actuel
        db: Session de base de données

    Returns:
        Participation de l'utilisateur

    Raises:
        HTTPException: Si la participation n'est pas valide
    """
    try:
        # Récupération de la participation
        stmt = select(GameParticipation).where(
            GameParticipation.game_id == game_id,
            GameParticipation.player_id == current_user.id
        )
        result = await db.execute(stmt)
        participation = result.scalar_one_or_none()

        if not participation:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne participez pas à cette partie"
            )

        if participation.status == ParticipationStatus.DISCONNECTED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous avez quitté cette partie"
            )

        if participation.status == ParticipationStatus.ELIMINATED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous avez été éliminé de cette partie"
            )

        return participation

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la validation de participation"
        )


async def validate_uuid(
        uuid_str: str,
        field_name: str = "ID"
) -> UUID:
    """
    Valide et convertit une chaîne UUID

    Args:
        uuid_str: Chaîne UUID à valider
        field_name: Nom du champ pour l'erreur

    Returns:
        UUID validé

    Raises:
        HTTPException: Si l'UUID est invalide
    """
    try:
        return UUID(uuid_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} invalide: format UUID requis"
        )


# === DÉPENDANCES DE SÉCURITÉ AVANCÉE ===

async def check_api_key(
        api_key: Optional[str] = Query(default=None, description="Clé API")
) -> bool:
    """
    Vérifie la clé API (si configurée)

    Args:
        api_key: Clé API fournie

    Returns:
        True si la clé est valide

    Raises:
        HTTPException: Si la clé est invalide
    """
    # Pour l'instant, on accepte toutes les requêtes sans clé API
    # En production, implémenter la validation des clés API
    return True


async def rate_limit_check(
        request: Request,
        current_user: Optional[User] = Depends(get_current_user_optional)
) -> bool:
    """
    Vérifie les limites de taux de requêtes

    Args:
        request: Requête FastAPI
        current_user: Utilisateur actuel (optionnel)

    Returns:
        True si dans les limites

    Raises:
        HTTPException: Si les limites sont dépassées
    """
    # Pour l'instant, pas de limitation
    # En production, implémenter un système de rate limiting
    return True


# === DÉPENDANCES DE LOGGING ET MÉTRIQUES ===

async def log_request_metrics(
        request: Request,
        current_user: Optional[User] = Depends(get_current_user_optional),
        client_info: Dict[str, Any] = Depends(get_client_info)
) -> None:
    """
    Log les métriques de requête

    Args:
        request: Requête FastAPI
        current_user: Utilisateur actuel
        client_info: Informations client
    """
    # TODO: Implémenter le logging des métriques
    pass


# === HELPERS POUR LES EXCEPTIONS ===

def create_http_exception_from_error(error: Exception) -> HTTPException:
    """
    Crée une HTTPException à partir d'une exception métier
    CORRECTION: Gestion robuste des différents types d'exceptions
    """
    from app.utils.exceptions import BaseQuantumMastermindError

    # Cas 1: Exception métier héritant de BaseQuantumMastermindError
    if isinstance(error, BaseQuantumMastermindError):
        status_code = get_http_status_code(error)
        details = get_exception_details(error)

        return HTTPException(
            status_code=status_code,
            detail=details['message'],
            headers={"X-Error-Code": details.get('error_code')} if details.get('error_code') else None
        )

    # Cas 2: Exception Python standard (KeyError, ValueError, etc.)
    elif isinstance(error, (KeyError, ValueError, TypeError)):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur de validation: {str(error)}",
            headers={"X-Error-Code": "VALIDATION_ERROR"}
        )

    # Cas 3: Exception générique
    else:
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur inattendue: {str(error)}",
            headers={"X-Error-Code": "INTERNAL_ERROR"}
        )


# === MIDDLEWARE HELPERS ===

async def get_request_context(
        request: Request,
        client_info: Dict[str, Any] = Depends(get_client_info),
        current_user: Optional[User] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """
    Rassemble le contexte complet de la requête

    Args:
        request: Requête FastAPI
        client_info: Informations client
        current_user: Utilisateur actuel

    Returns:
        Contexte complet de la requête
    """
    return {
        'request_id': client_info.get('request_id') or f"req_{int(time.time())}",
        'method': request.method,
        'path': str(request.url.path),
        'query_params': dict(request.query_params),
        'client_info': client_info,
        'user_id': str(current_user.id) if current_user else None,
        'username': current_user.username if current_user else None,
        'is_authenticated': current_user is not None,
        'is_admin': current_user.is_superuser if current_user else False,
        'timestamp': time.time()
    }


# === EXPORTS ===

__all__ = [
    # Base
    "get_database", "get_client_info",

    # Authentification
    "get_current_user", "get_current_user_optional",
    "get_current_active_user", "get_current_verified_user", "get_current_superuser",

    # Services
    "get_game_service",

    # Pagination et recherche
    "PaginationParams", "SearchParams",
    "get_pagination_params", "get_search_params",

    # Validation de jeu
    "validate_game_access", "validate_game_modification", "validate_game_participation",

    # Utilitaires
    "validate_uuid", "create_http_exception_from_error",

    # Sécurité
    "check_api_key", "rate_limit_check",

    # Logging
    "log_request_metrics", "get_request_context"
]