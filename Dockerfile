FROM python:3.12-slim

# Métadonnées
LABEL maintainer="quantum-mastermind-2025"
LABEL description="Quantum Mastermind API - Versions 2025 optimisées"
LABEL version="2.0"

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Répertoire de travail
WORKDIR /app

# Installation des dépendances système optimisées
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Mise à jour pip et installation des requirements avec timeout étendu
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --timeout 300 --retries 3 -r requirements.txt

# Copie du code source
COPY ./app ./app

# Création utilisateur non-root pour sécurité
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Exposition du port
EXPOSE 8000

# Health check optimisé
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Point d'entrée optimisé
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--access-log"]
