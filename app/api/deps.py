"""
Dépendances FastAPI pour Quantum Mastermind
Injection de dépendances pour l'authentification, base de données, etc.
"""
import hashlib
import time
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status, Request, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.services.auth import auth_service
from app.utils.exceptions import (
    AuthenticationError, get_http_status_code, get_exception_details
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
            detail="Schéma d'authentification invalide. Utilisez 'Bearer token'",
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
        Utilisateur actuel

    Raises:
        HTTPException: Si le token est invalide ou l'utilisateur n'existe pas
    """
    try:
        user = await auth_service.get_current_user(db, token)
        return user
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la vérification de l'authentification"
        )


async def get_current_user_optional(
        db: AsyncSession = Depends(get_database),
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """
    Récupère l'utilisateur actuel de manière optionnelle

    Args:
        db: Session de base de données
        credentials: Credentials optionnelles

    Returns:
        Utilisateur actuel ou None si non authentifié
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        user = await auth_service.get_current_user(db, token)
        return user
    except:
        return None


async def get_current_active_user(
        current_user: User = Depends(get_current_user)
) -> User:
    """
    Vérifie que l'utilisateur actuel est actif

    Args:
        current_user: Utilisateur actuel

    Returns:
        Utilisateur actif

    Raises:
        HTTPException: Si l'utilisateur est inactif
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte utilisateur inactif"
        )
    return current_user


async def get_current_verified_user(
        current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Vérifie que l'utilisateur actuel est vérifié (email confirmé)

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
            detail="Email non vérifié. Vérifiez votre boîte email."
        )
    return current_user


async def get_current_superuser(
        current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Vérifie que l'utilisateur actuel est un super-utilisateur

    Args:
        current_user: Utilisateur actuel

    Returns:
        Super-utilisateur

    Raises:
        HTTPException: Si l'utilisateur n'est pas un super-utilisateur
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privilèges de super-utilisateur requis"
        )
    return current_user


# === DÉPENDANCES DE VALIDATION D'ACCÈS ===

async def validate_user_access(
        target_user_id: UUID,
        current_user: User = Depends(get_current_active_user)
) -> bool:
    """
    Valide que l'utilisateur peut accéder aux données d'un autre utilisateur

    Args:
        target_user_id: ID de l'utilisateur cible
        current_user: Utilisateur actuel

    Returns:
        True si l'accès est autorisé

    Raises:
        HTTPException: Si l'accès est refusé
    """
    # L'utilisateur peut accéder à ses propres données
    if current_user.id == target_user_id:
        return True

    # Les super-utilisateurs peuvent accéder à tout
    if current_user.is_superuser:
        return True

    # TODO: Ajouter d'autres règles d'accès (amis, parties partagées, etc.)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Accès non autorisé aux données de cet utilisateur"
    )


# === DÉPENDANCES DE PAGINATION ===

class PaginationParams:
    """Paramètres de pagination standardisés"""

    def __init__(
            self,
            skip: int = Query(0, ge=0, description="Nombre d'éléments à ignorer"),
            limit: int = Query(20, ge=1, le=100, description="Nombre d'éléments à retourner")
    ):
        self.skip = skip
        self.limit = limit

    @property
    def offset(self) -> int:
        """Alias pour skip (compatibilité SQLAlchemy)"""
        return self.skip


async def get_pagination_params(
        skip: int = Query(0, ge=0, description="Nombre d'éléments à ignorer"),
        limit: int = Query(20, ge=1, le=100, description="Nombre d'éléments à retourner")
) -> PaginationParams:
    """
    Dépendance pour les paramètres de pagination

    Args:
        skip: Nombre d'éléments à ignorer
        limit: Nombre d'éléments à retourner

    Returns:
        Paramètres de pagination validés
    """
    return PaginationParams(skip, limit)


# === DÉPENDANCES DE RECHERCHE ===

class SearchParams:
    """Paramètres de recherche standardisés"""

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
        q: Optional[str] = Query(None, description="Terme de recherche"),
        category: Optional[str] = Query(None, description="Catégorie"),
        status: Optional[str] = Query(None, description="Statut"),
        limit: int = Query(20, ge=1, le=100, description="Limite de résultats")
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


# === DÉPENDANCES DE VALIDATION D'ENTRÉE ===

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


# === DÉPENDANCES SPÉCIFIQUES AU JEU ===

async def validate_game_access(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> bool:
    """
    Valide que l'utilisateur peut accéder à une partie

    Args:
        game_id: ID de la partie
        current_user: Utilisateur actuel
        db: Session de base de données

    Returns:
        True si l'accès est autorisé

    Raises:
        HTTPException: Si l'accès est refusé
    """
    # TODO: Implémenter la logique de validation d'accès aux parties
    # - Créateur de la partie
    # - Participant à la partie
    # - Partie publique
    # - Admin
    return True


async def validate_game_modification(
        game_id: UUID,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_database)
) -> bool:
    """
    Valide que l'utilisateur peut modifier une partie

    Args:
        game_id: ID de la partie
        current_user: Utilisateur actuel
        db: Session de base de données

    Returns:
        True si la modification est autorisée

    Raises:
        HTTPException: Si la modification est refusée
    """
    # TODO: Implémenter la logique de validation de modification
    # - Créateur de la partie
    # - Admin
    # - Modérateur (si implémenté)
    return True


# === DÉPENDANCES DE SÉCURITÉ AVANCÉE ===

async def check_api_key(
        api_key: Optional[str] = Query(None, description="Clé API (optionnelle)")
) -> Optional[str]:
    """
    Vérifie une clé API optionnelle pour les accès publics

    Args:
        api_key: Clé API

    Returns:
        Clé API validée ou None
    """
    # TODO: Implémenter la validation des clés API
    return api_key


async def require_api_key(
        api_key: str = Query(..., description="Clé API requise")
) -> str:
    """
    Requiert une clé API valide

    Args:
        api_key: Clé API

    Returns:
        Clé API validée

    Raises:
        HTTPException: Si la clé API est invalide
    """
    # TODO: Implémenter la validation stricte des clés API
    if not api_key or len(api_key) < 32:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide ou manquante"
        )
    return api_key


# === DÉPENDANCES DE FEATURE FLAGS ===

async def check_feature_flag(
        feature_name: str,
        current_user: Optional[User] = Depends(get_current_user_optional)
) -> bool:
    """
    Vérifie si une fonctionnalité est activée pour l'utilisateur

    Args:
        feature_name: Nom de la fonctionnalité
        current_user: Utilisateur actuel

    Returns:
        True si la fonctionnalité est activée
    """
    # TODO: Implémenter un système de feature flags
    # - Flags globaux
    # - Flags par utilisateur
    # - Flags par rôle
    # - Tests A/B

    # Pour l'instant, tout est activé
    return True


# === DÉPENDANCES DE LOCALISATION ===

async def get_user_locale(
        request: Request,
        current_user: Optional[User] = Depends(get_current_user_optional)
) -> str:
    """
    Détermine la locale de l'utilisateur

    Args:
        request: Requête FastAPI
        current_user: Utilisateur actuel

    Returns:
        Code de locale (ex: 'fr-FR', 'en-US')
    """
    # Priorité :
    # 1. Préférence utilisateur (si connecté)
    # 2. Header Accept-Language
    # 3. Défaut français

    if current_user and hasattr(current_user, 'preferred_locale'):
        return current_user.preferred_locale

    accept_language = request.headers.get("Accept-Language", "")
    if "fr" in accept_language.lower():
        return "fr-FR"
    elif "en" in accept_language.lower():
        return "en-US"

    return "fr-FR"  # Défaut français pour Quantum Mastermind