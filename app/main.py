"""
Point d'entrée principal de l'application Quantum Mastermind
MODIFIÉ: Ajout des routes quantiques et configuration étendue
CORRECTION: Ajout de l'initialisation de la base de données dans le cycle de vie
"""
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import auth, users, games
from app.core.config import settings
from app.core.database import init_db, close_db, get_db
from app.services.quantum import quantum_service
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
    Gestionnaire de cycle de vie de l'application
    NOUVEAU: Test du backend quantique au démarrage
    CORRECTION: Ajout de l'initialisation de la base de données
    """
    # Démarrage
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

    # NOUVEAU: Test du système quantique au démarrage
    try:
        quantum_status = await quantum_service.test_quantum_backend()
        if quantum_status["status"] == "healthy":
            logger.info("✅ Backend quantique opérationnel")
            logger.info(f"   - Backend: {quantum_status.get('backend', 'Unknown')}")
            logger.info(f"   - Version Qiskit: {quantum_status.get('qiskit_version', 'Unknown')}")
            logger.info(f"   - Algorithmes disponibles: {', '.join(quantum_status.get('available_algorithms', []))}")
        else:
            logger.warning("⚠️  Backend quantique non disponible")
            logger.warning(f"   - Erreur: {quantum_status.get('error', 'Unknown')}")
            logger.warning("   - Les fonctionnalités quantiques utiliseront des fallbacks classiques")
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'initialisation quantique: {e}")

    logger.info("🎯 Application prête à traiter les requêtes")

    yield

    # Arrêt
    logger.info("🛑 Arrêt de Quantum Mastermind API")
    logger.info("🔌 Fermeture des connexions...")

    # CORRECTION: Fermeture propre de la base de données
    try:
        await close_db()
        logger.info("✅ Base de données fermée proprement")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la fermeture de la base de données: {e}")

    logger.info("⚛️  Arrêt du backend quantique...")
    logger.info("👋 Arrêt terminé")


# === CONFIGURATION DE L'APPLICATION ===

app = FastAPI(
    title="🎯⚛️ Quantum Mastermind API",
    description="""
    API REST pour le jeu Quantum Mastermind intégrant l'informatique quantique.
    
    ## 🎮 Fonctionnalités
    
    - **Modes de jeu** : Solo classique, solo quantique, multijoueur
    - **Hints quantiques** : Utilisation d'algorithmes de Grover, superposition, intrication
    - **Temps réel** : WebSockets pour le multijoueur
    - **Sécurité** : Authentification JWT, validation des données
    - **Performance** : Cache Redis, pagination, rate limiting
    
    ## ⚛️ Informatique Quantique
    
    - **Backend** : Qiskit avec simulateurs et accès aux ordinateurs quantiques IBM
    - **Algorithmes** : Grover, superposition, détection d'intrication
    - **Optimisation** : Fallbacks classiques en cas d'indisponibilité
    
    ## 🔐 Authentification
    
    Utilisez le header `Authorization: Bearer <token>` pour les endpoints protégés.
    """,
    version="1.0.0-quantum",
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

# === ROUTES DE SANTÉ ===

@app.get("/health", tags=["monitoring"])
async def health_check():
    """
    Vérification de la santé de l'application

    Retourne l'état de tous les services
    """
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0-quantum",
        "environment": settings.ENVIRONMENT,
        "services": {
            "api": "healthy",
            "quantum_backend": "healthy",  # Sera déterminé dynamiquement
            "database": "healthy"  # Sera déterminé dynamiquement
        }
    }

@app.get("/metrics", tags=["monitoring"])
async def get_metrics():
    """
    Métriques de performance de l'application

    Inclut les métriques quantiques spécifiques
    """
    try:
        metrics = {
            "timestamp": time.time(),
            "uptime": time.time(),  # À améliorer avec un timestamp de démarrage
            "memory_usage": "N/A",  # À implémenter
            "active_connections": "N/A",  # À implémenter
            "requests_per_minute": "N/A"  # À implémenter
        }

        # NOUVEAU: Métriques quantiques
        try:
            quantum_metrics = quantum_service.get_metrics()
            metrics["quantum_metrics"] = quantum_metrics
        except Exception as e:
            metrics["quantum_metrics"] = {
                "error": str(e),
                "status": "unavailable"
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


# === ÉVÉNEMENTS DE L'APPLICATION (DÉPRÉCIÉS - Migration vers lifespan) ===

@app.on_event("startup")
async def startup_event():
    """
    Événements de démarrage supplémentaires
    DÉPRÉCIÉ: Migration vers lifespan recommandée
    """
    logger.info("📡 Configuration des connexions...")

    # NOUVEAU: Log des capacités quantiques au démarrage
    try:
        quantum_capabilities = quantum_service.get_quantum_info()
        logger.info("⚛️  Capacités quantiques:")
        logger.info(f"   - Backend: {quantum_capabilities.get('backend', 'N/A')}")
        logger.info(f"   - Max qubits: {quantum_capabilities.get('max_qubits', 'N/A')}")
        logger.info(f"   - Features: {len(quantum_capabilities.get('supported_hints', []))} hint algorithms")
        logger.info(f"   - Status: {quantum_capabilities.get('status', 'Unknown')}")
    except Exception as e:
        logger.warning(f"⚠️  Impossible de charger les capacités quantiques: {e}")


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
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )