-- =====================================================
-- QUANTUM MASTERMIND - SCHÉMA POSTGRESQL CORRIGÉ
-- Compatible avec les modèles Python existants
-- CORRECTION: Correspond exactement aux modèles SQLAlchemy
-- =====================================================

-- Connexion à la base de données
\c quantum_mastermind;

-- Extensions PostgreSQL 16
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- === TABLE USERS (identique à l'original) ===
CREATE TABLE IF NOT EXISTS users (
    -- Clé primaire UUID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Informations d'identification
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(254) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,

    -- Informations personnelles
    full_name VARCHAR(100) DEFAULT NULL,
    avatar_url VARCHAR(500) DEFAULT NULL,
    bio TEXT DEFAULT NULL,

    -- Statut et permissions
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    is_superuser BOOLEAN NOT NULL DEFAULT false,

    -- Paramètres et préférences (JSONB pour PostgreSQL)
    preferences JSONB DEFAULT '{}',
    settings JSONB DEFAULT '{}',

    -- Statistiques de jeu
    total_games INTEGER NOT NULL DEFAULT 0,
    games_won INTEGER NOT NULL DEFAULT 0,
    total_score INTEGER NOT NULL DEFAULT 0,
    best_score INTEGER DEFAULT NULL,
    quantum_points INTEGER NOT NULL DEFAULT 0,
    rank VARCHAR(20) NOT NULL DEFAULT 'Bronze',

    -- Métadonnées temporelles
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE DEFAULT NULL,

    -- Sécurité et audit
    email_verified_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    last_ip_address INET DEFAULT NULL,

    -- Contraintes
    CONSTRAINT ck_users_games_won CHECK (games_won >= 0 AND games_won <= total_games),
    CONSTRAINT ck_users_total_games CHECK (total_games >= 0),
    CONSTRAINT ck_users_total_score CHECK (total_score >= 0),
    CONSTRAINT ck_users_quantum_points CHECK (quantum_points >= 0),
    CONSTRAINT ck_users_login_attempts CHECK (login_attempts >= 0),
    CONSTRAINT ck_users_rank CHECK (rank IN ('Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond', 'Master', 'Grandmaster'))
);

-- === TABLE GAMES (identique à l'original) ===
CREATE TABLE IF NOT EXISTS games (
    -- Clé primaire UUID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Code de room unique
    room_code VARCHAR(10) UNIQUE NOT NULL,

    -- Configuration du jeu
    game_type VARCHAR(20) NOT NULL DEFAULT 'classic',
    game_mode VARCHAR(20) NOT NULL DEFAULT 'single',
    status VARCHAR(20) NOT NULL DEFAULT 'waiting',
    difficulty VARCHAR(20) NOT NULL DEFAULT 'medium',

    -- Paramètres de jeu
    combination_length INTEGER NOT NULL DEFAULT 4,
    available_colors INTEGER NOT NULL DEFAULT 6,
    max_attempts INTEGER DEFAULT 12,
    time_limit INTEGER DEFAULT NULL,  -- en secondes
    max_players INTEGER NOT NULL DEFAULT 1,

    -- Solution (stockée de manière sécurisée)
    solution JSONB NOT NULL,

    -- Configuration avancée
    is_private BOOLEAN NOT NULL DEFAULT false,
    allow_spectators BOOLEAN NOT NULL DEFAULT true,
    enable_chat BOOLEAN NOT NULL DEFAULT true,
    quantum_enabled BOOLEAN NOT NULL DEFAULT false,

    -- Relations
    creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Paramètres avancés (JSONB)
    settings JSONB DEFAULT '{"allow_duplicates": true, "allow_blanks": false, "quantum_enabled": true, "hint_cost": 10, "auto_reveal_pegs": true, "show_statistics": true}',

    -- Données quantiques (si applicable)
    quantum_data JSONB DEFAULT NULL,

    -- Métadonnées temporelles
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    finished_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,

    -- Contraintes
    CONSTRAINT ck_games_combination_length CHECK (combination_length >= 2 AND combination_length <= 8),
    CONSTRAINT ck_games_available_colors CHECK (available_colors >= 3 AND available_colors <= 15),
    CONSTRAINT ck_games_max_attempts CHECK (max_attempts IS NULL OR max_attempts > 0),
    CONSTRAINT ck_games_time_limit CHECK (time_limit IS NULL OR time_limit > 0),
    CONSTRAINT ck_games_max_players CHECK (max_players >= 1 AND max_players <= 50),
    CONSTRAINT ck_games_type CHECK (game_type IN ('classic', 'quantum', 'speed', 'precision', 'multiplayer')),
    CONSTRAINT ck_games_mode CHECK (game_mode IN ('single', 'multiplayer', 'battle_royale', 'tournament')),
    CONSTRAINT ck_games_status CHECK (status IN ('waiting', 'starting', 'active', 'paused', 'finished', 'cancelled', 'aborted')),
    CONSTRAINT ck_games_difficulty CHECK (difficulty IN ('easy', 'medium', 'hard', 'expert', 'quantum'))
);

-- === TABLE GAME_PARTICIPATIONS (CORRIGÉ: utilise player_id) ===
CREATE TABLE IF NOT EXISTS game_participations (
    -- Clé primaire UUID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relations (CORRIGÉ: player_id au lieu de user_id)
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    player_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Statut de participation
    status VARCHAR(20) NOT NULL DEFAULT 'waiting',
    role VARCHAR(20) NOT NULL DEFAULT 'player',

    -- Ordre et position
    join_order INTEGER NOT NULL,
    finish_position INTEGER DEFAULT NULL,

    -- Scoring et statistiques
    score INTEGER NOT NULL DEFAULT 0,
    attempts_made INTEGER NOT NULL DEFAULT 0,
    quantum_hints_used INTEGER NOT NULL DEFAULT 0,
    time_taken INTEGER DEFAULT NULL,  -- en secondes

    -- Flags (AJOUT: is_creator et is_spectator)
    is_ready BOOLEAN NOT NULL DEFAULT false,
    is_winner BOOLEAN NOT NULL DEFAULT false,
    is_eliminated BOOLEAN NOT NULL DEFAULT false,
    is_creator BOOLEAN NOT NULL DEFAULT false,
    is_spectator BOOLEAN NOT NULL DEFAULT false,

    -- Métadonnées temporelles
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    finished_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Contraintes
    UNIQUE(game_id, player_id),
    CONSTRAINT ck_participations_score CHECK (score >= 0),
    CONSTRAINT ck_participations_attempts CHECK (attempts_made >= 0),
    CONSTRAINT ck_participations_quantum_hints CHECK (quantum_hints_used >= 0),
    CONSTRAINT ck_participations_time_taken CHECK (time_taken IS NULL OR time_taken > 0),
    CONSTRAINT ck_participations_status CHECK (status IN ('waiting', 'ready', 'active', 'finished', 'eliminated', 'disconnected', 'spectator', 'left')),
    CONSTRAINT ck_participations_role CHECK (role IN ('player', 'spectator', 'moderator'))
);

-- === TABLE GAME_ATTEMPTS (CORRIGÉ: utilise player_id) ===
CREATE TABLE IF NOT EXISTS game_attempts (
    -- Clé primaire UUID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relations (CORRIGÉ: player_id au lieu de user_id)
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    player_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Détails de la tentative
    attempt_number INTEGER NOT NULL,
    combination JSONB NOT NULL,  -- La combinaison proposée [1,2,3,4]
    mastermind_number INTEGER NOT NULL DEFAULT 1,
    mastermind_total INTEGER NOT NULL DEFAULT 1

    -- Résultats
    correct_positions INTEGER NOT NULL DEFAULT 0,  -- Pegs noirs
    correct_colors INTEGER NOT NULL DEFAULT 0,     -- Pegs blancs
    is_correct BOOLEAN NOT NULL DEFAULT false,     -- Solution trouvée

    -- Scoring et temps
    attempt_score INTEGER NOT NULL DEFAULT 0,
    time_taken INTEGER DEFAULT NULL,  -- temps pour cette tentative en ms

    -- Données quantiques (si applicable)
    quantum_data JSONB DEFAULT NULL,
    used_quantum_hint BOOLEAN NOT NULL DEFAULT false,
    hint_type VARCHAR(50) DEFAULT NULL,

    -- Métadonnées
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Contraintes
    UNIQUE(game_id, player_id, attempt_number),
    CONSTRAINT ck_attempts_attempt_number CHECK (attempt_number > 0),
    CONSTRAINT ck_attempts_correct_positions CHECK (correct_positions >= 0),
    CONSTRAINT ck_attempts_correct_colors CHECK (correct_colors >= 0),
    CONSTRAINT ck_attempts_score CHECK (attempt_score >= 0),
    CONSTRAINT ck_attempts_time_taken CHECK (time_taken IS NULL OR time_taken > 0),
    CONSTRAINT ck_attempts_hint_type CHECK (hint_type IS NULL OR hint_type IN ('grover', 'superposition', 'entanglement', 'interference'))
);

-- =====================================================
-- TABLES MULTIPLAYER (CORRRIGÉES pour correspondre aux modèles Python)
-- =====================================================

-- === TABLE MULTIPLAYER_GAMES (CORRIGÉ: avec toutes les colonnes du modèle Python) ===
CREATE TABLE IF NOT EXISTS multiplayer_games (
    -- Clé primaire UUID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Référence au jeu de base
    base_game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,

    -- Type de partie multijoueur
    game_type VARCHAR(50) NOT NULL DEFAULT 'multi_mastermind',

    -- Configuration des masterminds
    total_masterminds INTEGER NOT NULL DEFAULT 3,
    current_mastermind INTEGER NOT NULL DEFAULT 1,
    is_final_mastermind BOOLEAN NOT NULL DEFAULT false,

    -- Configuration de la difficulté (dupliqué pour performance)
    difficulty VARCHAR(20) NOT NULL DEFAULT 'medium',

    -- Configuration des objets
    items_enabled BOOLEAN NOT NULL DEFAULT true,
    items_per_mastermind INTEGER NOT NULL DEFAULT 1,

    -- Métadonnées temporelles (AJOUT: started_at et finished_at manquants)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    finished_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Contraintes
    CONSTRAINT ck_multiplayer_games_type CHECK (game_type IN ('multi_mastermind', 'battle_royale', 'tournament')),
    CONSTRAINT ck_multiplayer_games_masterminds CHECK (total_masterminds >= 1 AND total_masterminds <= 10),
    CONSTRAINT ck_multiplayer_games_current CHECK (current_mastermind >= 1 AND current_mastermind <= total_masterminds),
    CONSTRAINT ck_multiplayer_games_difficulty CHECK (difficulty IN ('easy', 'medium', 'hard', 'expert', 'quantum')),
    CONSTRAINT ck_multiplayer_games_items_per_mastermind CHECK (items_per_mastermind >= 0),

    -- Index unique sur base_game_id
    CONSTRAINT uq_multiplayer_games_base_game UNIQUE (base_game_id)
);

-- === TABLE GAME_MASTERMINDS (identique à la version précédente) ===
CREATE TABLE IF NOT EXISTS game_masterminds (
    -- Clé primaire UUID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Référence à la partie multijoueur
    multiplayer_game_id UUID NOT NULL REFERENCES multiplayer_games(id) ON DELETE CASCADE,

    -- Numéro du mastermind
    mastermind_number INTEGER NOT NULL,

    -- Configuration du mastermind
    combination_length INTEGER NOT NULL,
    available_colors INTEGER NOT NULL,
    max_attempts INTEGER NOT NULL,

    -- Solution secrète
    solution JSONB NOT NULL,

    -- État du mastermind
    is_active BOOLEAN NOT NULL DEFAULT false,
    is_completed BOOLEAN NOT NULL DEFAULT false,

    -- Métadonnées temporelles
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Contraintes
    CONSTRAINT ck_game_masterminds_number CHECK (mastermind_number >= 1),
    CONSTRAINT ck_game_masterminds_length CHECK (combination_length >= 2 AND combination_length <= 8),
    CONSTRAINT ck_game_masterminds_colors CHECK (available_colors >= 3 AND available_colors <= 15),
    CONSTRAINT ck_game_masterminds_attempts CHECK (max_attempts > 0),

    -- Index unique sur multiplayer_game_id + mastermind_number
    CONSTRAINT uq_game_masterminds_game_number UNIQUE (multiplayer_game_id, mastermind_number)
);

-- === TABLE PLAYER_PROGRESS (identique à la version précédente) ===
CREATE TABLE IF NOT EXISTS player_progress (
    -- Clé primaire UUID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Références
    multiplayer_game_id UUID NOT NULL REFERENCES multiplayer_games(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Statut du joueur
    status VARCHAR(30) NOT NULL DEFAULT 'waiting',

    -- Progression
    current_mastermind INTEGER NOT NULL DEFAULT 1,
    completed_masterminds INTEGER NOT NULL DEFAULT 0,

    -- Scores
    total_score INTEGER NOT NULL DEFAULT 0,

    -- Temps total
    total_time FLOAT NOT NULL DEFAULT 0.0,

    -- État de fin
    is_finished BOOLEAN NOT NULL DEFAULT false,
    finish_position INTEGER DEFAULT NULL,
    finish_time TIMESTAMP WITH TIME ZONE DEFAULT NULL,

    -- Objets collectés (AJOUT: colonnes JSONB pour les objets)
    collected_items JSONB DEFAULT '[]',
    used_items JSONB DEFAULT '[]',

    -- Métadonnées temporelles (AJOUT: created_at et updated_at manquants)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Contraintes
    CONSTRAINT ck_player_progress_status CHECK (status IN ('waiting', 'playing', 'mastermind_complete', 'finished', 'eliminated')),
    CONSTRAINT ck_player_progress_current CHECK (current_mastermind >= 1),
    CONSTRAINT ck_player_progress_completed CHECK (completed_masterminds >= 0),
    CONSTRAINT ck_player_progress_score CHECK (total_score >= 0),
    CONSTRAINT ck_player_progress_time CHECK (total_time >= 0),
    CONSTRAINT ck_player_progress_position CHECK (finish_position IS NULL OR finish_position >= 1),

    -- Index unique sur multiplayer_game_id + user_id
    CONSTRAINT uq_player_progress_game_user UNIQUE (multiplayer_game_id, user_id)
);

-- === TABLE PLAYER_MASTERMIND_ATTEMPTS (identique à la version précédente) ===
CREATE TABLE IF NOT EXISTS player_mastermind_attempts (
    -- Clé primaire UUID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Références
    player_progress_id UUID NOT NULL REFERENCES player_progress(id) ON DELETE CASCADE,
    mastermind_id UUID NOT NULL REFERENCES game_masterminds(id) ON DELETE CASCADE,

    -- Détails de la tentative
    attempt_number INTEGER NOT NULL,
    combination JSONB NOT NULL,
    exact_matches INTEGER NOT NULL,
    position_matches INTEGER NOT NULL,
    is_correct BOOLEAN NOT NULL DEFAULT false,

    -- Temps et score
    attempt_score INTEGER NOT NULL DEFAULT 0,
    time_taken FLOAT DEFAULT NULL,

    -- Données quantiques
    quantum_calculated BOOLEAN NOT NULL DEFAULT false,
    quantum_probabilities JSONB DEFAULT NULL,

    -- Métadonnées temporelles
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Contraintes
    CONSTRAINT ck_mastermind_attempts_number CHECK (attempt_number >= 1),
    CONSTRAINT ck_mastermind_attempts_exact CHECK (exact_matches >= 0),
    CONSTRAINT ck_mastermind_attempts_position CHECK (position_matches >= 0),
    CONSTRAINT ck_mastermind_attempts_score CHECK (attempt_score >= 0),
    CONSTRAINT ck_mastermind_attempts_time CHECK (time_taken IS NULL OR time_taken >= 0),

    -- Index unique sur player_progress_id + mastermind_id + attempt_number
    CONSTRAINT uq_mastermind_attempts_progress_mastermind_number UNIQUE (player_progress_id, mastermind_id, attempt_number)
);

-- === TABLE GAME_ITEMS (identique à la version précédente) ===
CREATE TABLE IF NOT EXISTS game_items (
    -- Clé primaire UUID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Informations de base
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    item_type VARCHAR(30) NOT NULL,
    rarity VARCHAR(20) NOT NULL,

    -- Configuration
    is_self_target BOOLEAN NOT NULL DEFAULT true,
    duration_seconds INTEGER DEFAULT NULL,
    effect_value FLOAT DEFAULT NULL,

    -- Métadonnées
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Contraintes
    CONSTRAINT ck_game_items_type CHECK (item_type IN (
        'extra_hint', 'time_bonus', 'skip_mastermind', 'double_score',
        'freeze_time', 'add_mastermind', 'reduce_attempts', 'scramble_colors'
    )),
    CONSTRAINT ck_game_items_rarity CHECK (rarity IN ('common', 'rare', 'epic', 'legendary')),
    CONSTRAINT ck_game_items_duration CHECK (duration_seconds IS NULL OR duration_seconds > 0)
);

-- === TABLE PLAYER_LEADERBOARD (identique à la version précédente) ===
CREATE TABLE IF NOT EXISTS player_leaderboard (
    -- Clé primaire UUID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Références
    multiplayer_game_id UUID NOT NULL REFERENCES multiplayer_games(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Classement
    final_position INTEGER NOT NULL,
    final_score INTEGER NOT NULL,
    total_time FLOAT NOT NULL,

    -- Statistiques détaillées
    masterminds_completed INTEGER NOT NULL DEFAULT 0,
    total_attempts INTEGER NOT NULL DEFAULT 0,
    perfect_solutions INTEGER NOT NULL DEFAULT 0,
    quantum_hints_used INTEGER NOT NULL DEFAULT 0,
    items_used INTEGER NOT NULL DEFAULT 0,

    -- Métadonnées temporelles
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Contraintes
    CONSTRAINT ck_player_leaderboard_position CHECK (final_position >= 1),
    CONSTRAINT ck_player_leaderboard_score CHECK (final_score >= 0),
    CONSTRAINT ck_player_leaderboard_time CHECK (total_time >= 0),
    CONSTRAINT ck_player_leaderboard_completed CHECK (masterminds_completed >= 0),
    CONSTRAINT ck_player_leaderboard_attempts CHECK (total_attempts >= 0),
    CONSTRAINT ck_player_leaderboard_perfect CHECK (perfect_solutions >= 0),
    CONSTRAINT ck_player_leaderboard_quantum CHECK (quantum_hints_used >= 0),
    CONSTRAINT ck_player_leaderboard_items CHECK (items_used >= 0),

    -- Index unique sur multiplayer_game_id + user_id
    CONSTRAINT uq_player_leaderboard_game_user UNIQUE (multiplayer_game_id, user_id)
);

-- === TABLE WEBSOCKET_SESSIONS (identique à l'original) ===
CREATE TABLE IF NOT EXISTS websocket_sessions (
    -- Clé primaire UUID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identification
    session_id VARCHAR(100) UNIQUE NOT NULL,
    connection_id VARCHAR(100) UNIQUE NOT NULL,

    -- Relations
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    game_id UUID REFERENCES games(id) ON DELETE SET NULL,

    -- État de la connexion
    status VARCHAR(20) NOT NULL DEFAULT 'connected',
    ip_address INET DEFAULT NULL,
    user_agent TEXT DEFAULT NULL,

    -- Métadonnées temporelles
    connected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    disconnected_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    last_heartbeat TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Statistiques
    messages_sent INTEGER NOT NULL DEFAULT 0,
    messages_received INTEGER NOT NULL DEFAULT 0,

    -- Données de session (JSONB)
    session_data JSONB DEFAULT '{}',

    -- Contraintes
    CONSTRAINT ck_websocket_status CHECK (status IN ('connected', 'disconnected', 'error', 'timeout')),
    CONSTRAINT ck_websocket_messages CHECK (messages_sent >= 0 AND messages_received >= 0)
);

-- === TABLE AUDIT_LOG (identique à l'original) ===
CREATE TABLE IF NOT EXISTS audit_log (
    -- Clé primaire UUID
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relations
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Action et ressource
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID DEFAULT NULL,

    -- Détails de l'action
    old_values JSONB DEFAULT NULL,
    new_values JSONB DEFAULT NULL,

    -- Informations client
    ip_address INET DEFAULT NULL,
    user_agent TEXT DEFAULT NULL,
    client_info JSONB DEFAULT '{}',

    -- Métadonnées
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Contraintes
    CONSTRAINT ck_audit_action CHECK (LENGTH(action) > 0),
    CONSTRAINT ck_audit_resource_type CHECK (LENGTH(resource_type) > 0)
);

-- =====================================================
-- INDEX POUR PERFORMANCE OPTIMALE
-- =====================================================

-- Index primaires Users
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_users_superuser ON users(is_superuser) WHERE is_superuser = true;
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_last_login ON users(last_login);
CREATE INDEX IF NOT EXISTS idx_users_rank ON users(rank);

-- Index Games
CREATE INDEX IF NOT EXISTS idx_games_room_code ON games(room_code);
CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);
CREATE INDEX IF NOT EXISTS idx_games_type ON games(game_type);
CREATE INDEX IF NOT EXISTS idx_games_mode ON games(game_mode);
CREATE INDEX IF NOT EXISTS idx_games_creator_id ON games(creator_id);
CREATE INDEX IF NOT EXISTS idx_games_created_at ON games(created_at);
CREATE INDEX IF NOT EXISTS idx_games_started_at ON games(started_at);
CREATE INDEX IF NOT EXISTS idx_games_finished_at ON games(finished_at);
CREATE INDEX IF NOT EXISTS idx_games_difficulty ON games(difficulty);
CREATE INDEX IF NOT EXISTS idx_games_public ON games(is_private) WHERE is_private = false;

-- Index composites Games
CREATE INDEX IF NOT EXISTS idx_games_status_created ON games(status, created_at);
CREATE INDEX IF NOT EXISTS idx_games_type_mode ON games(game_type, game_mode);
CREATE INDEX IF NOT EXISTS idx_games_creator_status ON games(creator_id, status);

-- Index Game Participations (CORRIGÉ: player_id)
CREATE INDEX IF NOT EXISTS idx_participations_game_id ON game_participations(game_id);
CREATE INDEX IF NOT EXISTS idx_participations_player_id ON game_participations(player_id);
CREATE INDEX IF NOT EXISTS idx_participations_status ON game_participations(status);
CREATE INDEX IF NOT EXISTS idx_participations_score ON game_participations(score DESC);
CREATE INDEX IF NOT EXISTS idx_participations_join_order ON game_participations(join_order);
CREATE INDEX IF NOT EXISTS idx_participations_finished_at ON game_participations(finished_at);

-- Index Game Attempts (CORRIGÉ: player_id)
CREATE INDEX IF NOT EXISTS idx_attempts_game_id ON game_attempts(game_id);
CREATE INDEX IF NOT EXISTS idx_attempts_player_id ON game_attempts(player_id);
CREATE INDEX IF NOT EXISTS idx_attempts_created_at ON game_attempts(created_at);
CREATE INDEX IF NOT EXISTS idx_attempts_correct ON game_attempts(is_correct);
CREATE INDEX IF NOT EXISTS idx_attempts_attempt_number ON game_attempts(attempt_number);

-- Index composites Attempts (CORRIGÉ: player_id)
CREATE INDEX IF NOT EXISTS idx_attempts_game_player ON game_attempts(game_id, player_id);
CREATE INDEX IF NOT EXISTS idx_attempts_game_number ON game_attempts(game_id, attempt_number);

-- === INDEX MULTIPLAYER ===

-- Index sur les parties multijoueur actives
CREATE INDEX IF NOT EXISTS idx_multiplayer_games_active
ON multiplayer_games(game_type, created_at)
WHERE current_mastermind <= total_masterminds;

-- Index sur les masterminds actifs
CREATE INDEX IF NOT EXISTS idx_game_masterminds_active
ON game_masterminds(multiplayer_game_id, is_active, mastermind_number)
WHERE is_active = true;

-- Index sur la progression des joueurs
CREATE INDEX IF NOT EXISTS idx_player_progress_active
ON player_progress(multiplayer_game_id, status, current_mastermind)
WHERE is_finished = false;

-- Index sur les tentatives récentes
CREATE INDEX IF NOT EXISTS idx_mastermind_attempts_recent
ON player_mastermind_attempts(mastermind_id, created_at, attempt_number);

-- Index sur les objets de jeu
CREATE INDEX IF NOT EXISTS idx_game_items_type ON game_items(item_type);
CREATE INDEX IF NOT EXISTS idx_game_items_rarity ON game_items(rarity);
CREATE INDEX IF NOT EXISTS idx_game_items_active ON game_items(is_active) WHERE is_active = true;

-- Index sur le classement
CREATE INDEX IF NOT EXISTS idx_player_leaderboard_position ON player_leaderboard(final_position);
CREATE INDEX IF NOT EXISTS idx_player_leaderboard_score ON player_leaderboard(final_score DESC);

-- Index WebSocket Sessions
CREATE INDEX IF NOT EXISTS idx_websocket_user_id ON websocket_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_websocket_game_id ON websocket_sessions(game_id);
CREATE INDEX IF NOT EXISTS idx_websocket_status ON websocket_sessions(status);
CREATE INDEX IF NOT EXISTS idx_websocket_connected_at ON websocket_sessions(connected_at);
CREATE INDEX IF NOT EXISTS idx_websocket_session_id ON websocket_sessions(session_id);

-- Index Audit Log
CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_log(created_at);

-- Index JSON (GIN) pour requêtes complexes
CREATE INDEX IF NOT EXISTS idx_users_preferences_gin ON users USING GIN (preferences);
CREATE INDEX IF NOT EXISTS idx_users_settings_gin ON users USING GIN (settings);
CREATE INDEX IF NOT EXISTS idx_games_settings_gin ON games USING GIN (settings);
CREATE INDEX IF NOT EXISTS idx_games_quantum_data_gin ON games USING GIN (quantum_data) WHERE quantum_data IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_attempts_quantum_data_gin ON game_attempts USING GIN (quantum_data) WHERE quantum_data IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_websocket_session_data_gin ON websocket_sessions USING GIN (session_data);
CREATE INDEX IF NOT EXISTS idx_audit_client_info_gin ON audit_log USING GIN (client_info);
CREATE INDEX IF NOT EXISTS idx_mastermind_attempts_quantum_gin ON player_mastermind_attempts USING GIN (quantum_probabilities) WHERE quantum_probabilities IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_player_progress_collected_items_gin ON player_progress USING GIN (collected_items);
CREATE INDEX IF NOT EXISTS idx_player_progress_used_items_gin ON player_progress USING GIN (used_items);

-- =====================================================
-- CONTRAINTES DE RÉFÉRENCE SUPPLÉMENTAIRES
-- =====================================================

-- Contraintes pour game_participations (CORRIGÉ: player_id)
ALTER TABLE game_participations
ADD CONSTRAINT fk_participations_game
FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE;

ALTER TABLE game_participations
ADD CONSTRAINT fk_participations_player
FOREIGN KEY (player_id) REFERENCES users(id) ON DELETE CASCADE;

-- Contraintes pour game_attempts (CORRIGÉ: player_id)
ALTER TABLE game_attempts
ADD CONSTRAINT fk_attempts_game
FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE;

ALTER TABLE game_attempts
ADD CONSTRAINT fk_attempts_player
FOREIGN KEY (player_id) REFERENCES users(id) ON DELETE CASCADE;

-- =====================================================
-- VUES UTILITAIRES POUR STATISTIQUES
-- =====================================================

-- Vue des statistiques des joueurs
CREATE OR REPLACE VIEW player_stats AS
SELECT
    u.id,
    u.username,
    u.total_games,
    u.games_won,
    CASE
        WHEN u.total_games > 0 THEN ROUND(u.games_won::NUMERIC / u.total_games * 100, 2)
        ELSE 0
    END as win_rate_percentage,
    u.total_score,
    u.best_score,
    u.quantum_points,
    u.rank,
    u.created_at,
    u.last_login
FROM users u
WHERE u.is_active = true;

-- Vue des parties actives (CORRIGÉ: player_id)
CREATE OR REPLACE VIEW active_games AS
SELECT
    g.id,
    g.room_code,
    g.game_type,
    g.game_mode,
    g.status,
    g.difficulty,
    COUNT(gp.id) as current_players,
    g.max_players,
    creator.username as creator_username,
    g.created_at,
    g.started_at
FROM games g
LEFT JOIN game_participations gp ON g.id = gp.game_id
    AND gp.status IN ('waiting', 'ready', 'active')
LEFT JOIN users creator ON g.creator_id = creator.id
WHERE g.status IN ('waiting', 'starting', 'active')
GROUP BY g.id, creator.username;

-- Vue du leaderboard global
CREATE OR REPLACE VIEW leaderboard AS
SELECT
    ROW_NUMBER() OVER (ORDER BY u.total_score DESC, u.games_won DESC, u.total_games ASC) as position,
    u.id,
    u.username,
    u.total_games,
    u.games_won,
    u.total_score,
    u.quantum_points,
    u.rank
FROM users u
WHERE u.is_active = true AND u.total_games > 0
ORDER BY u.total_score DESC, u.games_won DESC, u.total_games ASC;

-- Vue des parties multijoueur actives
CREATE OR REPLACE VIEW active_multiplayer_games AS
SELECT
    g.id,
    g.room_code,
    mg.game_type as multiplayer_type,
    g.difficulty,
    g.status,
    mg.current_mastermind,
    mg.total_masterminds,
    COUNT(pp.id) as current_players,
    g.max_players,
    g.quantum_enabled,
    mg.items_enabled,
    creator.username as creator_username,
    g.created_at,
    g.started_at
FROM games g
JOIN multiplayer_games mg ON g.id = mg.base_game_id
LEFT JOIN player_progress pp ON mg.id = pp.multiplayer_game_id AND pp.is_finished = false
LEFT JOIN users creator ON g.creator_id = creator.id
WHERE g.status IN ('waiting', 'starting', 'active')
GROUP BY g.id, mg.id, creator.username;

-- =====================================================
-- FONCTIONS UTILITAIRES
-- =====================================================

-- Fonction pour mettre à jour le timestamp updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers pour updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_games_updated_at BEFORE UPDATE ON games
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_game_participations_updated_at BEFORE UPDATE ON game_participations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_game_attempts_updated_at BEFORE UPDATE ON game_attempts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_multiplayer_games_updated_at BEFORE UPDATE ON multiplayer_games
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_player_progress_updated_at BEFORE UPDATE ON player_progress
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- DONNÉES INITIALES
-- =====================================================

-- Utilisateurs de test avec mots de passe hachés (password123)
-- Hash bcrypt pour "password123": $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewHZLgHkWh0xLHbG
INSERT INTO users (id, username, email, hashed_password, full_name, is_active, is_verified, total_games, games_won, total_score, quantum_points, rank)
VALUES
    (gen_random_uuid(), 'admin', 'admin@quantummastermind.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewHZLgHkWh0xLHbG', 'Administrateur Quantum', true, true, 0, 0, 0, 0, 'Master'),
    (gen_random_uuid(), 'alice_quantum', 'alice@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewHZLgHkWh0xLHbG', 'Alice Quantum', true, true, 15, 8, 2450, 125, 'Gold'),
    (gen_random_uuid(), 'bob_mastermind', 'bob@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewHZLgHkWh0xLHbG', 'Bob Mastermind', true, true, 22, 12, 3780, 89, 'Silver'),
    (gen_random_uuid(), 'charlie_dev', 'charlie@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewHZLgHkWh0xLHbG', 'Charlie Developer', true, false, 5, 2, 890, 34, 'Bronze')
ON CONFLICT (username) DO NOTHING;

-- Insérer les objets de base
INSERT INTO game_items (name, description, item_type, rarity, is_self_target, duration_seconds, effect_value) VALUES
-- Bonus pour soi
('Indice Supplémentaire', 'Révèle un élément de la solution', 'extra_hint', 'common', true, NULL, 1),
('Temps Bonus', 'Ajoute 30 secondes au timer', 'time_bonus', 'rare', true, NULL, 30),
('Passe-Mastermind', 'Passe automatiquement au mastermind suivant', 'skip_mastermind', 'epic', true, NULL, 1),
('Score Double', 'Double le score du prochain mastermind réussi', 'double_score', 'legendary', true, NULL, 2),

-- Malus pour les adversaires
('Gel Temporel', 'Gèle les adversaires pendant 15 secondes', 'freeze_time', 'rare', false, 15, NULL),
('Mastermind Supplémentaire', 'Ajoute un mastermind à tous les adversaires', 'add_mastermind', 'epic', false, NULL, 1),
('Tentatives Réduites', 'Réduit les tentatives des adversaires de 2', 'reduce_attempts', 'epic', false, NULL, 2),
('Couleurs Mélangées', 'Mélange l affichage des couleurs des adversaires', 'scramble_colors', 'legendary', false, 10, NULL)

ON CONFLICT DO NOTHING;

-- =====================================================
-- NOTIFICATIONS DE FIN D'INSTALLATION
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '🎯⚛️ === QUANTUM MASTERMIND DATABASE FIXED === ⚛️🎯';
    RAISE NOTICE '';
    RAISE NOTICE '🔧 CORRECTIONS APPORTÉES:';
    RAISE NOTICE '   • game_participations: utilise player_id (pas user_id)';
    RAISE NOTICE '   • game_attempts: utilise player_id (pas user_id)';
    RAISE NOTICE '   • multiplayer_games: ajout is_final_mastermind, items_per_mastermind, started_at, finished_at';
    RAISE NOTICE '   • player_progress: ajout collected_items, used_items, created_at, updated_at';
    RAISE NOTICE '   • game_participations: ajout is_creator, is_spectator';
    RAISE NOTICE '';
    RAISE NOTICE '📊 Tables créées (COMPATIBLES AVEC LES MODÈLES PYTHON):';
    RAISE NOTICE '   • users (avec hashed_password)';
    RAISE NOTICE '   • games (avec solution JSONB)';
    RAISE NOTICE '   • game_participations (player_id + flags créateur/spectateur)';
    RAISE NOTICE '   • game_attempts (player_id + données quantiques)';
    RAISE NOTICE '   • multiplayer_games (toutes colonnes modèle Python)';
    RAISE NOTICE '   • game_masterminds (masterminds individuels)';
    RAISE NOTICE '   • player_progress (progression + objets JSONB)';
    RAISE NOTICE '   • player_mastermind_attempts (tentatives par mastermind)';
    RAISE NOTICE '   • game_items (objets bonus/malus)';
    RAISE NOTICE '   • player_leaderboard (classements)';
    RAISE NOTICE '   • websocket_sessions (temps réel)';
    RAISE NOTICE '   • audit_log (traçabilité)';
    RAISE NOTICE '';
    RAISE NOTICE '🔍 Index optimisés: Standard + GIN pour JSONB + Multiplayer';
    RAISE NOTICE '⚛️ Support quantique: quantum_data, quantum_hints';
    RAISE NOTICE '🎯 Support multijoueur: Parties multi-masterminds complètes';
    RAISE NOTICE '🛡️ Sécurité: Audit complet + contraintes strictes';
    RAISE NOTICE '👥 4 utilisateurs de test créés (password: password123)';
    RAISE NOTICE '🎮 8 objets de jeu initialisés';
    RAISE NOTICE '📈 Vues: player_stats, active_games, leaderboard, active_multiplayer_games';
    RAISE NOTICE '';
    RAISE NOTICE '✅ SCHÉMA COMPATIBLE AVEC LES MODÈLES PYTHON EXISTANTS';
    RAISE NOTICE '🚀 Solo + Multiplayer devraient maintenant fonctionner!';
    RAISE NOTICE '';
END $$;