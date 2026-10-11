
import sqlite3
from pathlib import Path


SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SEED_CONTENT_PATH = Path(__file__).with_name("seed_content.sql")
SCHEMA_VERSION = 1


# Open a SQLite connection with named columns and foreign key enforcement.
def get_connection(database_path):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# Initialize the database tables and populate the Classic levels.
def initialize_database(database_path):
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = get_connection(database_path)
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]

        if version not in (0, SCHEMA_VERSION):
            raise RuntimeError(f"Unsupported database version: {version}")

        # The dedicated Week-1 database uses one idempotent Classic-only schema.
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        connection.executescript(schema)

        seed = SEED_CONTENT_PATH.read_text(encoding="ascii")
        connection.executescript(seed)
    finally:
        connection.close()


# Retrieve all player profiles sorted by name.
def list_profiles(database_path):
    connection = get_connection(database_path)
    try:
        return connection.execute(
            "SELECT id, name, created_at FROM profiles ORDER BY name_key"
        ).fetchall()
    finally:
        connection.close()


# Retrieve all Classic levels in ascending order.
def list_classic_levels(database_path):
    connection = get_connection(database_path)
    try:
        rows = connection.execute(
            "SELECT id, tier, title, passage FROM classic_levels ORDER BY id"
        ).fetchall()

        levels = []
        for row in rows:
            levels.append(dict(row))

        return levels
    finally:
        connection.close()


# Retrieve a specific Classic level using its ID.
def get_classic_level(database_path, level_id):
    connection = get_connection(database_path)
    try:
        row = connection.execute(
            "SELECT id, tier, title, passage FROM classic_levels WHERE id = ?",
            (level_id,),
        ).fetchone()

        if row is None:
            return None

        return dict(row)
    finally:
        connection.close()


# Retrieve the currently selected player profile.
def get_active_profile(database_path):
    connection = get_connection(database_path)
    try:
        return connection.execute(
            """
            SELECT profiles.id, profiles.name, profiles.created_at
            FROM app_settings
            JOIN profiles ON profiles.id = app_settings.active_profile_id
            WHERE app_settings.id = 1
            """
        ).fetchone()
    finally:
        connection.close()


# Create a new player profile and make it the active profile.
def create_profile(database_path, name):
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Enter a profile name.")
    if len(clean_name) > 24:
        raise ValueError("Profile names must be 24 characters or fewer.")

    # SQLite's NOCASE comparison covers ASCII only, so use Python's casefold.
    name_key = clean_name.casefold()
    connection = get_connection(database_path)
    try:
        with connection:
            cursor = connection.execute(
                "INSERT INTO profiles (name, name_key) VALUES (?, ?)",
                (clean_name, name_key),
            )
            connection.execute(
                "UPDATE app_settings SET active_profile_id = ? WHERE id = 1",
                (cursor.lastrowid,),
            )
        return cursor.lastrowid
    finally:
        connection.close()


# Switch the active profile to an existing player.
def select_profile(database_path, profile_id):
    connection = get_connection(database_path)
    try:
        with connection:
            cursor = connection.execute(
                """
                UPDATE app_settings
                SET active_profile_id = ?
                WHERE id = 1
                  AND EXISTS (SELECT 1 FROM profiles WHERE id = ?)
                """,
                (profile_id, profile_id),
            )
        return cursor.rowcount == 1
    finally:
        connection.close()


# Retrieve the best stars and net WPM for each level played by a profile.
def list_classic_progress(database_path, profile_id):
    connection = get_connection(database_path)
    try:
        return connection.execute(
            """
            SELECT level_id, best_stars, best_net_wpm
            FROM classic_progress
            WHERE profile_id = ?
            ORDER BY level_id
            """,
            (profile_id,),
        ).fetchall()
    finally:
        connection.close()


# Calculate completed levels, total best stars, and highest net WPM.
def get_classic_summary(database_path, profile_id):
    connection = get_connection(database_path)
    try:
        return connection.execute(
            """
            SELECT COUNT(*) AS levels_completed,
                   COALESCE(SUM(best_stars), 0) AS total_best_stars,
                   COALESCE(MAX(best_net_wpm), 0) AS best_net_wpm
            FROM classic_progress
            WHERE profile_id = ?
            """,
            (profile_id,),
        ).fetchone()
    finally:
        connection.close()


# Retrieve the 10 most recent Classic sessions for a profile.
def list_recent_classic_sessions(database_path, profile_id):
    connection = get_connection(database_path)
    try:
        return connection.execute(
            """
            SELECT id, level_id, completed_at, active_elapsed_ms,
                   raw_wpm, accuracy, net_wpm, stars_earned
            FROM sessions
            WHERE profile_id = ? AND mode = 'classic'
            ORDER BY id DESC
            LIMIT 10
            """,
            (profile_id,),
        ).fetchall()
    finally:
        connection.close()


# Save a completed session and update its best stars and net WPM.
def save_classic_result(database_path, profile_id, level_id, result):
    connection = get_connection(database_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        with connection:
            active_profile = connection.execute(
                "SELECT active_profile_id FROM app_settings WHERE id = 1"
            ).fetchone()
            if active_profile is None or active_profile["active_profile_id"] != profile_id:
                raise ValueError("The active profile changed. This run was not saved.")

            cursor = connection.execute(
                """
                INSERT INTO sessions (
                    profile_id, mode, level_id, active_elapsed_ms,
                    retained_characters, correct_positions, opportunity_positions,
                    raw_wpm, accuracy, net_wpm, stars_earned
                ) VALUES (?, 'classic', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    level_id,
                    result["active_elapsed_ms"],
                    result["retained_characters"],
                    result["correct_positions"],
                    result["opportunity_positions"],
                    result["raw_wpm"],
                    result["accuracy"],
                    result["net_wpm"],
                    result["stars_earned"],
                ),
            )
            connection.execute(
                """
                INSERT INTO classic_progress (
                    profile_id, level_id, best_stars, best_net_wpm
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(profile_id, level_id) DO UPDATE SET
                    best_stars = MAX(classic_progress.best_stars, excluded.best_stars),
                    best_net_wpm = MAX(classic_progress.best_net_wpm, excluded.best_net_wpm)
                """,
                (profile_id, level_id, result["stars_earned"], result["net_wpm"]),
            )
            progress = connection.execute(
                """
                SELECT best_stars, best_net_wpm
                FROM classic_progress
                WHERE profile_id = ? AND level_id = ?
                """,
                (profile_id, level_id),
            ).fetchone()
        return cursor.lastrowid, progress
    finally:
        connection.close()
