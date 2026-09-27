import sqlite3
import tempfile
import unittest
from pathlib import Path

import app as typequest
from database import (
    create_profile,
    get_classic_level,
    get_connection,
    initialize_database,
    list_classic_levels,
)


class ContentStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "typequest_week1.sqlite3"
        initialize_database(self.database_path)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_fresh_seed_is_classic_only_and_repeatable(self):
        levels = list_classic_levels(self.database_path)
        self.assertEqual([level["id"] for level in levels], list(range(1, 21)))
        initialize_database(self.database_path)
        self.assertEqual(list_classic_levels(self.database_path), levels)

        connection = get_connection(self.database_path)
        try:
            tables = {
                row["name"] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertEqual(tables, {
                "profiles", "app_settings", "sessions",
                "classic_progress", "classic_levels",
            })
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        finally:
            connection.close()

        profile_id = create_profile(self.database_path, "Schema check")
        connection = get_connection(self.database_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO sessions (
                        profile_id, mode, level_id, active_elapsed_ms,
                        retained_characters, correct_positions, opportunity_positions,
                        raw_wpm, accuracy, net_wpm, stars_earned
                    ) VALUES (?, 'time_attack', 1, 1000, 1, 1, 1, 12, 1, 12, 3)
                    """,
                    (profile_id,),
                )
        finally:
            connection.close()

    def test_missing_level_is_restored_without_replacing_existing_content(self):
        original_level = get_classic_level(self.database_path, 20)
        connection = get_connection(self.database_path)
        try:
            with connection:
                connection.execute("DELETE FROM classic_levels WHERE id = 20")
                connection.execute(
                    "UPDATE classic_levels SET title = 'Kept title' WHERE id = 1"
                )
        finally:
            connection.close()

        initialize_database(self.database_path)
        self.assertEqual(get_classic_level(self.database_path, 20), original_level)
        self.assertEqual(get_classic_level(self.database_path, 1)["title"], "Kept title")
        self.assertEqual(len(list_classic_levels(self.database_path)), 20)

    def test_non_week_one_database_version_is_rejected(self):
        connection = get_connection(self.database_path)
        try:
            connection.execute("PRAGMA user_version = 3")
        finally:
            connection.close()
        with self.assertRaisesRegex(RuntimeError, "Unsupported database version: 3"):
            initialize_database(self.database_path)

    def test_classic_route_reads_runtime_content_from_sqlite(self):
        previous_path = typequest.DATABASE_PATH
        typequest.DATABASE_PATH = self.database_path
        typequest.app.testing = True
        try:
            connection = get_connection(self.database_path)
            try:
                with connection:
                    connection.execute(
                        "UPDATE classic_levels SET title = ?, passage = ? WHERE id = 1",
                        ("SQLite title", "SQLite passage."),
                    )
            finally:
                connection.close()

            client = typequest.app.test_client()
            page = client.get("/play/classic/1")
            self.assertEqual(page.status_code, 200)
            self.assertIn(b"SQLite title", page.data)
            self.assertIn(b"SQLite passage.", page.data)
        finally:
            typequest.DATABASE_PATH = previous_path


if __name__ == "__main__":
    unittest.main()
