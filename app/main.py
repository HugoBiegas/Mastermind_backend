"""
Application principale Quantum Mastermind
Point d'entrée FastAPI avec configuration complète
"""
import asyncio
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


# === LIFESPAN DE L'APPLICATION ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire du cycle de vie de l'application"""
    # Démarrage
    print("🚀 Démarrage de Quantum Mastermind...")

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
        print(f"⚛️ Quantum Backend: {settings.QISKIT_BACKEND}")

        yield

    finally:
        # Arrêt
        print("🛑 Arrêt de Quantum Mastermind...")

        # Arrêt des tâches
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

        # Fermeture des connexions
        await close_db()
        print("✅ Base de données fermée")

        print("👋 Quantum Mastermind arrêté proprement")


# === CRÉATION DE L'APPLICATION ===

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
    🎯⚛️ **Quantum Mastermind API** - Un jeu de Mastermind révolutionnaire intégrant les principes de l'informatique quantique.
    
    ## Fonctionnalités
    
    * **Authentification JWT** sécurisée avec refresh tokens
    * **Modes de jeu multiples** : Solo, Multijoueur, Battle Royale, Tournois
    * **Algorithmes quantiques** : Grover, Superposition, Intrication
    * **WebSocket temps réel** pour les parties multijoueurs
    * **Système de scoring** basé sur l'avantage quantique
    * **API REST complète** avec pagination et recherche avancée
    
    ## Technologies
    
    * **FastAPI** 0.115.12 - Framework web haute performance
    * **SQLAlchemy** 2.0.41 - ORM moderne avec support async
    * **PostgreSQL** 16 - Base de données relationnelle
    * **Redis** 7.4 - Cache et sessions
    * **Qiskit** 2.0.2 - Framework quantique IBM
    
    ---
    
    Développé avec ❤️ et ⚛️ pour repousser les limites du gaming quantique.
    """,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
    docs_url=f"{settings.API_V1_STR}/docs" if settings.DEBUG else None,
    redoc_url=f"{settings.API_V1_STR}/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)


# === MIDDLEWARE ===

# CORS - Configuration sécurisée
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Error-Code"]
)

# Compression Gzip
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Hosts de confiance
if settings.TRUSTED_HOSTS:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.TRUSTED_HOSTS
    )


# === MIDDLEWARE CUSTOM ===

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Ajoute les en-têtes de sécurité"""
    response = await call_next(request)

    # En-têtes de sécurité
    security_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }

    # En production uniquement
    if settings.ENVIRONMENT == "production":
        security_headers.update({
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
        })

    for header, value in security_headers.items():
        response.headers[header] = value

    return response


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Ajoute un ID de requête unique"""
    import uuid
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log les requêtes en production"""
    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time

    if settings.ENVIRONMENT == "production":
        # TODO: Intégrer avec un système de logging structuré
        print(f"[{request.state.request_id}] {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")

    response.headers["X-Process-Time"] = str(process_time)

    return response


# === GESTIONNAIRE D'EXCEPTIONS GLOBAL ===

@app.exception_handler(BaseQuantumMastermindError)
async def quantum_mastermind_exception_handler(
    request: Request,
    exc: BaseQuantumMastermindError
):
    """Gestionnaire pour les exceptions métier"""
    return JSONResponse(
        status_code=get_http_status_code(exc),
        content=exc.to_dict(),
        headers={"X-Error-Code": exc.error_code}
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Gestionnaire pour les HTTPException"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": exc.detail,
            "details": {}
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Gestionnaire pour les exceptions générales"""
    error_details = get_exception_details(exc)

    # En développement, on peut révéler plus de détails
    if settings.DEBUG:
        error_details["debug_info"] = {
            "exception_type": type(exc).__name__,
            "traceback": str(exc)
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "Une erreur interne s'est produite",
            "details": error_details if settings.DEBUG else {}
        }
    )


# === ROUTES PRINCIPALES ===

@app.get("/", tags=["Root"])
async def root():
    """Page d'accueil de l'API"""
    return {
        "message": "🎯⚛️ Quantum Mastermind API",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "operational",
        "quantum_ready": True,
        "features": [
            "🔐 Authentification JWT sécurisée",
            "🎮 Modes de jeu multiples",
            "⚛️ Algorithmes quantiques intégrés",
            "📡 WebSocket temps réel",
            "📊 Statistiques avancées",
            "🏆 Système de classement"
        ],
        "endpoints": {
            "docs": f"{settings.API_V1_STR}/docs" if settings.DEBUG else "disabled",
            "auth": f"{settings.API_V1_STR}/auth",
            "users": f"{settings.API_V1_STR}/users",
            "games": f"{settings.API_V1_STR}/games",
            "websocket": "/ws"
        },
        "quantum_info": {
            "backend": settings.QISKIT_BACKEND,
            "max_qubits": settings.MAX_QUBITS,
            "quantum_shots": settings.QUANTUM_SHOTS
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Endpoint de santé pour les checks de déploiement"""
    # Vérification de la base de données
    db_healthy = True
    try:
        async for db in get_db():
            await db.execute("SELECT 1")
            break
    except Exception:
        db_healthy = False

    # Statistiques WebSocket
    ws_stats = websocket_manager.get_connection_stats()

    # Informations quantum
    try:
        from app.services.quantum import quantum_service
        quantum_info = quantum_service.get_backend_info()
    except Exception:
        quantum_info = {"available": False, "error": "Service indisponible"}

    status_code = status.HTTP_200_OK if db_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if db_healthy else "unhealthy",
            "timestamp": time.time(),
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "services": {
                "database": "up" if db_healthy else "down",
                "websocket": "up",
                "quantum": "up" if quantum_info["available"] else "down"
            },
            "metrics": {
                "websocket_connections": ws_stats["total_connections"],
                "authenticated_users": ws_stats["authenticated_connections"],
                "active_game_rooms": ws_stats["active_game_rooms"]
            },
            "quantum_backend": quantum_info
        }
    )


@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """Endpoint de métriques pour Prometheus"""
    if not settings.ENABLE_METRICS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Métriques désactivées"
        )

    ws_stats = websocket_manager.get_connection_stats()

    # Format Prometheus basique
    metrics = [
        f"# HELP quantum_mastermind_websocket_connections Total WebSocket connections",
        f"# TYPE quantum_mastermind_websocket_connections gauge",
        f"quantum_mastermind_websocket_connections {ws_stats['total_connections']}",
        "",
        f"# HELP quantum_mastermind_authenticated_users Authenticated users",
        f"# TYPE quantum_mastermind_authenticated_users gauge",
        f"quantum_mastermind_authenticated_users {ws_stats['authenticated_connections']}",
        "",
        f"# HELP quantum_mastermind_game_rooms Active game rooms",
        f"# TYPE quantum_mastermind_game_rooms gauge",
        f"quantum_mastermind_game_rooms {ws_stats['active_game_rooms']}",
    ]

    return "\n".join(metrics)


# === ROUTES API ===

# Inclusion des routes avec préfixe
app.include_router(auth.router, prefix=settings.API_V1_STR, tags=["Authentification"])
app.include_router(users.router, prefix=settings.API_V1_STR, tags=["Utilisateurs"])
app.include_router(games.router, prefix=settings.API_V1_STR, tags=["Jeux"])


# === WEBSOCKET ===

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket principal"""
    connection_id = None

    try:
        # Connexion
        connection_id = await websocket_manager.connect(websocket)

        # Boucle de traitement des messages
        while True:
            # Attente d'un message
            message = await websocket.receive_text()

            # Traitement avec base de données
            async for db in get_db():
                await message_handler.handle_message(connection_id, message, db)
                break

    except WebSocketDisconnect:
        # Déconnexion normale
        pass
    except Exception as e:
        # Erreur de connexion
        print(f"Erreur WebSocket pour {connection_id}: {e}")
    finally:
        # Nettoyage
        if connection_id:
            await websocket_manager.disconnect(connection_id)


@app.get("/ws/stats", tags=["WebSocket"])
async def websocket_stats():
    """Statistiques des connexions WebSocket"""
    return websocket_manager.get_connection_stats()


@app.get("/ws/rooms", tags=["WebSocket"])
async def websocket_rooms():
    """Liste des rooms WebSocket actives"""
    rooms_info = {}

    for room_id in websocket_manager.game_rooms.keys():
        room_info = websocket_manager.get_room_info(room_id)
        if room_info:
            rooms_info[room_id] = room_info

    return {
        "total_rooms": len(rooms_info),
        "rooms": rooms_info
    }


# === TÂCHES PÉRIODIQUES ===

async def websocket_cleanup_task():
    """Tâche de nettoyage périodique des WebSockets"""
    while True:
        try:
            await asyncio.sleep(30)  # Toutes les 30 secondes
            await websocket_manager.heartbeat_check()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Erreur lors du nettoyage WebSocket: {e}")


# === ROUTES STATIQUES (OPTIONNEL) ===

if settings.DEBUG:
    # En développement, on peut servir des fichiers statiques
    # app.mount("/static", StaticFiles(directory="static"), name="static")
    pass


# === POINT D'ENTRÉE ===

if __name__ == "__main__":
    import uvicorn

    print("🚀 Démarrage en mode développement...")

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
        server_header=False,  # Sécurité
        date_header=False     # Sécurité
    )