CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Global role and account status enums (NFREQ4, FREQ34, FREQ36, FREQ37)
CREATE TYPE global_role AS ENUM ('USER', 'ADMIN');
CREATE TYPE account_status AS ENUM ('PENDING_VERIFICATION', 'ACTIVE', 'SUSPENDED', 'REMOVED');
CREATE TYPE roster_request_status AS ENUM ('PENDING', 'APPROVED', 'DENIED', 'LEFT');

-- Users Table (FREQ1, FREQ4, FREQ6, FREQ8, FREQ36, FREQ37, FREQ42)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verification_token VARCHAR(255),
    role global_role NOT NULL DEFAULT 'USER',
    status account_status NOT NULL DEFAULT 'PENDING_VERIFICATION',
    discord_id VARCHAR(100) UNIQUE,
    discord_username VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Games / Game Communities Table (Use Cases 2, 3, 11)
CREATE TABLE games (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(150) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    stat_formula_type VARCHAR(50) NOT NULL DEFAULT 'FPS_TAC', -- e.g. FPS_TAC, MOBA, SPORTS
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Community Memberships (User -> Community Member for a specific game)
CREATE TABLE community_memberships (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, game_id)
);

-- Scoped Game Manager Assignments (FREQ32, FREQ33, UC-7, UC-9)
CREATE TABLE game_managers (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    assigned_by UUID REFERENCES users(id) ON DELETE SET NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, game_id)
);

-- Teams Table (FREQ26, FREQ27, FREQ28, FREQ44, UC-7)
CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    name VARCHAR(150) NOT NULL,
    max_capacity INT NOT NULL DEFAULT 10,
    is_shell BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (game_id, name)
);

-- Team Roster Memberships (Community Member promoted to Player on Team: FREQ7, FREQ20, FREQ22, UC-6)
CREATE TABLE team_rosters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status roster_request_status NOT NULL DEFAULT 'PENDING',
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (team_id, user_id)
);

-- Events Table (FREQ11, FREQ12, FREQ13, FREQ15, FREQ19, UC-4)
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_id UUID REFERENCES games(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    location VARCHAR(255) NOT NULL,
    event_date DATE NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT valid_event_time CHECK (end_time > start_time)
);

-- Game Schedules Table (FREQ16, FREQ17, FREQ18, FREQ38, FREQ40, UC-5)
CREATE TABLE game_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    team_id UUID REFERENCES teams(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    visibility VARCHAR(20) NOT NULL DEFAULT 'PUBLIC', -- PUBLIC or ROSTER_ONLY
    external_calendar_event_id VARCHAR(255),
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT valid_schedule_time CHECK (end_time > start_time)
);

-- Team VODs Table (FREQ29, FREQ45, UC-8, UC-13)
CREATE TABLE team_vods (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    file_url TEXT NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Team Statistics & Manager Analysis Comments (FREQ30, FREQ31, FREQ43, FREQ46, UC-8, UC-13)
CREATE TABLE team_statistics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    match_label VARCHAR(255) NOT NULL,
    raw_input_data JSONB NOT NULL,
    calculated_metrics JSONB NOT NULL,
    manager_comments JSONB NOT NULL DEFAULT '[]'::jsonb,
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_start_time ON events(start_time);
CREATE INDEX idx_schedules_game_time ON game_schedules(game_id, start_time, end_time);
CREATE INDEX idx_team_rosters_user_status ON team_rosters(user_id, status);
