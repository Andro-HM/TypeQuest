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
    list_continuous_chunks,
    save_classic_result,
    save_time_attack_result,
)


class ContentStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "typequest.sqlite3"
        initialize_database(self.database_path)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_fresh_seed_is_complete_and_repeatable(self):
        levels = list_classic_levels(self.database_path)
        chunks = list_continuous_chunks(self.database_path)
        self.assertEqual([level["id"] for level in levels], list(range(1, 51)))
        self.assertEqual([chunk["id"] for chunk in chunks], list(range(1, 101)))
        self.assertEqual(
            [sum(chunk["tier"] == tier for chunk in chunks) for tier in range(1, 6)],
            [20, 20, 20, 20, 20],
        )
        initialize_database(self.database_path)
        self.assertEqual(list_classic_levels(self.database_path), levels)
        self.assertEqual(list_continuous_chunks(self.database_path), chunks)

    def test_missing_rows_are_restored_without_replacing_existing_rows(self):
        original_level = get_classic_level(self.database_path, 50)
        original_chunk = list_continuous_chunks(self.database_path)[-1]
        connection = get_connection(self.database_path)
        try:
            with connection:
                connection.execute("DELETE FROM classic_levels WHERE id = 50")
                connection.execute("DELETE FROM continuous_chunks WHERE id = 100")
                connection.execute(
                    "UPDATE classic_levels SET title = 'Kept title' WHERE id = 1"
                )
        finally:
            connection.close()

        initialize_database(self.database_path)
        self.assertEqual(get_classic_level(self.database_path, 50), original_level)
        self.assertEqual(list_continuous_chunks(self.database_path)[-1], original_chunk)
        self.assertEqual(get_classic_level(self.database_path, 1)["title"], "Kept title")

    def test_old_local_v3_receives_tables_without_losing_user_data(self):
        profile_id = create_profile(self.database_path, "Existing")
        classic_result = {
            "active_elapsed_ms": 60000,
            "retained_characters": 300,
            "correct_positions": 285,
            "opportunity_positions": 300,
            "raw_wpm": 60,
            "accuracy": 0.95,
            "net_wpm": 57,
            "stars_earned": 3,
        }
        save_classic_result(self.database_path, profile_id, 1, classic_result)
        time_attack_result = {
            "active_elapsed_ms": 30000,
            "retained_characters": 0,
            "correct_positions": 0,
            "opportunity_positions": 0,
            "raw_wpm": 0,
            "accuracy": 0,
            "net_wpm": 0,
            "words_typed": 0,
        }
        save_time_attack_result(self.database_path, profile_id, 30, time_attack_result)

        connection = get_connection(self.database_path)
        try:
            with connection:
                connection.execute("DROP TABLE classic_levels")
                connection.execute("DROP TABLE continuous_chunks")
            tables = ("profiles", "app_settings", "classic_progress", "sessions")
            before = {
                table: [tuple(row) for row in connection.execute(
                    f"SELECT * FROM {table} ORDER BY rowid"
                )]
                for table in tables
            }
        finally:
            connection.close()

        initialize_database(self.database_path)
        connection = get_connection(self.database_path)
        try:
            for table, expected in before.items():
                self.assertEqual(
                    [tuple(row) for row in connection.execute(
                        f"SELECT * FROM {table} ORDER BY rowid"
                    )], expected,
                )
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 3)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            connection.close()
        self.assertEqual(len(list_classic_levels(self.database_path)), 50)
        self.assertEqual(len(list_continuous_chunks(self.database_path)), 100)

    def test_classic_and_time_attack_routes_read_database_content(self):
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
                    connection.execute(
                        "UPDATE continuous_chunks SET text = ? WHERE id = 1",
                        ("SQLite-only chunk.",),
                    )
            finally:
                connection.close()

            client = typequest.app.test_client()
            classic_page = client.get("/play/classic/1")
            self.assertIn(b"SQLite title", classic_page.data)
            self.assertIn(b"SQLite passage.", classic_page.data)
            time_attack_page = client.get("/play/time-attack?duration=30")
            self.assertIn(b"SQLite-only chunk.", time_attack_page.data)

            profile_id = create_profile(self.database_path, "Reader")
            order = list(range(1, 101))
            response = client.post("/api/time-attack/results", json={
                "profile_id": profile_id,
                "duration_seconds": 30,
                "chunk_ids": order,
                "typed_buffer": "SQLite-only chunk.",
            })
            self.assertEqual(response.status_code, 201)
            connection = get_connection(self.database_path)
            try:
                saved = connection.execute(
                    "SELECT correct_positions FROM sessions WHERE mode = 'time_attack'"
                ).fetchone()
                self.assertEqual(saved["correct_positions"], len("SQLite-only chunk."))
            finally:
                connection.close()
        finally:
            typequest.DATABASE_PATH = previous_path


if __name__ == "__main__":
    unittest.main()
