# 🎯⚛️ Quantum Mastermind

Un jeu de Mastermind intégrant les principes de l'informatique quantique, avec des modes solo et multijoueur avancés.

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.12-green.svg)](https://fastapi.tiangolo.com)
[![Qiskit](https://img.shields.io/badge/Qiskit-2.0.2-purple.svg)](https://qiskit.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

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

## 🏗️ Architecture

```
quantum-mastermind/
├── app/                    # Code source Python
│   ├── main.py            # Point d'entrée FastAPI
│   ├── models/            # Modèles SQLAlchemy
│   ├── api/               # Routes API
│   ├── quantum/           # Logique quantique (Qiskit)
│   ├── websocket/         # Gestion WebSocket temps réel
│   └── utils/             # Utilitaires et helpers
├── docker-compose.yml     # Orchestration services
├── Dockerfile            # Image application Python
├── init.sql              # Schéma base de données
├── requirements.txt      # Dépendances Python
└── README.md             # Documentation
```

### 🔧 Stack Technique

**Backend**
- **FastAPI 0.115.12** : API REST haute performance
- **WebSockets** : Communication temps réel
- **SQLAlchemy 2.0.41** : ORM moderne avec support async
- **PostgreSQL 16** : Base de données relationnelle
- **Redis 7.4** : Cache et sessions
- **Uvicorn** : Serveur ASGI

**Quantum Computing**
- **Qiskit 2.0.2** : Framework IBM pour informatique quantique
- **Qiskit Aer** : Simulateur quantique
- **NumPy & SciPy** : Calculs scientifiques

**DevOps & Sécurité**
- **Docker & Docker Compose** : Containerisation
- **JWT** : Authentification sécurisée
- **bcrypt** : Hachage des mots de passe
- **CORS** : Configuration sécurisée
- **Logging** : Audit et monitoring

## 🚀 Installation et Démarrage

### Prérequis
- Docker 24.0+
- Docker Compose 2.0+
- Git
- 4GB RAM minimum (pour les simulations quantiques)

## 🎯 Guide d'Utilisation

### 🎮 Modes de Jeu

**Solo Quantique**
- Utilisez la superposition pour révéler des indices
- L'algorithme de Grover pour des hints optimisés
- Score bonus basé sur l'efficacité quantique

**Battle Royale**
- 2-8 joueurs simultanés
- Chacun résout sa propre combinaison
- Élimination des plus lents à chaque round
- Derniers survivants dans la finale

**Mode Synchrone**
- Tous les joueurs ont la même combinaison
- Attente de tous avant révélation des résultats
- Classement basé sur vitesse et précision

## 📈 Monitoring et Logs

### Métriques Disponibles
- Nombre de connexions WebSocket actives
- Performances des requêtes API
- Utilisation des ressources quantiques
- Statistiques de jeu en temps réel


## 🛡️ Sécurité

### Authentification JWT
- Tokens sécurisés avec expiration
- Refresh tokens pour sessions longues
- Protection CSRF intégrée

### Base de Données
- Mots de passe hachés avec bcrypt
- Requêtes préparées (protection SQL injection)
- Audit trail complet
- Chiffrement des données sensibles

### Infrastructure
- Communications HTTPS en production
- CORS configuré restrictivement
- Rate limiting sur les API
- Validation stricte des entrées
