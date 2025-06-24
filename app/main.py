"""
Point d'entrée principal de l'application Quantum Mastermind
MODIFIÉ: Ajout des routes quantiques et configuration étendue
CORRECTION: Ajout de l'initialisation de la base de données dans le cycle de vie
NOUVEAU: Ajout du support multijoueur complet
"""
import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import auth, users, games

# NOUVEAU: Import conditionnel du multiplayer
try:
    from app.api import multiplayer
    MULTIPLAYER_AVAILABLE = True
except ImportError:
    MULTIPLAYER_AVAILABLE = False
    print("⚠️  Module multiplayer non trouvé, fonctionnalités multijoueur désactivées")

from app.core.config import settings
from app.core.database import init_db, close_db
from app.services.quantum import quantum_service

# CORRECTION: Import conditionnel des WebSockets multiplayer
try:
    from app.websocket.multiplayer import multiplayer_ws_manager, initialize_multiplayer_websocket, cleanup_multiplayer_websocket
    WEBSOCKET_MULTIPLAYER_AVAILABLE = True
except ImportError:
    WEBSOCKET_MULTIPLAYER_AVAILABLE = False
    print("⚠️  WebSocket multiplayer non trouvé")
    # Fonctions vides pour éviter les erreurs
    async def initialize_multiplayer_websocket():
        pass
    async def cleanup_multiplayer_websocket():
        pass

from app.utils.exceptions import (
    BaseQuantumMastermindError, get_http_status_code,
    get_exception_details
)
import logging

# Configuration du logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestionnaire de cycle de vie de l'application - CORRIGÉ
    NOUVEAU: Test du backend quantique au démarrage
    CORRECTION: Ajout de l'initialisation de la base de données
    CORRECTION: Gestion correcte du cycle de vie des WebSockets
    """
    # =====================================================
    # PHASE DE DÉMARRAGE
    # =====================================================
    logger.info("🚀 Démarrage de Quantum Mastermind API")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # CORRECTION: Initialisation de la base de données
    logger.info("🗃️  Initialisation de la base de données...")
    try:
        await init_db()
        logger.info("✅ Base de données initialisée avec succès")
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'initialisation de la base de données: {e}")
        raise

    # NOUVEAU: Initialisation des WebSockets multijoueur (si disponible)
    websocket_initialized = False
    if WEBSOCKET_MULTIPLAYER_AVAILABLE:
        logger.info("🔌 Initialisation des WebSockets multijoueur...")
        try:
            await initialize_multiplayer_websocket()
            websocket_initialized = True
            logger.info("✅ WebSockets multijoueur initialisés")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation WebSocket: {e}")
    else:
        logger.warning("⚠️  WebSockets multijoueur non disponibles")

    # Test du système quantique au démarrage
    try:
        quantum_status = await quantum_service.test_quantum_backend()
        if quantum_status["status"] == "healthy":
            logger.info("✅ Backend quantique opérationnel")
            logger.info(f"   - Backend: {quantum_status.get('backend', 'N/A')}")
            logger.info(f"   - Version Qiskit: {quantum_status.get('qiskit_version', 'N/A')}")
            logger.info("   - Algorithmes disponibles:")
            for algo in quantum_status.get("available_algorithms", []):
                logger.info(f"     • {algo}")
        else:
            logger.warning(f"⚠️  Backend quantique en mode dégradé: {quantum_status.get('message', 'N/A')}")
    except Exception as e:
        logger.error(f"❌ Erreur lors du test quantique: {e}")

    logger.info("🎯 Application prête à traiter les requêtes")

    # =====================================================
    # YIELD - L'APPLICATION FONCTIONNE ICI
    # =====================================================
    yield

    # =====================================================
    # PHASE D'ARRÊT
    # =====================================================
    logger.info("🔌 Arrêt de l'application...")

    # CORRECTION: Fermeture des WebSockets seulement à l'arrêt
    if websocket_initialized and WEBSOCKET_MULTIPLAYER_AVAILABLE:
        logger.info("🔌 Fermeture des WebSockets multijoueur...")
        try:
            await cleanup_multiplayer_websocket()
            logger.info("✅ WebSockets fermés proprement")
        except Exception as e:
            logger.error(f"❌ Erreur lors de la fermeture WebSocket: {e}")

    # Fermeture de la base de données
    logger.info("🗃️  Fermeture de la base de données...")
    try:
        await close_db()
        logger.info("✅ Base de données fermée proprement")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la fermeture de la DB: {e}")

    logger.info("⚛️  Arrêt du backend quantique...")
    logger.info("✅ Application fermée proprement")


# === CONFIGURATION DE L'APPLICATION ===

app = FastAPI(
    title="🎯⚛️ Quantum Mastermind API",
    description=f"""
    API REST pour le jeu Quantum Mastermind intégrant l'informatique quantique.
    
    ## 🎮 Fonctionnalités
    
    - **Modes de jeu** : Solo classique, solo quantique{", multijoueur temps réel" if MULTIPLAYER_AVAILABLE else ""}
    - **Hints quantiques** : Utilisation d'algorithmes de Grover, superposition, intrication
    {f"- **Temps réel** : WebSockets pour le multijoueur avec événements en direct" if WEBSOCKET_MULTIPLAYER_AVAILABLE else ""}
    - **Sécurité** : Authentification JWT, validation des données
    - **Performance** : Cache Redis, pagination, rate limiting
    
    ## ⚛️ Informatique Quantique
    
    - **Backend** : Qiskit avec simulateurs et accès aux ordinateurs quantiques IBM
    - **Algorithmes** : Grover, superposition, détection d'intrication
    - **Optimisation** : Fallbacks classiques en cas d'indisponibilité
    {f"- **Multijoueur** : Support quantique complet dans les parties multijoueur" if MULTIPLAYER_AVAILABLE else ""}
    
    ## 🔐 Authentification
    
    Utilisez le header `Authorization: Bearer <token>` pour les endpoints protégés.
    
    {f'''## 🎯 Multiplayer
    
    - **WebSockets** : Connexion temps réel via `/api/v1/multiplayer/ws/{{room_code}}`
    - **Rooms** : Parties privées et publiques avec codes d'accès
    - **Objets** : Système d'objets bonus/malus pour parties avancées
    - **Quantique** : Indices quantiques disponibles en multijoueur''' if MULTIPLAYER_AVAILABLE else ""}
    """,
    version="2.0.0-quantum" if MULTIPLAYER_AVAILABLE else "1.0.0-quantum",
    openapi_tags=[
        {
            "name": "auth",
            "description": "🔐 Authentification et gestion des comptes"
        },
        {
            "name": "users",
            "description": "👥 Gestion des utilisateurs et profils"
        },
        {
            "name": "games",
            "description": "🎮 Création et gestion des parties"
        },
    ] + ([{
            "name": "multiplayer",
            "description": "🎯 Parties multijoueur temps réel"
        }] if MULTIPLAYER_AVAILABLE else []) + [
        {
            "name": "quantum",
            "description": "⚛️ Fonctionnalités quantiques et hints"
        },
        {
            "name": "monitoring",
            "description": "📊 Santé et métriques de l'application"
        }
    ],
    lifespan=lifespan,
    # Configuration pour la documentation
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None
)

# === MIDDLEWARE ===

# Gestion des erreurs globales
@app.exception_handler(BaseQuantumMastermindError)
async def quantum_mastermind_exception_handler(
    request: Request,
    exc: BaseQuantumMastermindError
) -> JSONResponse:
    """Gestionnaire global des exceptions métier"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "timestamp": time.time()
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Gestionnaire global pour toutes les autres exceptions"""
    logger.error(f"Erreur non gérée: {exc}", exc_info=True)

    # En production, on ne révèle pas les détails techniques
    if settings.ENVIRONMENT == "production":
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": "Une erreur interne s'est produite",
                "details": {},
                "timestamp": time.time()
            }
        )
    else:
        return JSONResponse(
            status_code=get_http_status_code(exc),
            content={
                "error": True,
                "error_code": "UNEXPECTED_ERROR",
                "message": str(exc),
                "details": get_exception_details(exc),
                "timestamp": time.time()
            }
        )

# Middleware de sécurité des hôtes
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.TRUSTED_HOSTS
)

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Pagination-Page", "X-Pagination-Per-Page"]
)

# Middleware de compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# === MIDDLEWARE PERSONNALISÉS ===

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Ajoute des en-têtes de sécurité à toutes les réponses"""
    response = await call_next(request)

    # En-têtes de sécurité
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # CSP pour la sécurité quantique (éviter les injections de circuits malveillants)
    if settings.ENVIRONMENT == "production":
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self' wss: ws:; "
            "font-src 'self'"
        )

    return response

@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    """Ajoute le timing des requêtes"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    response.headers["X-Process-Time"] = str(process_time)

    # Log des requêtes lentes (> 2 secondes)
    if process_time > 2.0:
        logger.warning(
            f"Requête lente détectée: {request.method} {request.url.path} "
            f"({process_time:.2f}s)"
        )

    return response

@app.middleware("http")
async def log_quantum_operations(request: Request, call_next):
    """Log spécial pour les opérations quantiques"""
    response = await call_next(request)

    # Log des opérations quantiques pour audit
    if "/quantum" in str(request.url.path) or "quantum" in request.url.query:
        logger.info(
            f"Opération quantique: {request.method} {request.url.path} "
            f"- Status: {response.status_code}"
        )

    return response

# NOUVEAU: Middleware pour log des opérations multijoueur
@app.middleware("http")
async def log_multiplayer_operations(request: Request, call_next):
    """Log spécial pour les opérations multijoueur"""
    response = await call_next(request)

    # Log des opérations multijoueur pour audit
    if "/multiplayer" in str(request.url.path):
        logger.info(
            f"Opération multijoueur: {request.method} {request.url.path} "
            f"- Status: {response.status_code}"
        )

    return response

# === ROUTES DE SANTÉ ===

@app.get("/health", tags=["monitoring"])
async def health_check():
    """
    Vérification de la santé de l'application

    Retourne l'état de tous les services
    """
    services = {
        "api": "healthy",
        "quantum_backend": "healthy",  # Sera déterminé dynamiquement
        "database": "healthy"  # Sera déterminé dynamiquement
    }

    # NOUVEAU: Ajout des services multijoueur
    if MULTIPLAYER_AVAILABLE:
        services["multiplayer"] = "healthy"
    if WEBSOCKET_MULTIPLAYER_AVAILABLE:
        services["websockets"] = "healthy"

    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "2.0.0-quantum" if MULTIPLAYER_AVAILABLE else "1.0.0-quantum",
        "environment": settings.ENVIRONMENT,
        "services": services
    }

@app.get("/metrics", tags=["monitoring"])
async def get_metrics():
    """
    Métriques de performance de l'application

    Inclut les métriques quantiques spécifiques et multijoueur
    """
    try:
        metrics = {
            "timestamp": time.time(),
            "uptime": time.time(),  # À améliorer avec un timestamp de démarrage
            "memory_usage": "N/A",  # À implémenter
            "active_connections": "N/A",  # À implémenter
            "requests_per_minute": "N/A"  # À implémenter
        }

        # Métriques quantiques
        try:
            quantum_metrics = quantum_service.get_metrics()
            metrics["quantum_metrics"] = quantum_metrics
        except Exception as e:
            metrics["quantum_metrics"] = {
                "error": str(e),
                "status": "unavailable"
            }

        # NOUVEAU: Métriques WebSocket multijoueur (si disponible)
        if WEBSOCKET_MULTIPLAYER_AVAILABLE:
            try:
                from app.websocket.multiplayer import multiplayer_ws_manager
                metrics["websockets"] = {
                    "status": "operational",
                    "total_rooms": len(multiplayer_ws_manager.multiplayer_rooms),
                    "total_connections": sum(
                        len(conns) for conns in multiplayer_ws_manager.room_connections.values()
                    ),
                    "active_effects": sum(
                        len(effects) for effects in multiplayer_ws_manager.active_effects.values()
                    )
                }
            except Exception as e:
                metrics["websockets"] = {
                    "status": "error",
                    "error": str(e)
                }

        return metrics

    except Exception as e:
        return {
            "error": "Erreur lors de la récupération des métriques",
            "details": str(e)
        }


# === ROUTES API ===

# Routes d'authentification
app.include_router(auth.router, prefix="/api/v1")

# Routes des utilisateurs
app.include_router(users.router, prefix="/api/v1")

# Routes des jeux (avec support quantique intégré)
app.include_router(games.router, prefix="/api/v1")

# NOUVEAU: Routes multijoueur (si disponible)
if MULTIPLAYER_AVAILABLE:
    app.include_router(multiplayer.router, prefix="/api/v1")
    logger.info("✅ Routes multijoueur activées")
else:
    logger.warning("⚠️  Routes multijoueur désactivées")


# === ÉVÉNEMENTS DE L'APPLICATION (DÉPRÉCIÉS - Migration vers lifespan) ===

@app.on_event("startup")
async def startup_event():
    """
    Événements de démarrage supplémentaires
    DÉPRÉCIÉ: Migration vers lifespan recommandée
    """
    logger.info("📡 Configuration des connexions...")

    # Log des capacités quantiques au démarrage
    try:
        quantum_capabilities = quantum_service.get_quantum_info()
        logger.info("⚛️  Capacités quantiques:")
        logger.info(f"   - Backend: {quantum_capabilities.get('backend', 'N/A')}")
        logger.info(f"   - Max qubits: {quantum_capabilities.get('max_qubits', 'N/A')}")
        logger.info(f"   - Features: {len(quantum_capabilities.get('supported_hints', []))} hint algorithms")
        logger.info(f"   - Status: {quantum_capabilities.get('status', 'Unknown')}")
    except Exception as e:
        logger.warning(f"⚠️  Impossible de charger les capacités quantiques: {e}")

    # NOUVEAU: Log des fonctionnalités multijoueur
    if MULTIPLAYER_AVAILABLE:
        logger.info("🎮 Fonctionnalités multijoueur activées")
        if WEBSOCKET_MULTIPLAYER_AVAILABLE:
            logger.info("🔌 WebSockets temps réel disponibles")
    else:
        logger.info("🎮 Mode solo uniquement")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Événements d'arrêt
    DÉPRÉCIÉ: Migration vers lifespan recommandée
    """
    logger.info("🔌 Fermeture des connexions...")
    logger.info("⚛️  Arrêt du backend quantique...")


# === CONFIGURATION FINALE ===

if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Démarrage direct de l'application")
    if MULTIPLAYER_AVAILABLE:
        logger.info("🎮 Mode multijoueur activé")

    # NOUVEAU: Configuration uvicorn adaptée selon les fonctionnalités
    uvicorn_config = {
        "app": "app.main:app",
        "host": settings.API_HOST,
        "port": settings.API_PORT,
        "reload": settings.DEBUG,
        "log_level": settings.LOG_LEVEL.lower(),
    }

    # Configuration WebSocket uniquement si disponible
    if WEBSOCKET_MULTIPLAYER_AVAILABLE:
        uvicorn_config.update({
            "ws_max_size": 16777216,  # 16MB pour les gros messages
            "ws_ping_interval": 20,   # Ping interval WebSocket
            "ws_ping_timeout": 20     # Ping timeout WebSocket
        })
        logger.info("🔌 Configuration WebSocket activée")

    uvicorn.run(**uvicorn_config)