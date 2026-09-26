import sqlite3
from pathlib import Path


SCHEMA_PATH = Path(__file__).with_name("schema.sql")
MIGRATION_PATH = Path(__file__).with_name("migration_1_to_2.sql")
SCHEMA_VERSION = 2


def get_connection(database_path):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path):
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = get_connection(database_path)
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            schema = SCHEMA_PATH.read_text(encoding="utf-8")
            connection.executescript(schema)
        elif version == 1:
            migration = MIGRATION_PATH.read_text(encoding="utf-8")
            connection.executescript(migration)
        elif version != SCHEMA_VERSION:
            raise RuntimeError(f"Unsupported database version: {version}")
    finally:
        connection.close()


def list_profiles(database_path):
    connection = get_connection(database_path)
    try:
        return connection.execute(
            "SELECT id, name, created_at FROM profiles ORDER BY name_key"
        ).fetchall()
    finally:
        connection.close()


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
