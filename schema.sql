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

PRAGMA user_version = 1;
