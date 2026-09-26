BEGIN;

CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
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

CREATE INDEX sessions_profile_recent
ON sessions (profile_id, id DESC);

CREATE TABLE classic_progress (
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    level_id INTEGER NOT NULL,
    best_stars INTEGER NOT NULL CHECK (best_stars BETWEEN 1 AND 3),
    best_net_wpm REAL NOT NULL CHECK (best_net_wpm >= 0),
    PRIMARY KEY (profile_id, level_id)
);

PRAGMA user_version = 2;
COMMIT;
