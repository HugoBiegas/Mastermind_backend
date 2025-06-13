"""
Dépendances FastAPI pour Quantum Mastermind
Injection de dépendances pour l'authentification, base de données, etc.
"""
from typing import Any, Dict, Generator, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import jwt_manager
from app.models.user import User
from app.services.auth import auth_service
from app.utils.exceptions import (
    AuthenticationError, AuthorizationError,
    get_http_status_code, get_exception_details
)

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
            detail="Schéma d'authentification invalide. Utilisez Bearer",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return credentials.credentials


async def get_current_user(
        db: AsyncSession = Depends(get_database),
        token: str = Depends(get_current_user_token)
) -> User:
    """
    Récupère l'utilisateur actuel à partir du token JWT

    Args:
        db: Session de base de données
        token: Token JWT

    Returns:
        Utilisateur authentifié

    Raises:
        HTTPException: Si l'utilisateur n'est pas trouvé ou le token invalide
    """
    try:
        user = await auth_service.get_current_user(db, token)
        return user
    except AuthenticationError as e:
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la vérification de l'authentification"
        )


async def get_current_active_user(
        current_user: User = Depends(get_current_user)
) -> User:
    """
    Vérifie que l'utilisateur actuel est actif

    Args:
        current_user: Utilisateur authentifié

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
    Vérifie que l'utilisateur actuel a vérifié son email

    Args:
        current_user: Utilisateur actif

    Returns:
        Utilisateur vérifié

    Raises:
        HTTPException: Si l'email n'est pas vérifié
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vérification email requise"
        )
    return current_user


async def get_current_superuser(
        current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Vérifie que l'utilisateur actuel est un superuser

    Args:
        current_user: Utilisateur actif

    Returns:
        Superutilisateur

    Raises:
        HTTPException: Si l'utilisateur n'est pas superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissions administrateur requises"
        )
    return current_user


# === DÉPENDANCES OPTIONNELLES ===

async def get_current_user_optional(
        db: AsyncSession = Depends(get_database),
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """
    Récupère l'utilisateur actuel si authentifié, None sinon

    Args:
        db: Session de base de données
        credentials: Credentials optionnels

    Returns:
        Utilisateur authentifié ou None
    """
    if not credentials:
        return None

    try:
        user = await auth_service.get_current_user(db, credentials.credentials)
        return user if user.is_active else None
    except:
        return None


# === DÉPENDANCES DE VALIDATION DE RESSOURCES ===

async def validate_user_access(
        target_user_id: UUID,
        current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Valide que l'utilisateur actuel peut accéder aux données d'un autre utilisateur

    Args:
        target_user_id: ID de l'utilisateur cible
        current_user: Utilisateur actuel

    Returns:
        Utilisateur actuel si autorisé

    Raises:
        HTTPException: Si l'accès n'est pas autorisé
    """
    # L'utilisateur peut accéder à ses propres données ou être admin
    if current_user.id != target_user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès non autorisé à cette ressource"
        )
    return current_user


def create_game_access_validator(require_host: bool = False):
    """
    Crée un validateur d'accès aux parties

    Args:
        require_host: Si True, nécessite d'être l'hôte de la partie

    Returns:
        Fonction de validation
    """

    async def validate_game_access(
            game_id: UUID,
            current_user: User = Depends(get_current_active_user),
            db: AsyncSession = Depends(get_database)
    ) -> User:
        """Valide l'accès à une partie"""
        # TODO: Implémenter la validation d'accès aux parties
        # Une fois que le service de jeu est complètement intégré

        # Pour l'instant, permet l'accès si l'utilisateur est authentifié
        return current_user

    return validate_game_access


# === DÉPENDANCES DE PAGINATION ===

class PaginationParams:
    """Paramètres de pagination"""

    def __init__(
            self,
            page: int = 1,
            page_size: int = 20,
            sort_by: Optional[str] = None,
            sort_order: str = "desc"
    ):
        # Validation des paramètres
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 100)  # Limite à 100
        self.sort_by = sort_by
        self.sort_order = sort_order if sort_order in ["asc", "desc"] else "desc"

    @property
    def offset(self) -> int:
        """Calcule l'offset pour la pagination"""
        return (self.page - 1) * self.page_size


async def get_pagination_params(
        page: int = 1,
        page_size: int = 20,
        sort_by: Optional[str] = None,
        sort_order: str = "desc"
) -> PaginationParams:
    """
    Dépendance pour les paramètres de pagination

    Args:
        page: Numéro de page (commence à 1)
        page_size: Taille de la page (max 100)
        sort_by: Champ de tri
        sort_order: Ordre de tri (asc/desc)

    Returns:
        Paramètres de pagination validés
    """
    return PaginationParams(page, page_size, sort_by, sort_order)


# === DÉPENDANCES DE RECHERCHE ===

class SearchParams:
    """Paramètres de recherche"""

    def __init__(
            self,
            q: Optional[str] = None,
            category: Optional[str] = None,
            status: Optional[str] = None,
            limit: int = 20
    ):
        self.query = q.strip() if q else None
        self.category = category
        self.status = status
        self.limit = min(max(1, limit), 100)


async def get_search_params(
        q: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20
) -> SearchParams:
    """
    Dépendance pour les paramètres de recherche

    Args:
        q: Terme de recherche
        category: Catégorie
        status: Statut
        limit: Limite de résultats

    Returns:
        Paramètres de recherche validés
    """
    return SearchParams(q, category, status, limit)


# === DÉPENDANCES DE CACHE ===

async def get_cache_key(
        request: Request,
        current_user: Optional[User] = Depends(get_current_user_optional)
) -> str:
    """
    Génère une clé de cache pour la requête

    Args:
        request: Requête FastAPI
        current_user: Utilisateur actuel (optionnel)

    Returns:
        Clé de cache unique
    """
    # Construction de la clé de cache
    cache_parts = [
        request.method,
        str(request.url.path),
        str(sorted(request.query_params.items())),
    ]

    if current_user:
        cache_parts.append(f"user:{current_user.id}")

    # Hash de la clé pour éviter les clés trop longues
    import hashlib
    cache_key = "|".join(cache_parts)
    return hashlib.md5(cache_key.encode()).hexdigest()


# === DÉPENDANCES DE RATE LIMITING ===

async def check_rate_limit(
        request: Request,
        client_info: Dict[str, Any] = Depends(get_client_info)
) -> bool:
    """
    Vérifie les limites de taux de requêtes

    Args:
        request: Requête FastAPI
        client_info: Informations client

    Returns:
        True si dans les limites

    Raises:
        HTTPException: Si limite dépassée
    """
    # TODO: Implémenter le rate limiting avec Redis
    # Pour l'instant, toujours autoriser
    return True


# === DÉPENDANCES DE MONITORING ===

async def log_request_metrics(
        request: Request,
        client_info: Dict[str, Any] = Depends(get_client_info)
) -> None:
    """
    Log les métriques de requête pour le monitoring

    Args:
        request: Requête FastAPI
        client_info: Informations client
    """
    # TODO: Implémenter le logging des métriques
    pass


# === HELPERS POUR LES EXCEPTIONS ===

def create_http_exception_from_error(error: Exception) -> HTTPException:
    """
    Crée une HTTPException à partir d'une exception métier

    Args:
        error: Exception à convertir

    Returns:
        HTTPException appropriée
    """
    status_code = get_http_status_code(error)
    details = get_exception_details(error)

    return HTTPException(
        status_code=status_code,
        detail=details['message'],
        headers={"X-Error-Code": details['error']} if details['error'] else None
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
    import time

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