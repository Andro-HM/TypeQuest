PRAGMA foreign_keys = OFF;
BEGIN;

CREATE TABLE sessions_new (
    id INTEGER PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    mode TEXT NOT NULL CHECK (mode IN ('classic', 'time_attack', 'survival')),
    level_id INTEGER,
    selected_duration_seconds INTEGER,
    completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    active_elapsed_ms REAL NOT NULL CHECK (active_elapsed_ms > 0),
    retained_characters INTEGER NOT NULL CHECK (retained_characters >= 0),
    correct_positions INTEGER NOT NULL CHECK (correct_positions >= 0),
    opportunity_positions INTEGER NOT NULL CHECK (opportunity_positions >= correct_positions),
    raw_wpm REAL NOT NULL CHECK (raw_wpm >= 0),
    accuracy REAL NOT NULL CHECK (accuracy BETWEEN 0 AND 1),
    net_wpm REAL NOT NULL CHECK (net_wpm >= 0),
    stars_earned INTEGER,
    words_typed INTEGER,
    CHECK (
        (mode = 'classic' AND level_id IS NOT NULL
         AND selected_duration_seconds IS NULL AND words_typed IS NULL
         AND stars_earned BETWEEN 1 AND 3)
        OR
        (mode = 'time_attack' AND level_id IS NULL AND stars_earned IS NULL
         AND selected_duration_seconds IN (30, 60, 120, 180, 300)
         AND words_typed >= 0)
        OR
        (mode = 'survival' AND level_id IS NULL
         AND selected_duration_seconds IS NULL AND stars_earned IS NULL
         AND words_typed IS NULL)
    )
);

INSERT INTO sessions_new (
    id, profile_id, mode, level_id, selected_duration_seconds, completed_at,
    active_elapsed_ms, retained_characters, correct_positions,
    opportunity_positions, raw_wpm, accuracy, net_wpm, stars_earned, words_typed
)
SELECT id, profile_id, mode, level_id, selected_duration_seconds, completed_at,
       active_elapsed_ms, retained_characters, correct_positions,
       opportunity_positions, raw_wpm, accuracy, net_wpm, stars_earned, words_typed
FROM sessions;

DROP TABLE sessions;
ALTER TABLE sessions_new RENAME TO sessions;
CREATE INDEX sessions_profile_recent ON sessions (profile_id, id DESC);

PRAGMA user_version = 4;
COMMIT;
PRAGMA foreign_keys = ON;
