"""
Application principale Quantum Mastermind
Point d'entrée FastAPI avec configuration complète
"""
import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import init_db, close_db, get_db
from app.api import auth, users, games
from app.websocket.manager import websocket_manager
from app.websocket.handlers import message_handler
from app.utils.exceptions import (
    BaseQuantumMastermindError, get_http_status_code, get_exception_details
)

# === TÂCHE DE NETTOYAGE WEBSOCKET ===

async def websocket_cleanup_task():
    """Tâche périodique de nettoyage des connexions WebSocket inactives"""
    while True:
        try:
            await websocket_manager.cleanup_inactive_connections()
            await asyncio.sleep(60)  # Nettoyage toutes les minutes
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"❌ Erreur lors du nettoyage WebSocket: {e}")
            await asyncio.sleep(10)  # Attendre avant de réessayer


# === LIFESPAN DE L'APPLICATION ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire du cycle de vie de l'application"""
    # Démarrage
    print("🚀 Démarrage de Quantum Mastermind...")

    cleanup_task = None  # Initialiser la variable

    try:
        # Initialisation de la base de données
        await init_db()
        print("✅ Base de données initialisée")

        # Démarrage du nettoyage périodique des WebSockets
        cleanup_task = asyncio.create_task(websocket_cleanup_task())
        print("✅ Tâche de nettoyage WebSocket démarrée")

        print("🎯 Quantum Mastermind API prête!")
        print(f"📡 Serveur: {settings.API_HOST}:{settings.API_PORT}")
        print(f"🌐 Environnement: {settings.ENVIRONMENT}")

        yield

    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la base de données: {e}")
        print("🛑 Arrêt de Quantum Mastermind...")
        raise  # Re-lever l'exception pour arrêter l'app

    finally:
        # Arrêt
        print("🛑 Arrêt de Quantum Mastermind...")

        # Arrêt des tâches (seulement si elle existe)
        if cleanup_task is not None:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

        # Fermeture des connexions
        try:
            await close_db()
            print("✅ Base de données fermée")
        except:
            pass

        print("👋 Quantum Mastermind arrêté proprement")

# === CRÉATION DE L'APPLICATION ===

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
    🎯⚛️ **Quantum Mastermind API** - Un jeu de Mastermind révolutionnaire intégrant les principes de l'informatique quantique.
    
    ## 🌟 Fonctionnalités
    
    ### 🎮 Modes de Jeu
    - **Solo Classique** : Mastermind traditionnel avec hints quantiques
    - **Solo Quantique** : Utilisation de superposition et intrication
    - **Multijoueur Synchrone** : Tous les joueurs résolvent la même combinaison
    - **Battle Royale** : Chacun sa combinaison, élimination progressive
    - **Mode Rapidité** : Classement basé sur le temps
    - **Mode Précision** : Classement basé sur le nombre de coups
    
    ### 🏆 Système de Scoring
    - Score quantique basé sur l'utilisation des fonctionnalités avancées
    - Statistiques détaillées par joueur
    - Leaderboard global et classements par mode
    - Système de rang et progression
    
    ### ⚛️ Informatique Quantique
    - **Qiskit 2.0.2** : Framework IBM pour informatique quantique
    - **Hints Quantiques** : Algorithme de Grover pour optimiser les indices
    - **Superposition** : États quantiques multiples simultanés
    - **Intrication** : Corrélations quantiques entre les couleurs
    
    ## 🔧 Technologies
    - **FastAPI 0.115.12** : API REST haute performance
    - **SQLAlchemy 2.0.41** : ORM moderne avec support async
    - **PostgreSQL 16** : Base de données relationnelle
    - **Redis 7.4** : Cache et sessions
    - **WebSockets** : Communication temps réel
    - **JWT** : Authentification sécurisée
    """,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# === MIDDLEWARE ===

# Sécurité des hosts de confiance
if settings.TRUSTED_HOSTS:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.TRUSTED_HOSTS
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Request-ID"]
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

    return response


@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    """Ajoute le timing des requêtes"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
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
            "path": str(request.url.path)
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
    """Page d'accueil de l'API"""
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
            "Algorithme de Grover pour les hints",
            "Superposition quantique",
            "Intrication des couleurs",
            "Mesures probabilistes"
        ]
    }


@app.get(
    "/health",
    tags=["Base"],
    summary="Santé de l'API",
    description="Vérifie l'état de santé de l'API et de ses composants"
)
async def health_check():
    """Check de santé de l'API"""
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
            from sqlalchemy import text
            await db.execute(text("SELECT 1"))
            health_status["components"]["database"] = "healthy"
            break
    except Exception as e:
        health_status["components"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    # Test du backend quantique
    try:
        from app.services.quantum import quantum_service
        quantum_info = quantum_service.get_quantum_info()
        health_status["components"]["quantum"] = "healthy"
        health_status["quantum_backend"] = quantum_info.get("backend", "unknown")
    except Exception as e:
        health_status["components"]["quantum"] = f"unhealthy: {str(e)}"
        # On ne marque pas comme dégradé pour le quantique car c'est optionnel

    # WebSocket Manager
    try:
        from app.websocket.manager import websocket_manager
        health_status["components"]["websocket"] = "healthy"
        health_status["websocket_connections"] = websocket_manager.get_connection_count()
    except Exception as e:
        health_status["components"]["websocket"] = f"unhealthy: {str(e)}"

    # Toujours retourner 200 sauf si base de données down
    status_code = 200 if health_status["status"] != "critical" else 503

    return JSONResponse(
        status_code=status_code,
        content=health_status
    )
@app.get(
    "/metrics",
    tags=["Base"],
    summary="Métriques de l'API",
    description="Métriques de performance et d'utilisation"
)
async def metrics():
    """Métriques de l'API"""
    return {
        "connections": {
            "websocket_active": websocket_manager.get_connection_count(),
            "websocket_rooms": websocket_manager.get_room_count()
        },
        "performance": {
            "uptime": time.time(),  # À améliorer avec le vrai uptime
        },
        "version": settings.VERSION,
        "timestamp": time.time()
    }


# === ROUTES API ===

# Inclusion des routers
app.include_router(
    auth.router,
    prefix=settings.API_V1_STR,
    tags=["Authentification"]
)

app.include_router(
    users.router,
    prefix=settings.API_V1_STR,
    tags=["Utilisateurs"]
)

app.include_router(
    games.router,
    prefix=settings.API_V1_STR,
    tags=["Jeux"]
)


# === WEBSOCKET ===

@app.websocket("/ws/{connection_type}")
async def websocket_endpoint(websocket: WebSocket, connection_type: str):
    """
    Point d'entrée WebSocket principal

    Types de connexion supportés:
    - game: Connexion de jeu temps réel
    - chat: Chat en temps réel (futur)
    - admin: Administration (futur)
    """
    if connection_type not in ["game", "chat", "admin"]:
        await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
        return

    connection_id = await websocket_manager.connect(websocket)

    try:
        while True:
            # Réception du message
            data = await websocket.receive_text()

            # Traitement via le gestionnaire de messages
            async for db in get_db():
                await message_handler.handle_message(connection_id, data, db)
                break

    except WebSocketDisconnect:
        await websocket_manager.disconnect(connection_id)
    except Exception as e:
        print(f"❌ Erreur WebSocket: {e}")
        await websocket_manager.disconnect(connection_id)


# === ÉVÉNEMENTS DE DÉMARRAGE/ARRÊT (Legacy - pour compatibilité) ===

@app.on_event("startup")
async def startup_event():
    """Événement de démarrage (legacy)"""
    print("📡 Application démarrée (legacy event)")


@app.on_event("shutdown")
async def shutdown_event():
    """Événement d'arrêt (legacy)"""
    print("🔄 Application en cours d'arrêt (legacy event)")


# === CONFIGURATION FINALE ===

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS if not settings.DEBUG else 1,
        log_level="info",
        access_log=True,
        server_header=False,  # Sécurité
        date_header=False     # Sécurité
    )