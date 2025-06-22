"""
Point d'entrée principal de l'application Quantum Mastermind
COMPLET: Intégration de toutes les fonctionnalités multijoueur et quantiques
Version: 2.0.0 - Multijoueur Quantique
"""
import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

# Routes API principales
from app.api import auth, users, games

# NOUVEAU: Import conditionnel du multiplayer avec gestion d'erreurs
try:
    from app.api import multiplayer
    MULTIPLAYER_AVAILABLE = True
    print("✅ Module multiplayer chargé avec succès")
except ImportError as e:
    MULTIPLAYER_AVAILABLE = False
    print(f"⚠️  Module multiplayer non trouvé: {e}")

from app.core.config import settings
from app.core.database import init_db, close_db, get_db

# Services principaux
try:
    from app.services.quantum import quantum_service
    QUANTUM_AVAILABLE = True
    print("✅ Service quantique disponible")
except ImportError as e:
    QUANTUM_AVAILABLE = False
    print(f"⚠️  Service quantique non disponible: {e}")

# NOUVEAU: Import conditionnel des WebSockets multiplayer
try:
    from app.websocket.multiplayer import (
        initialize_multiplayer_websocket,
        cleanup_task,
        multiplayer_ws_manager
    )
    WEBSOCKET_MULTIPLAYER_AVAILABLE = True
    print("✅ WebSocket multiplayer disponible")
except ImportError as e:
    WEBSOCKET_MULTIPLAYER_AVAILABLE = False
    print(f"⚠️  WebSocket multiplayer non disponible: {e}")

# Utilitaires et exceptions
from app.utils.exceptions import (
    BaseQuantumMastermindError,
    get_http_status_code,
    get_exception_details,
    create_error_response
)

import logging

# Configuration du logging améliorée
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/quantum_mastermind.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


# =====================================================
# CYCLE DE VIE DE L'APPLICATION
# =====================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire de cycle de vie de l'application"""
    logger.info("🚀 Démarrage de Quantum Mastermind...")

    try:
        # Initialisation de la base de données
        logger.info("🗄️  Initialisation de la base de données...")
        await init_db()
        logger.info("✅ Base de données initialisée")

        # Initialisation du service quantique
        if QUANTUM_AVAILABLE:
            try:
                logger.info("⚛️  Initialisation du service quantique...")
                await quantum_service.initialize()
                logger.info("✅ Service quantique initialisé")
            except Exception as e:
                logger.warning(f"⚠️  Erreur initialisation quantique: {e}")

        # NOUVEAU: Initialisation des WebSockets multijoueur
        if WEBSOCKET_MULTIPLAYER_AVAILABLE:
            try:
                logger.info("🌐 Initialisation des WebSockets multijoueur...")
                await initialize_multiplayer_websocket()
                logger.info("✅ WebSockets multijoueur initialisés")
            except Exception as e:
                logger.warning(f"⚠️  Erreur initialisation WebSocket: {e}")

        # Statistiques de démarrage
        startup_stats = {
            "timestamp": datetime.now().isoformat(),
            "environment": settings.ENVIRONMENT,
            "multiplayer": MULTIPLAYER_AVAILABLE,
            "quantum": QUANTUM_AVAILABLE,
            "websockets": WEBSOCKET_MULTIPLAYER_AVAILABLE,
            "version": "2.0.0"
        }
        logger.info(f"📊 Statistiques de démarrage: {startup_stats}")

        yield  # L'application fonctionne ici

    except Exception as e:
        logger.error(f"❌ Erreur critique au démarrage: {e}")
        raise
    finally:
        # Nettoyage à l'arrêt
        logger.info("🛑 Arrêt de Quantum Mastermind...")

        try:
            # Nettoyage WebSocket
            if WEBSOCKET_MULTIPLAYER_AVAILABLE:
                logger.info("🌐 Nettoyage des WebSockets...")
                await cleanup_task()

            # Nettoyage quantique
            if QUANTUM_AVAILABLE:
                logger.info("⚛️  Nettoyage du service quantique...")
                await quantum_service.cleanup()

            # Fermeture base de données
            logger.info("🗄️  Fermeture de la base de données...")
            await close_db()

            logger.info("✅ Arrêt propre terminé")

        except Exception as e:
            logger.error(f"❌ Erreur lors du nettoyage: {e}")


# =====================================================
# CRÉATION DE L'APPLICATION
# =====================================================

app = FastAPI(
    title="🎯⚛️ Quantum Mastermind API",
    description="""
    API REST pour Quantum Mastermind - Jeu de mastermind avec intégration quantique et multijoueur
    
    ## 🌟 Fonctionnalités
    
    ### 🎮 Modes de Jeu
    - **Solo Classique** : Mastermind traditionnel avec hints quantiques
    - **Solo Quantique** : Utilisation de superposition et intrication  
    - **Multijoueur Synchrone** : Tous les joueurs résolvent la même combinaison
    - **Battle Royale** : Chacun sa combinaison, élimination progressive
    - **Mode Rapidité** : Classement basé sur le temps
    
    ### ⚛️ Fonctionnalités Quantiques
    - **Indices Grover** : Recherche quantique optimisée
    - **Superposition** : Exploration de multiples états
    - **Intrication** : Corrélations quantiques entre tentatives
    - **Interférence** : Optimisation des patterns
    
    ### 🏆 Système Multijoueur
    - **Parties en temps réel** avec WebSockets
    - **Système d'objets** et d'effets avancés
    - **Classements** et statistiques détaillées
    - **Chat intégré** et communication
    """,
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None
)

# =====================================================
# MIDDLEWARE CONFIGURATION
# =====================================================

# Compression GZIP
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS - Configuration sécurisée
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time", "X-Request-ID"]
)

# Hosts de confiance
if settings.TRUSTED_HOSTS:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.TRUSTED_HOSTS
    )


# =====================================================
# MIDDLEWARE PERSONNALISÉS
# =====================================================

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Ajoute le temps de traitement dans les headers"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    response.headers["X-Process-Time"] = str(round(process_time, 4))

    # Log des requêtes lentes (> 2 secondes)
    if process_time > 2.0:
        logger.warning(
            f"🐌 Requête lente détectée: {request.method} {request.url.path} "
            f"({process_time:.2f}s)"
        )

    return response


@app.middleware("http")
async def add_request_id_header(request: Request, call_next):
    """Ajoute un ID unique pour chaque requête"""
    import uuid
    request_id = str(uuid.uuid4())[:8]

    # Ajouter l'ID à la requête pour le logging
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response


@app.middleware("http")
async def log_quantum_operations(request: Request, call_next):
    """Log spécial pour les opérations quantiques"""
    response = await call_next(request)

    # Log des opérations quantiques pour audit
    if "/quantum" in str(request.url.path) or "quantum" in request.url.query:
        request_id = getattr(request.state, 'request_id', 'unknown')
        logger.info(
            f"⚛️  Opération quantique [{request_id}]: {request.method} {request.url.path} "
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
        request_id = getattr(request.state, 'request_id', 'unknown')
        logger.info(
            f"🎯 Opération multijoueur [{request_id}]: {request.method} {request.url.path} "
            f"- Status: {response.status_code}"
        )

    return response


# NOUVEAU: Middleware pour gestion globale des erreurs
@app.middleware("http")
async def global_exception_handler(request: Request, call_next):
    """Gestionnaire global d'exceptions"""
    try:
        response = await call_next(request)
        return response
    except BaseQuantumMastermindError as e:
        # Erreurs métier connues
        request_id = getattr(request.state, 'request_id', 'unknown')
        logger.warning(f"⚠️  Erreur métier [{request_id}]: {e.message}")

        error_response = create_error_response(e)
        error_response["timestamp"] = datetime.now().isoformat()
        error_response["request_id"] = request_id

        return JSONResponse(
            status_code=get_http_status_code(e),
            content=error_response
        )
    except Exception as e:
        # Erreurs système inattendues
        request_id = getattr(request.state, 'request_id', 'unknown')
        logger.error(f"❌ Erreur système [{request_id}]: {str(e)}")

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "type": "InternalServerError",
                    "message": "Erreur interne du serveur",
                    "code": "INTERNAL_ERROR"
                },
                "data": None,
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id
            }
        )


# =====================================================
# ROUTES DE SANTÉ ET MONITORING
# =====================================================

@app.get("/", tags=["System"])
async def api_root():
    """Page d'accueil de l'API"""
    return {
        "name": "🎯⚛️ Quantum Mastermind API",
        "version": "2.0.0",
        "status": "operational",
        "features": {
            "multiplayer": MULTIPLAYER_AVAILABLE,
            "quantum": QUANTUM_AVAILABLE,
            "websockets": WEBSOCKET_MULTIPLAYER_AVAILABLE
        },
        "documentation": "/docs" if settings.ENVIRONMENT != "production" else "Contact admin",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health", tags=["Monitoring"])
async def health_check():
    """
    Vérification de la santé de l'application
    Retourne l'état de tous les services
    """
    health_status = "healthy"
    services = {
        "api": "healthy",
        "database": "healthy"  # Sera vérifié dynamiquement
    }

    # Test de connexion à la base de données
    try:
        async for db in get_db():
            await db.execute("SELECT 1")
            break
    except Exception as e:
        services["database"] = f"unhealthy: {str(e)}"
        health_status = "degraded"

    # Service quantique
    if QUANTUM_AVAILABLE:
        try:
            services["quantum"] = "healthy"
            # Test optionnel du service quantique
        except Exception as e:
            services["quantum"] = f"unhealthy: {str(e)}"
            health_status = "degraded"
    else:
        services["quantum"] = "unavailable"

    # Services multijoueur
    if MULTIPLAYER_AVAILABLE:
        services["multiplayer"] = "healthy"
    else:
        services["multiplayer"] = "unavailable"

    if WEBSOCKET_MULTIPLAYER_AVAILABLE:
        try:
            # Vérifier l'état du gestionnaire WebSocket
            active_rooms = len(multiplayer_ws_manager.multiplayer_rooms)
            active_connections = sum(
                len(conns) for conns in multiplayer_ws_manager.room_connections.values()
            )
            services["websockets"] = {
                "status": "healthy",
                "active_rooms": active_rooms,
                "active_connections": active_connections
            }
        except Exception as e:
            services["websockets"] = f"unhealthy: {str(e)}"
            health_status = "degraded"
    else:
        services["websockets"] = "unavailable"

    return {
        "status": health_status,
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "environment": settings.ENVIRONMENT,
        "services": services,
        "uptime": time.time()  # À améliorer avec un timestamp de démarrage réel
    }


@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """
    Métriques de performance de l'application
    Inclut les métriques quantiques et multijoueur spécifiques
    """
    try:
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "uptime": time.time(),  # À améliorer avec un timestamp de démarrage
            "version": "2.0.0",
            "environment": settings.ENVIRONMENT
        }

        # Métriques quantiques
        if QUANTUM_AVAILABLE:
            try:
                quantum_metrics = await quantum_service.get_metrics()
                metrics["quantum"] = quantum_metrics
            except Exception as e:
                metrics["quantum"] = {
                    "error": str(e),
                    "status": "error"
                }
        else:
            metrics["quantum"] = {"status": "unavailable"}

        # NOUVEAU: Métriques WebSocket multijoueur
        if WEBSOCKET_MULTIPLAYER_AVAILABLE:
            try:
                ws_metrics = {
                    "status": "operational",
                    "total_rooms": len(multiplayer_ws_manager.multiplayer_rooms),
                    "total_connections": sum(
                        len(conns) for conns in multiplayer_ws_manager.room_connections.values()
                    ),
                    "active_effects": sum(
                        len(effects) for effects in multiplayer_ws_manager.active_effects.values()
                    ),
                    "background_tasks": len(multiplayer_ws_manager.background_tasks)
                }

                # Détails par room
                room_details = {}
                for room_code in multiplayer_ws_manager.multiplayer_rooms:
                    room_details[room_code] = multiplayer_ws_manager.get_room_stats(room_code)

                ws_metrics["rooms"] = room_details
                metrics["websockets"] = ws_metrics

            except Exception as e:
                metrics["websockets"] = {
                    "status": "error",
                    "error": str(e)
                }
        else:
            metrics["websockets"] = {"status": "unavailable"}

        # Métriques système de base
        try:
            import psutil
            metrics["system"] = {
                "memory_usage_percent": psutil.virtual_memory().percent,
                "cpu_usage_percent": psutil.cpu_percent(interval=1),
                "disk_usage_percent": psutil.disk_usage('/').percent
            }
        except ImportError:
            metrics["system"] = {"status": "psutil not available"}

        return metrics

    except Exception as e:
        logger.error(f"❌ Erreur récupération métriques: {e}")
        return {
            "error": "Erreur lors de la récupération des métriques",
            "details": str(e),
            "timestamp": datetime.now().isoformat()
        }


# =====================================================
# INCLUSION DES ROUTES API
# =====================================================

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


# =====================================================
# ROUTES DE DÉVELOPPEMENT (à supprimer en production)
# =====================================================

if settings.ENVIRONMENT in ["development", "testing"]:

    @app.get("/debug/info", tags=["Debug"])
    async def debug_info():
        """Informations de debug (développement seulement)"""
        return {
            "environment": settings.ENVIRONMENT,
            "debug_mode": True,
            "features": {
                "multiplayer": MULTIPLAYER_AVAILABLE,
                "quantum": QUANTUM_AVAILABLE,
                "websockets": WEBSOCKET_MULTIPLAYER_AVAILABLE
            },
            "database_url": settings.DATABASE_URL[:20] + "..." if settings.DATABASE_URL else None,
            "cors_origins": settings.CORS_ORIGINS,
            "log_level": settings.LOG_LEVEL
        }

    if WEBSOCKET_MULTIPLAYER_AVAILABLE:
        @app.get("/debug/websockets", tags=["Debug"])
        async def debug_websockets():
            """Debug des WebSockets (développement seulement)"""
            return {
                "multiplayer_rooms": list(multiplayer_ws_manager.multiplayer_rooms.keys()),
                "room_connections": {
                    room: len(conns) for room, conns in multiplayer_ws_manager.room_connections.items()
                },
                "active_effects": {
                    room: len(effects) for room, effects in multiplayer_ws_manager.active_effects.items()
                },
                "background_tasks_count": len(multiplayer_ws_manager.background_tasks)
            }


# =====================================================
# GESTION DES ERREURS GLOBALES (fallback)
# =====================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Gestionnaire pour les exceptions HTTP"""
    request_id = getattr(request.state, 'request_id', 'unknown')

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "type": "HTTPException",
                "message": exc.detail,
                "code": f"HTTP_{exc.status_code}"
            },
            "data": None,
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id
        }
    )


# =====================================================
# MESSAGE DE DÉMARRAGE
# =====================================================

if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Démarrage de Quantum Mastermind en mode direct...")
    logger.info(f"🌍 Environnement: {settings.ENVIRONMENT}")
    logger.info(f"🎯 Multijoueur: {'✅' if MULTIPLAYER_AVAILABLE else '❌'}")
    logger.info(f"⚛️  Quantique: {'✅' if QUANTUM_AVAILABLE else '❌'}")
    logger.info(f"🌐 WebSocket: {'✅' if WEBSOCKET_MULTIPLAYER_AVAILABLE else '❌'}")

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower()
    )