-- Script d'initialisation pour Quantum Mastermind (2025)
-- Compatible PostgreSQL 16 + SQLAlchemy 2.0.41
-- Exécuté automatiquement au démarrage du conteneur

-- Connexion à la base
\c quantum_mastermind;

-- Extensions PostgreSQL modernes
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- === TABLES PRINCIPALES ===

-- Table des utilisateurs (optimisée 2025)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(254) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,

    -- Statistiques de jeu
    total_games INTEGER DEFAULT 0 CHECK (total_games >= 0),
    wins INTEGER DEFAULT 0 CHECK (wins >= 0 AND wins <= total_games),
    best_time FLOAT DEFAULT NULL CHECK (best_time > 0),
    average_time FLOAT DEFAULT NULL CHECK (average_time > 0),
    quantum_score INTEGER DEFAULT 0 CHECK (quantum_score >= 0),

    -- Métadonnées
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    login_count INTEGER DEFAULT 0,

    -- Préférences JSON
    preferences JSONB DEFAULT '{}',

    CONSTRAINT valid_win_rate CHECK (wins <= total_games)
);

-- Table des parties (optimisée)
CREATE TABLE IF NOT EXISTS games (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Configuration du jeu
    game_type VARCHAR(20) NOT NULL DEFAULT 'classic'
        CHECK (game_type IN ('classic', 'quantum', 'hybrid', 'tournament')),
    game_mode VARCHAR(20) NOT NULL DEFAULT 'solo'
        CHECK (game_mode IN ('solo', 'multiplayer', 'ranked', 'training')),
    difficulty VARCHAR(10) NOT NULL DEFAULT 'normal'
        CHECK (difficulty IN ('easy', 'normal', 'hard', 'expert')),

    -- État et règles
    status VARCHAR(20) DEFAULT 'waiting'
        CHECK (status IN ('waiting', 'active', 'paused', 'finished', 'cancelled')),
    max_attempts INTEGER DEFAULT 10 CHECK (max_attempts BETWEEN 1 AND 20),
    time_limit INTEGER DEFAULT NULL CHECK (time_limit > 0), -- en secondes

    -- Solutions
    quantum_solution JSONB DEFAULT NULL,
    classical_solution JSONB DEFAULT NULL,
    solution_hash VARCHAR(64), -- SHA-256 pour vérification

    -- Résultats
    winner_id UUID REFERENCES users(id) ON DELETE SET NULL,
    total_attempts INTEGER DEFAULT 0,
    game_duration INTERVAL DEFAULT NULL,

    -- Métadonnées
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    finished_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,

    -- Données supplémentaires
    settings JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}'
);

-- Table des joueurs dans une partie
CREATE TABLE IF NOT EXISTS game_players (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    player_name VARCHAR(100) NOT NULL,

    -- État du joueur
    status VARCHAR(20) DEFAULT 'joined'
        CHECK (status IN ('joined', 'ready', 'playing', 'finished', 'disconnected')),
    is_host BOOLEAN DEFAULT false,
    join_order INTEGER NOT NULL,

    -- Performance
    score INTEGER DEFAULT 0 CHECK (score >= 0),
    attempts_count INTEGER DEFAULT 0 CHECK (attempts_count >= 0),
    best_attempt INTEGER DEFAULT NULL,
    time_taken INTERVAL DEFAULT NULL,

    -- Résultat
    has_won BOOLEAN DEFAULT false,
    final_rank INTEGER DEFAULT NULL,
    completion_rate FLOAT DEFAULT 0.0 CHECK (completion_rate BETWEEN 0.0 AND 1.0),

    -- Quantum spécifique
    quantum_measurements_used INTEGER DEFAULT 0 CHECK (quantum_measurements_used >= 0),
    grover_hints_used INTEGER DEFAULT 0 CHECK (grover_hints_used >= 0),
    entanglement_exploits INTEGER DEFAULT 0 CHECK (entanglement_exploits >= 0),
    quantum_advantage_score FLOAT DEFAULT 0.0,

    -- Métadonnées
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,

    -- Contraintes
    UNIQUE(game_id, user_id),
    UNIQUE(game_id, join_order)
);

-- Table des tentatives (optimisée)
CREATE TABLE IF NOT EXISTS game_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    player_id UUID NOT NULL REFERENCES game_players(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Détails de la tentative
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    guess JSONB NOT NULL,
    is_valid BOOLEAN DEFAULT true,

    -- Résultats
    result JSONB NOT NULL, -- {blacks: int, whites: int, etc.}
    is_correct BOOLEAN DEFAULT false,
    confidence_score FLOAT DEFAULT NULL CHECK (confidence_score BETWEEN 0.0 AND 1.0),

    -- Quantum spécifique
    quantum_result JSONB DEFAULT NULL,
    measurement_used BOOLEAN DEFAULT false,
    measured_position INTEGER DEFAULT NULL CHECK (measured_position BETWEEN 0 AND 3),
    quantum_state_before JSONB DEFAULT NULL,
    quantum_state_after JSONB DEFAULT NULL,

    -- Performance
    time_taken INTERVAL NOT NULL,
    think_time INTERVAL DEFAULT NULL,
    response_time INTERVAL DEFAULT NULL,

    -- Métadonnées
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    client_info JSONB DEFAULT '{}', -- IP, User-Agent, etc.

    -- Contraintes
    UNIQUE(game_id, player_id, attempt_number)
);

-- Table des sessions WebSocket
CREATE TABLE IF NOT EXISTS websocket_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) UNIQUE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    game_id UUID REFERENCES games(id) ON DELETE SET NULL,

    -- État de la connexion
    status VARCHAR(20) DEFAULT 'connected'
        CHECK (status IN ('connected', 'disconnected', 'error')),
    ip_address INET,
    user_agent TEXT,

    -- Métadonnées
    connected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    disconnected_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Statistiques
    messages_sent INTEGER DEFAULT 0,
    messages_received INTEGER DEFAULT 0,

    -- Données de session
    session_data JSONB DEFAULT '{}'
);

-- Table d'audit (pour traçabilité)
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID DEFAULT NULL,

    -- Détails
    old_values JSONB DEFAULT NULL,
    new_values JSONB DEFAULT NULL,
    client_info JSONB DEFAULT '{}',

    -- Métadonnées
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- === INDEX POUR PERFORMANCE ===

-- Index principaux
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_last_login ON users(last_login);

-- Index pour les jeux
CREATE INDEX IF NOT EXISTS idx_games_room_id ON games(room_id);
CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);
CREATE INDEX IF NOT EXISTS idx_games_type ON games(game_type);
CREATE INDEX IF NOT EXISTS idx_games_created_by ON games(created_by);
CREATE INDEX IF NOT EXISTS idx_games_created_at ON games(created_at);
CREATE INDEX IF NOT EXISTS idx_games_finished_at ON games(finished_at);

-- Index pour les joueurs
CREATE INDEX IF NOT EXISTS idx_game_players_game_id ON game_players(game_id);
CREATE INDEX IF NOT EXISTS idx_game_players_user_id ON game_players(user_id);
CREATE INDEX IF NOT EXISTS idx_game_players_status ON game_players(status);
CREATE INDEX IF NOT EXISTS idx_game_players_score ON game_players(score DESC);

-- Index pour les tentatives
CREATE INDEX IF NOT EXISTS idx_game_attempts_game_id ON game_attempts(game_id);
CREATE INDEX IF NOT EXISTS idx_game_attempts_player_id ON game_attempts(player_id);
CREATE INDEX IF NOT EXISTS idx_game_attempts_user_id ON game_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_game_attempts_created_at ON game_attempts(created_at);
CREATE INDEX IF NOT EXISTS idx_game_attempts_correct ON game_attempts(is_correct);

-- Index pour WebSocket
CREATE INDEX IF NOT EXISTS idx_websocket_sessions_user_id ON websocket_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_websocket_sessions_game_id ON websocket_sessions(game_id);
CREATE INDEX IF NOT EXISTS idx_websocket_sessions_status ON websocket_sessions(status);
CREATE INDEX IF NOT EXISTS idx_websocket_sessions_connected_at ON websocket_sessions(connected_at);

-- Index JSON (GIN)
CREATE INDEX IF NOT EXISTS idx_users_preferences ON users USING GIN(preferences);
CREATE INDEX IF NOT EXISTS idx_games_settings ON games USING GIN(settings);
CREATE INDEX IF NOT EXISTS idx_games_metadata ON games USING GIN(metadata);
CREATE INDEX IF NOT EXISTS idx_game_attempts_result ON game_attempts USING GIN(result);
CREATE INDEX IF NOT EXISTS idx_game_attempts_quantum_result ON game_attempts USING GIN(quantum_result);

-- === FONCTIONS ET TRIGGERS ===

-- Fonction pour updated_at automatique
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers pour updated_at
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Fonction pour calculer le score quantique
CREATE OR REPLACE FUNCTION calculate_quantum_score(
    measurements INTEGER DEFAULT 0,
    grover_uses INTEGER DEFAULT 0,
    entanglements INTEGER DEFAULT 0,
    time_bonus FLOAT DEFAULT 0.0
) RETURNS INTEGER AS $$
BEGIN
    RETURN GREATEST(0,
        (measurements * 10) +
        (grover_uses * 50) +
        (entanglements * 25) +
        ROUND(time_bonus)::INTEGER
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Fonction pour valider les tentatives
CREATE OR REPLACE FUNCTION validate_guess(guess_json JSONB)
RETURNS BOOLEAN AS $$
BEGIN
    -- Vérifie que c'est un array de 4 éléments
    IF jsonb_array_length(guess_json) != 4 THEN
        RETURN false;
    END IF;

    -- Vérifie que tous les éléments sont des couleurs valides
    IF EXISTS (
        SELECT 1 FROM jsonb_array_elements_text(guess_json) AS color
        WHERE color NOT IN ('red', 'blue', 'green', 'yellow', 'orange', 'purple', 'black', 'white')
    ) THEN
        RETURN false;
    END IF;

    RETURN true;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- === VUES OPTIMISÉES ===

-- Vue pour les statistiques des joueurs
CREATE OR REPLACE VIEW player_stats AS
SELECT
    u.id,
    u.username,
    u.email,
    u.total_games,
    u.wins,
    CASE
        WHEN u.total_games > 0 THEN ROUND((u.wins::NUMERIC / u.total_games * 100), 2)
        ELSE 0
    END as win_rate_percent,
    u.best_time,
    u.average_time,
    u.quantum_score,
    u.created_at,
    u.last_login,
    u.login_count,

    -- Statistiques agrégées
    COALESCE(recent_stats.recent_games, 0) as games_last_30_days,
    COALESCE(recent_stats.recent_wins, 0) as wins_last_30_days,
    COALESCE(quantum_stats.total_measurements, 0) as total_quantum_measurements,
    COALESCE(quantum_stats.total_grover_uses, 0) as total_grover_hints_used,
    COALESCE(quantum_stats.avg_quantum_score, 0.0) as avg_quantum_advantage

FROM users u

LEFT JOIN (
    SELECT
        gp.user_id,
        COUNT(*) as recent_games,
        SUM(CASE WHEN gp.has_won THEN 1 ELSE 0 END) as recent_wins
    FROM game_players gp
    JOIN games g ON g.id = gp.game_id
    WHERE g.created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
        AND g.status = 'finished'
    GROUP BY gp.user_id
) recent_stats ON recent_stats.user_id = u.id

LEFT JOIN (
    SELECT
        gp.user_id,
        SUM(gp.quantum_measurements_used) as total_measurements,
        SUM(gp.grover_hints_used) as total_grover_uses,
        AVG(gp.quantum_advantage_score) as avg_quantum_score
    FROM game_players gp
    GROUP BY gp.user_id
) quantum_stats ON quantum_stats.user_id = u.id;

-- Vue pour les jeux actifs
CREATE OR REPLACE VIEW active_games AS
SELECT
    g.*,
    COUNT(gp.id) as player_count,
    MAX(gp.joined_at) as last_player_joined,
    STRING_AGG(DISTINCT gp.player_name, ', ' ORDER BY gp.player_name) as players
FROM games g
LEFT JOIN game_players gp ON gp.game_id = g.id
WHERE g.status IN ('waiting', 'active', 'paused')
GROUP BY g.id;

-- Vue pour le leaderboard
CREATE OR REPLACE VIEW leaderboard AS
SELECT
    ROW_NUMBER() OVER (ORDER BY quantum_score DESC, wins DESC, win_rate_percent DESC) as rank,
    username,
    quantum_score,
    wins,
    total_games,
    win_rate_percent,
    best_time,
    created_at
FROM player_stats
WHERE total_games >= 5  -- Minimum 5 jeux pour apparaître
ORDER BY quantum_score DESC, wins DESC;

-- === DONNÉES DE TEST ===

-- Utilisateurs de test avec mots de passe hachés (bcrypt)
INSERT INTO users (username, email, password_hash, is_verified) VALUES
    ('quantum_alice', 'alice@quantum.dev', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewreBdaQK9rZ6.eG', true),
    ('quantum_bob', 'bob@quantum.dev', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewreBdaQK9rZ6.eG', true),
    ('quantum_charlie', 'charlie@quantum.dev', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewreBdaQK9rZ6.eG', true)
ON CONFLICT (username) DO NOTHING;

-- Mise à jour des statistiques de test
UPDATE users SET
    total_games = 15,
    wins = 8,
    best_time = 45.2,
    average_time = 125.6,
    quantum_score = 750,
    last_login = CURRENT_TIMESTAMP - INTERVAL '2 hours'
WHERE username = 'quantum_alice';

UPDATE users SET
    total_games = 22,
    wins = 12,
    best_time = 38.9,
    average_time = 98.3,
    quantum_score = 920,
    last_login = CURRENT_TIMESTAMP - INTERVAL '30 minutes'
WHERE username = 'quantum_bob';

-- === CONFIGURATION ET OPTIMISATION ===

-- Optimisations PostgreSQL
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET max_connections = 100;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;

-- Configuration de sécurité
ALTER SYSTEM SET log_connections = on;
ALTER SYSTEM SET log_disconnections = on;
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_min_duration_statement = 1000; -- Log des requêtes > 1s

-- === MESSAGE DE CONFIRMATION ===

DO $$
BEGIN
    RAISE NOTICE '🎯 Base de données Quantum Mastermind (2025) initialisée avec succès!';
    RAISE NOTICE '📊 Tables créées: users, games, game_players, game_attempts, websocket_sessions, audit_log';
    RAISE NOTICE '🔍 Index optimisés pour PostgreSQL 16';
    RAISE NOTICE '⚛️ Support quantique complet intégré';
    RAISE NOTICE '🛡️ Sécurité et audit activés';
    RAISE NOTICE '👥 3 utilisateurs de test créés (password: password123)';
    RAISE NOTICE '📈 Vues de statistiques disponibles: player_stats, active_games, leaderboard';
    RAISE NOTICE '✅ Prêt pour SQLAlchemy 2.0.41 + FastAPI 0.115.12';
END $$;
