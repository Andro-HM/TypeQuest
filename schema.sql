BEGIN;

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 24),
    name_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    active_profile_id INTEGER REFERENCES profiles(id) ON DELETE SET NULL
);

INSERT OR IGNORE INTO app_settings (id, active_profile_id) VALUES (1, NULL);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    mode TEXT NOT NULL CHECK (mode = 'classic'),
    level_id INTEGER NOT NULL,
    completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    active_elapsed_ms REAL NOT NULL CHECK (active_elapsed_ms > 0),
    retained_characters INTEGER NOT NULL CHECK (retained_characters >= 0),
    correct_positions INTEGER NOT NULL CHECK (correct_positions >= 0),
    opportunity_positions INTEGER NOT NULL CHECK (opportunity_positions >= correct_positions),
    raw_wpm REAL NOT NULL CHECK (raw_wpm >= 0),
    accuracy REAL NOT NULL CHECK (accuracy BETWEEN 0 AND 1),
    net_wpm REAL NOT NULL CHECK (net_wpm >= 0),
    stars_earned INTEGER NOT NULL CHECK (stars_earned BETWEEN 1 AND 3)
);

CREATE INDEX IF NOT EXISTS sessions_profile_recent
ON sessions (profile_id, id DESC);

CREATE TABLE IF NOT EXISTS classic_progress (
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    level_id INTEGER NOT NULL,
    best_stars INTEGER NOT NULL CHECK (best_stars BETWEEN 1 AND 3),
    best_net_wpm REAL NOT NULL CHECK (best_net_wpm >= 0),
    PRIMARY KEY (profile_id, level_id)
);

CREATE TABLE IF NOT EXISTS classic_levels (
    id INTEGER PRIMARY KEY CHECK (id BETWEEN 1 AND 20),
    tier INTEGER NOT NULL CHECK (
        (id BETWEEN 1 AND 10 AND tier = 1)
        OR (id BETWEEN 11 AND 20 AND tier = 2)
    ),
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    passage TEXT NOT NULL CHECK (length(passage) > 0)
);

PRAGMA user_version = 1;
COMMIT;
