DROP TABLE IF EXISTS analytics_comments;
DROP TABLE IF EXISTS team_stats;
DROP TABLE IF EXISTS vods;
DROP TABLE IF EXISTS team_members;
DROP TABLE IF EXISTS teams;
DROP TABLE IF EXISTS roster_members;
DROP TABLE IF EXISTS schedules;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS games;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    is_verified INTEGER DEFAULT 0,
    verification_token TEXT,
    discord_username TEXT,
    is_admin INTEGER DEFAULT 0,
    is_game_manager INTEGER DEFAULT 0,
    assigned_game_id INTEGER,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assigned_game_id) REFERENCES games (id)
);

CREATE TABLE games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    location TEXT NOT NULL,
    visibility TEXT DEFAULT 'public',
    game_id INTEGER,
    team_id INTEGER,
    created_by INTEGER,
    FOREIGN KEY (game_id) REFERENCES games (id),
    FOREIGN KEY (team_id) REFERENCES teams (id),
    FOREIGN KEY (created_by) REFERENCES users (id)
);

CREATE TABLE schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    opponent TEXT,
    location TEXT,
    visibility TEXT DEFAULT 'roster',
    external_sync_status TEXT DEFAULT 'synced',
    FOREIGN KEY (game_id) REFERENCES games (id)
);

CREATE TABLE roster_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    game_id INTEGER NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (game_id) REFERENCES games (id),
    UNIQUE(user_id, game_id)
);

CREATE TABLE teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    game_id INTEGER NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games (id)
);

CREATE TABLE team_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (team_id) REFERENCES teams (id),
    UNIQUE(user_id, team_id)
);

CREATE TABLE vods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams (id)
);

CREATE TABLE team_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    match_name TEXT NOT NULL,
    matches_played INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    kills INTEGER DEFAULT 0,
    deaths INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    score REAL DEFAULT 0.0,
    win_rate REAL DEFAULT 0.0,
    kda REAL DEFAULT 0.0,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams (id)
);

CREATE TABLE analytics_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    comment TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stat_id) REFERENCES team_stats (id),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

INSERT INTO games (name, description) VALUES ('League of Legends', 'Tactical 5v5 MOBA');
INSERT INTO games (name, description) VALUES ('Valorant', 'Competitive 5v5 Tactical Shooter');
INSERT INTO games (name, description) VALUES ('Rocket League', 'Vehicular Soccer');
