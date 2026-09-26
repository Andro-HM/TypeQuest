import sqlite3
from pathlib import Path


SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SCHEMA_VERSION = 1


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
