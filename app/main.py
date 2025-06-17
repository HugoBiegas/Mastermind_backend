"""
Point d'entrée principal de l'application Quantum Mastermind
MODIFIÉ: Ajout des routes quantiques et configuration étendue
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
from app.core.database import get_db
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
    """
    # Démarrage
    logger.info("🚀 Démarrage de Quantum Mastermind API")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

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

    yield

    # Arrêt
    logger.info("🛑 Arrêt de Quantum Mastermind API")


# === CONFIGURATION DE L'APPLICATION ===

app = FastAPI(
    title="🎯⚛️ Quantum Mastermind API",
    description="""
    API REST pour le jeu Quantum Mastermind intégrant l'informatique quantique.
    
    ## 🌟 Fonctionnalités
    
    ### 🎮 Jeu Classique
    - Création et gestion de parties Mastermind
    - Modes solo et multijoueur
    - Système de scoring et classements
    
    ### ⚛️ Informatique Quantique
    - **Génération quantique de solutions** : Utilise la superposition quantique pour créer des combinaisons vraiment aléatoires
    - **Calcul quantique d'indices** : Algorithmes quantiques pour calculer les "bien placé" / "mal placé"
    - **Hints quantiques** : Algorithmes de Grover, superposition et intrication pour des indices avancés
    - **Backend Qiskit** : Intégration complète avec le framework IBM Quantum
    
    ### 🔒 Sécurité et Performance
    - Authentification JWT sécurisée
    - Validation des données robuste
    - WebSockets temps réel
    - Rate limiting et monitoring
    
    ## 🚀 Utilisation
    
    1. **Authentification** : Créez un compte et obtenez un token JWT
    2. **Créer une partie** : Choisissez entre mode classique ou quantique
    3. **Jouer** : Soumettez vos tentatives et recevez des indices
    4. **Explorer** : Testez les algorithmes quantiques dans la section dédiée
    
    ## 🔬 Algorithmes Quantiques Implémentés
    
    - **Génération de nombres aléatoires** : Portes Hadamard + mesure quantique
    - **Distance de Hamming quantique** : Comparaison parallèle par intrication
    - **Algorithme de Grover** : Recherche quantique pour hints optimisés
    - **Analyse de superposition** : Exploration d'états multiples simultanés
    
    ---
    
    Développé avec ❤️ et ⚛️ par l'équipe Quantum Mastermind
    """,
    version=settings.VERSION,
    openapi_tags=[
        {
            "name": "Authentification",
            "description": "Gestion des utilisateurs et authentification JWT"
        },
        {
            "name": "Utilisateurs",
            "description": "Profils, préférences et statistiques des joueurs"
        },
        {
            "name": "Jeux",
            "description": "Création, gestion et gameplay des parties Mastermind"
        },
        {
            "name": "Quantum Computing",
            "description": "🆕 Fonctionnalités quantiques avancées et algorithmes spécialisés"
        }
    ],
    contact={
        "name": "Équipe Quantum Mastermind",
        "email": "dev@quantum-mastermind.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan
)


# === MIDDLEWARE ===

# CORS - Configuration sécurisée
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Hosts de confiance
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.TRUSTED_HOSTS
    )

# Compression
app.add_middleware(GZipMiddleware, minimum_size=1000)


# === MIDDLEWARE PERSONNALISÉ ===

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Ajoute les en-têtes de sécurité"""
    response = await call_next(request)

    # Headers de sécurité
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Header personnalisé pour identifier l'API
    response.headers["X-Powered-By"] = f"Quantum-Mastermind-{settings.VERSION}"

    # NOUVEAU: Header pour indiquer les capacités quantiques
    response.headers["X-Quantum-Enabled"] = "true"
    response.headers["X-Quantum-Backend"] = "qiskit-aer"

    return response


@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    """Ajoute le timing des requêtes"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# NOUVEAU: Middleware pour logging des opérations quantiques
@app.middleware("http")
async def log_quantum_operations(request: Request, call_next):
    """Log spécial pour les opérations quantiques"""
    response = await call_next(request)

    # Logger les requêtes vers les endpoints quantiques
    if "/quantum" in str(request.url) or "/games" in str(request.url):
        logger.info(f"Quantum operation: {request.method} {request.url.path} - Status: {response.status_code}")

    return response


# === GESTION GLOBALE DES EXCEPTIONS ===

@app.exception_handler(BaseQuantumMastermindError)
async def quantum_mastermind_exception_handler(request: Request, exc: BaseQuantumMastermindError):
    """Gestionnaire pour les exceptions personnalisées"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "timestamp": time.time(),
            "path": str(request.url.path),
            "quantum_context": getattr(exc, 'quantum_context', None)  # NOUVEAU
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Gestionnaire pour les exceptions HTTP"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": f"HTTP_{exc.status_code}",
            "message": exc.detail,
            "timestamp": time.time(),
            "path": str(request.url.path)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Gestionnaire pour les exceptions générales"""
    status_code = get_http_status_code(exc)
    details = get_exception_details(exc)

    # En production, masquer les détails d'erreur sensibles
    if settings.ENVIRONMENT == "production" and status_code == 500:
        details['message'] = "Erreur interne du serveur"
        details['details'] = {}

    return JSONResponse(
        status_code=status_code,
        content={
            **details,
            "timestamp": time.time(),
            "path": str(request.url.path)
        }
    )


# === ROUTES DE BASE ===

@app.get(
    "/",
    tags=["Base"],
    summary="Page d'accueil",
    description="Point d'entrée de l'API Quantum Mastermind"
)
async def root():
    """Page d'accueil de l'API avec informations quantiques"""
    return {
        "message": "🎯⚛️ Quantum Mastermind API",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "documentation": "/docs",
        "features": [
            "Jeu de Mastermind avec informatique quantique",
            "Modes solo et multijoueur",
            "Système de scoring avancé",
            "WebSocket temps réel",
            "Authentification JWT sécurisée"
        ],
        "quantum_features": [
            "🎲 Génération quantique de solutions (superposition Hadamard)",
            "🔍 Calcul quantique d'indices (distance de Hamming quantique)",
            "🔮 Algorithme de Grover pour hints optimisés",
            "🌐 Analyse par intrication quantique",
            "📊 Mesures probabilistes avec vrais nombres aléatoires"
        ],
        "quantum_status": "operational",
        "algorithms_implemented": [
            "Quantum Random Number Generation",
            "Quantum Hamming Distance",
            "Grover's Search Algorithm",
            "Quantum Superposition Analysis",
            "Quantum Entanglement Detection"
        ],
        "api_endpoints": {
            "games": "/games - Gestion des parties avec support quantique",
            "quantum": "/quantum - Algorithmes quantiques spécialisés",
            "auth": "/auth - Authentification et gestion des comptes",
            "users": "/users - Profils et statistiques des joueurs"
        }
    }


@app.get(
    "/health",
    tags=["Base"],
    summary="Santé de l'API",
    description="Vérifie l'état de santé de l'API et de ses composants quantiques"
)
async def health_check():
    """Check de santé de l'API avec statut quantique"""
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "components": {
            "api": "healthy"
        }
    }

    # Test de la base de données
    try:
        async for db in get_db():
            # Simple test de connexion
            await db.execute("SELECT 1")
            health_status["components"]["database"] = "healthy"
            break
    except Exception as e:
        health_status["components"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    # NOUVEAU: Test du backend quantique
    try:
        quantum_status = await quantum_service.test_quantum_backend()
        if quantum_status["status"] == "healthy":
            health_status["components"]["quantum_backend"] = "healthy"
            health_status["quantum_info"] = {
                "backend": quantum_status.get("backend", "Unknown"),
                "qiskit_version": quantum_status.get("qiskit_version", "Unknown"),
                "algorithms": quantum_status.get("available_algorithms", [])
            }
        else:
            health_status["components"]["quantum_backend"] = "degraded"
            health_status["quantum_info"] = {
                "error": quantum_status.get("error", "Unknown"),
                "fallback": "classical_algorithms_available"
            }
    except Exception as e:
        health_status["components"]["quantum_backend"] = f"error: {str(e)}"
        health_status["quantum_info"] = {"fallback": "classical_algorithms_only"}

    # Déterminer le statut global
    if any("unhealthy" in status or "error" in status for status in health_status["components"].values()):
        health_status["status"] = "unhealthy"
    elif any("degraded" in status for status in health_status["components"].values()):
        health_status["status"] = "degraded"

    return health_status


@app.get(
    "/metrics",
    tags=["Base"],
    summary="Métriques système",
    description="Métriques de performance et d'utilisation"
)
async def get_metrics():
    """Métriques de l'API avec statistiques quantiques"""
    try:
        # Métriques basiques
        metrics = {
            "uptime": time.time(),
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT
        }

        # NOUVEAU: Métriques quantiques
        try:
            quantum_info = quantum_service.get_quantum_info()
            metrics["quantum_metrics"] = {
                "backend_available": quantum_info["status"] == "available",
                "max_qubits": quantum_info["max_qubits"],
                "default_shots": quantum_info["default_shots"],
                "supported_algorithms": len(quantum_info["supported_hints"]),
                "quantum_features_active": len(quantum_info.get("new_quantum_features", []))
            }
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


# === ÉVÉNEMENTS DE L'APPLICATION ===

@app.on_event("startup")
async def startup_event():
    """Événements de démarrage supplémentaires"""
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
    """Événements d'arrêt"""
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