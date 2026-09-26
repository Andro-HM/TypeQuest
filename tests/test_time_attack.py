import sqlite3
import tempfile
import unittest
from pathlib import Path

import app as typequest
from database import (
    create_profile,
    get_connection,
    initialize_database,
    list_continuous_chunks,
    select_profile,
)


class TimeAttackContentTests(unittest.TestCase):
    def test_one_hundred_unique_local_chunks(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / "typequest.sqlite3"
            initialize_database(database_path)
            chunks = list_continuous_chunks(database_path)
        self.assertEqual([chunk["id"] for chunk in chunks], list(range(1, 101)))
        self.assertEqual(len({chunk["text"] for chunk in chunks}), 100)
        for chunk in chunks:
            self.assertEqual(chunk["tier"], (chunk["id"] - 1) // 20 + 1)
            self.assertEqual(chunk["text"], " ".join(chunk["text"].split()))
            self.assertTrue(chunk["text"].isascii())


class TimeAttackDatabaseTests(unittest.TestCase):
    def test_v2_migration_preserves_classic_session(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / "old.sqlite3"
            connection = sqlite3.connect(database_path)
            connection.executescript("""
                CREATE TABLE profiles (id INTEGER PRIMARY KEY, name TEXT, name_key TEXT,
                    created_at TEXT);
                CREATE TABLE app_settings (id INTEGER PRIMARY KEY, active_profile_id INTEGER);
                CREATE TABLE sessions (
                    id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL, mode TEXT NOT NULL,
                    level_id INTEGER NOT NULL, completed_at TEXT NOT NULL,
                    active_elapsed_ms REAL NOT NULL, retained_characters INTEGER NOT NULL,
                    correct_positions INTEGER NOT NULL, opportunity_positions INTEGER NOT NULL,
                    raw_wpm REAL NOT NULL, accuracy REAL NOT NULL, net_wpm REAL NOT NULL,
                    stars_earned INTEGER NOT NULL);
                INSERT INTO profiles VALUES (1, 'Old player', 'old player', '2026-01-01');
                INSERT INTO app_settings VALUES (1, 1);
                INSERT INTO sessions VALUES
                    (7, 1, 'classic', 1, '2026-01-02', 60000, 300, 285, 300,
                     60, 0.95, 57, 3);
                PRAGMA user_version = 2;
            """)
            connection.close()

            initialize_database(database_path)
            upgraded = get_connection(database_path)
            try:
                self.assertEqual(upgraded.execute("PRAGMA user_version").fetchone()[0], 3)
                old = upgraded.execute("SELECT * FROM sessions WHERE id = 7").fetchone()
                self.assertEqual((old["profile_id"], old["mode"], old["level_id"]),
                                 (1, "classic", 1))
                self.assertEqual((old["raw_wpm"], old["accuracy"], old["net_wpm"],
                                  old["stars_earned"]), (60, 0.95, 57, 3))
                self.assertIsNone(old["selected_duration_seconds"])
                self.assertIsNone(old["words_typed"])
                self.assertEqual(
                    upgraded.execute("SELECT COUNT(*) FROM classic_levels").fetchone()[0], 50
                )
                self.assertEqual(
                    upgraded.execute("SELECT COUNT(*) FROM continuous_chunks").fetchone()[0], 100
                )
                self.assertEqual(upgraded.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                upgraded.close()


class TimeAttackRouteTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.previous_database_path = typequest.DATABASE_PATH
        typequest.DATABASE_PATH = Path(self.temporary_directory.name) / "typequest.sqlite3"
        initialize_database(typequest.DATABASE_PATH)
        typequest.app.testing = True
        self.client = typequest.app.test_client()
        self.chunk_ids = list(range(1, 101))

    def tearDown(self):
        typequest.DATABASE_PATH = self.previous_database_path
        self.temporary_directory.cleanup()

    def payload(self, profile_id, duration=30, typed="The morning "):
        return {
            "profile_id": profile_id,
            "duration_seconds": duration,
            "chunk_ids": self.chunk_ids,
            "typed_buffer": typed,
        }

    def test_all_duration_options_and_invalid_duration(self):
        selection = self.client.get("/play/time-attack")
        self.assertEqual(selection.status_code, 200)
        profile_id = create_profile(typequest.DATABASE_PATH, "Durations")
        for duration in (30, 60, 120, 180, 300):
            with self.subTest(duration=duration):
                page = self.client.get(f"/play/time-attack?duration={duration}")
                self.assertEqual(page.status_code, 200)
                self.assertIn(f'data-duration-seconds="{duration}"'.encode(), page.data)
                saved = self.client.post(
                    "/api/time-attack/results",
                    json=self.payload(profile_id, duration=duration, typed=""),
                )
                self.assertEqual(saved.status_code, 201)
        self.assertEqual(self.client.get("/play/time-attack?duration=45").status_code, 400)
        connection = get_connection(typequest.DATABASE_PATH)
        try:
            durations = connection.execute(
                "SELECT selected_duration_seconds FROM sessions ORDER BY id"
            ).fetchall()
            self.assertEqual([row[0] for row in durations], [30, 60, 120, 180, 300])
        finally:
            connection.close()

    def test_server_recomputes_metrics_and_excludes_partial_word(self):
        profile_id = create_profile(typequest.DATABASE_PATH, "Timer")
        payload = self.payload(profile_id, typed="The mornXng sun")
        payload.update(raw_wpm=999, accuracy=1, net_wpm=999, words_typed=99)
        response = self.client.post("/api/time-attack/results", json=payload)
        self.assertEqual(response.status_code, 201)

        connection = get_connection(typequest.DATABASE_PATH)
        try:
            saved = connection.execute("SELECT * FROM sessions").fetchone()
            self.assertEqual((saved["mode"], saved["selected_duration_seconds"]),
                             ("time_attack", 30))
            self.assertEqual(saved["active_elapsed_ms"], 30000)
            self.assertEqual(saved["retained_characters"], len(payload["typed_buffer"]))
            self.assertEqual(saved["correct_positions"], len(payload["typed_buffer"]) - 1)
            self.assertEqual(saved["opportunity_positions"], len(payload["typed_buffer"]))
            self.assertEqual(saved["words_typed"], 2)
            self.assertAlmostEqual(saved["raw_wpm"], len(payload["typed_buffer"]) / 2.5)
            self.assertAlmostEqual(saved["accuracy"],
                                   (len(payload["typed_buffer"]) - 1) / len(payload["typed_buffer"]))
            self.assertAlmostEqual(saved["net_wpm"],
                                   saved["raw_wpm"] * saved["accuracy"])
            self.assertIsNone(saved["stars_earned"])
        finally:
            connection.close()
        progress_page = self.client.get("/progress")
        self.assertIn(b"Sessions</dt><dd>1", progress_page.data)
        self.assertIn(b'<th scope="row">30 sec</th>', progress_page.data)
        self.assertIn(b"2 words", progress_page.data)

    def test_empty_run_profile_isolation_and_bad_order(self):
        first = create_profile(typequest.DATABASE_PATH, "First")
        self.assertEqual(self.client.post(
            "/api/time-attack/results", json=self.payload(first, typed="")
        ).status_code, 201)
        second = create_profile(typequest.DATABASE_PATH, "Second")
        self.assertIn(b"Sessions</dt><dd>0", self.client.get("/progress").data)
        self.assertEqual(self.client.post(
            "/api/time-attack/results", json=self.payload(first)
        ).status_code, 409)
        duplicate = self.payload(second)
        duplicate["chunk_ids"][1] = 1
        self.assertEqual(self.client.post(
            "/api/time-attack/results", json=duplicate
        ).status_code, 400)
        self.assertTrue(select_profile(typequest.DATABASE_PATH, first))
        self.assertIn(b"Sessions</dt><dd>1", self.client.get("/progress").data)

    def test_rejects_cross_cycle_repeat_and_invalid_buffer(self):
        profile_id = create_profile(typequest.DATABASE_PATH, "Validation")
        repeated = self.payload(profile_id)
        repeated["chunk_ids"] = self.chunk_ids + list(range(100, 0, -1))
        self.assertEqual(self.client.post(
            "/api/time-attack/results", json=repeated
        ).status_code, 400)
        invalid_buffer = self.payload(profile_id, typed="hello\nworld")
        self.assertEqual(self.client.post(
            "/api/time-attack/results", json=invalid_buffer
        ).status_code, 400)


if __name__ == "__main__":
    unittest.main()
