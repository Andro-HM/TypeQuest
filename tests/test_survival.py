import json
import math
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

import app as typequest
from database import (
    create_profile, get_connection, get_survival_summary, initialize_database,
    list_continuous_chunks, list_recent_survival_sessions, select_profile,
)
from survival_rules import (
    recompute_survival_result, scroll_distance_seconds, time_for_distance_seconds,
)


class SurvivalDatabaseTests(unittest.TestCase):
    def test_fresh_schema_is_v4_and_keeps_existing_mode_shapes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fresh.sqlite3"
            initialize_database(path)
            connection = get_connection(path)
            try:
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 4)
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
                with connection:
                    connection.execute(
                        "INSERT INTO profiles (id, name, name_key) VALUES (1, 'A', 'a')"
                    )
                valid_survival = (
                    1, "survival", 1000, 0, 0, 1, 0, 0, 0,
                )
                with connection:
                    connection.execute(
                        """
                        INSERT INTO sessions (
                            profile_id, mode, active_elapsed_ms, retained_characters,
                            correct_positions, opportunity_positions,
                            raw_wpm, accuracy, net_wpm
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        valid_survival,
                    )
                for statement in (
                    """INSERT INTO sessions (
                        profile_id, mode, level_id, active_elapsed_ms,
                        retained_characters, correct_positions, opportunity_positions,
                        raw_wpm, accuracy, net_wpm, stars_earned
                    ) VALUES (1, 'classic', 1, 1000, 1, 1, 1, 12, 1, 12, 4)""",
                    """INSERT INTO sessions (
                        profile_id, mode, selected_duration_seconds, active_elapsed_ms,
                        retained_characters, correct_positions, opportunity_positions,
                        raw_wpm, accuracy, net_wpm, words_typed
                    ) VALUES (1, 'time_attack', 45, 45000, 1, 1, 1, 1, 1, 1, 1)""",
                    """INSERT INTO sessions (
                        profile_id, mode, level_id, active_elapsed_ms,
                        retained_characters, correct_positions, opportunity_positions,
                        raw_wpm, accuracy, net_wpm
                    ) VALUES (1, 'survival', 1, 1000, 1, 1, 1, 12, 1, 12)""",
                ):
                    with self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(statement)
                self.assertEqual(connection.execute(
                    "SELECT COUNT(*) FROM sessions WHERE mode = 'survival'"
                ).fetchone()[0], 1)
            finally:
                connection.close()

    def test_v3_migration_preserves_classic_time_attack_and_content(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "old.sqlite3"
            connection = sqlite3.connect(path)
            try:
                connection.executescript("""
                    CREATE TABLE profiles (
                        id INTEGER PRIMARY KEY, name TEXT, name_key TEXT, created_at TEXT
                    );
                    CREATE TABLE app_settings (
                        id INTEGER PRIMARY KEY, active_profile_id INTEGER
                    );
                    CREATE TABLE sessions (
                        id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL,
                        mode TEXT NOT NULL, level_id INTEGER NOT NULL,
                        completed_at TEXT NOT NULL, active_elapsed_ms REAL NOT NULL,
                        retained_characters INTEGER NOT NULL,
                        correct_positions INTEGER NOT NULL,
                        opportunity_positions INTEGER NOT NULL, raw_wpm REAL NOT NULL,
                        accuracy REAL NOT NULL, net_wpm REAL NOT NULL,
                        stars_earned INTEGER NOT NULL
                    );
                    CREATE TABLE classic_progress (
                        profile_id INTEGER, level_id INTEGER, best_stars INTEGER,
                        best_net_wpm REAL, PRIMARY KEY (profile_id, level_id)
                    );
                    INSERT INTO profiles VALUES (1, 'Old player', 'old player', '2026-01-01');
                    INSERT INTO app_settings VALUES (1, 1);
                    INSERT INTO sessions VALUES
                        (7, 1, 'classic', 1, '2026-01-02', 60000, 300, 285,
                         300, 60, 0.95, 57, 3);
                    INSERT INTO classic_progress VALUES (1, 1, 3, 57);
                    PRAGMA user_version = 2;
                """)
                connection.executescript(
                    Path(__file__).resolve().parents[1]
                    .joinpath("migration_2_to_3.sql").read_text(encoding="utf-8")
                )
                connection.execute(
                    """
                    INSERT INTO sessions (
                        id, profile_id, mode, selected_duration_seconds,
                        completed_at, active_elapsed_ms, retained_characters,
                        correct_positions, opportunity_positions, raw_wpm,
                        accuracy, net_wpm, words_typed
                    ) VALUES (8, 1, 'time_attack', 30, '2026-01-03',
                              30000, 20, 18, 20, 8, 0.9, 7.2, 3)
                    """
                )
                connection.commit()
            finally:
                connection.close()

            initialize_database(path)
            upgraded = get_connection(path)
            try:
                self.assertEqual(upgraded.execute("PRAGMA user_version").fetchone()[0], 4)
                rows = upgraded.execute(
                    "SELECT id, mode, profile_id, active_elapsed_ms FROM sessions ORDER BY id"
                ).fetchall()
                self.assertEqual(
                    [tuple(row) for row in rows],
                    [(7, "classic", 1, 60000), (8, "time_attack", 1, 30000)],
                )
                self.assertEqual(upgraded.execute(
                    "SELECT best_stars FROM classic_progress"
                ).fetchone()[0], 3)
                self.assertEqual(upgraded.execute(
                    "SELECT active_profile_id FROM app_settings"
                ).fetchone()[0], 1)
                self.assertEqual(upgraded.execute(
                    "SELECT COUNT(*) FROM classic_levels"
                ).fetchone()[0], 50)
                self.assertEqual(upgraded.execute(
                    "SELECT COUNT(*) FROM continuous_chunks"
                ).fetchone()[0], 100)
                self.assertEqual(upgraded.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                upgraded.close()


class SurvivalRouteTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.previous_database_path = typequest.DATABASE_PATH
        typequest.DATABASE_PATH = Path(self.temporary_directory.name) / "survival.sqlite3"
        initialize_database(typequest.DATABASE_PATH)
        typequest.app.testing = True
        self.client = typequest.app.test_client()
        self.chunks = list_continuous_chunks(typequest.DATABASE_PATH)
        self.first_target = self.chunks[0]["text"]

    def tearDown(self):
        typequest.DATABASE_PATH = self.previous_database_path
        self.temporary_directory.cleanup()

    def payload(self, profile_id, entries=None, active_buffer="", chunk_ids=None):
        return {
            "profile_id": profile_id,
            "chunk_ids": [1] if chunk_ids is None else chunk_ids,
            "finalized_entries": [None] * 36 if entries is None else entries,
            "active_buffer": active_buffer,
        }

    def test_survival_page_uses_all_sqlite_chunks_and_navigation(self):
        page = self.client.get("/play/survival")
        self.assertEqual(page.status_code, 200)
        match = re.search(
            rb'<script id="survival-chunks" type="application/json">(.*?)</script>',
            page.data,
        )
        self.assertIsNotNone(match)
        embedded = json.loads(match.group(1))
        self.assertEqual(embedded, self.chunks)
        home = self.client.get("/").data
        self.assertIn(b"Survival</h3>", home)
        self.assertNotIn(b'href="/play/survival"', home)
        self.assertIn(b'href="/play/survival"', self.client.get("/play").data)

    def test_no_profile_and_profile_mismatch_are_rejected(self):
        self.assertEqual(self.client.post(
            "/api/survival/results", json=self.payload(1)
        ).status_code, 409)
        first = create_profile(typequest.DATABASE_PATH, "First")
        second = create_profile(typequest.DATABASE_PATH, "Second")
        self.assertEqual(self.client.post(
            "/api/survival/results", json=self.payload(first)
        ).status_code, 409)
        self.assertEqual(self.client.post(
            "/api/survival/results", json=self.payload(second)
        ).status_code, 201)

    def test_invalid_chunks_and_tier_order_are_rejected(self):
        profile_id = create_profile(typequest.DATABASE_PATH, "Chunk check")
        for ids in ([999], [21], [1, 41], [1, 1], list(range(1, 21)) + [20]):
            with self.subTest(ids=ids):
                response = self.client.post(
                    "/api/survival/results",
                    json=self.payload(profile_id, chunk_ids=ids),
                )
                self.assertEqual(response.status_code, 400)

    def test_invalid_entries_short_target_and_non_death_are_rejected(self):
        profile_id = create_profile(typequest.DATABASE_PATH, "History check")
        bad_payloads = (
            self.payload(profile_id, entries=[None] * 35),
            self.payload(profile_id, entries=[None] * 37),
            self.payload(profile_id, entries=[None] * 1000),
            self.payload(profile_id, entries=["ab"] + [None] * 35),
            self.payload(profile_id, active_buffer="\n"),
            self.payload(profile_id, active_buffer="x" * 61),
        )
        for payload in bad_payloads:
            with self.subTest(entries=len(payload["finalized_entries"])):
                self.assertEqual(
                    self.client.post("/api/survival/results", json=payload).status_code,
                    400,
                )

    def test_valid_death_recomputes_metrics_and_ignores_fake_values(self):
        profile_id = create_profile(typequest.DATABASE_PATH, "Survivor")
        active = self.first_target[36:39]
        payload = self.payload(profile_id, active_buffer=active)
        payload.update(raw_wpm=999, accuracy=1, net_wpm=999, half_heart_units=6)
        response = self.client.post("/api/survival/results", json=payload)
        self.assertEqual(response.status_code, 201)
        result = response.get_json()
        expected_ms = time_for_distance_seconds(36) * 1000
        self.assertAlmostEqual(result["active_elapsed_ms"], expected_ms)
        self.assertEqual(result["half_heart_units"], 0)
        self.assertEqual(result["retained_characters"], len(active))
        self.assertEqual(result["opportunity_positions"], 36 + len(active))
        self.assertEqual(result["correct_positions"], len(active))
        self.assertEqual(result["accuracy"], len(active) / (36 + len(active)))
        self.assertAlmostEqual(
            result["raw_wpm"], len(active) / 5 / (expected_ms / 60000)
        )
        self.assertAlmostEqual(
            result["net_wpm"], result["raw_wpm"] * result["accuracy"]
        )
        connection = get_connection(typequest.DATABASE_PATH)
        try:
            saved = connection.execute(
                "SELECT * FROM sessions WHERE id = ?", (result["session_id"],)
            ).fetchone()
            self.assertEqual(saved["mode"], "survival")
            self.assertIsNone(saved["level_id"])
            self.assertIsNone(saved["selected_duration_seconds"])
            self.assertIsNone(saved["stars_earned"])
            self.assertEqual(saved["opportunity_positions"], 39)
            self.assertAlmostEqual(saved["active_elapsed_ms"], expected_ms)
        finally:
            connection.close()

    def test_tier_two_death_uses_later_damage_stage_and_rejects_future_tier(self):
        profile_id = create_profile(typequest.DATABASE_PATH, "Tier check")
        ids = [1, 2, 21]
        target = " ".join(self.chunks[chunk_id - 1]["text"] for chunk_id in ids)
        entries = list(target[:105]) + [None] * 30
        payload = self.payload(profile_id, entries=entries, chunk_ids=ids)
        response = self.client.post("/api/survival/results", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["tier_reached"], 2)
        self.assertAlmostEqual(
            response.get_json()["active_elapsed_ms"],
            time_for_distance_seconds(135) * 1000,
        )
        future = self.payload(profile_id, entries=entries, chunk_ids=[1, 21, 41])
        self.assertEqual(
            self.client.post("/api/survival/results", json=future).status_code, 400
        )

    def test_profile_isolation_progress_and_recent_limit(self):
        first = create_profile(typequest.DATABASE_PATH, "First player")
        for _ in range(12):
            self.assertEqual(self.client.post(
                "/api/survival/results", json=self.payload(first)
            ).status_code, 201)
        self.assertEqual(get_survival_summary(
            typequest.DATABASE_PATH, first
        )["session_count"], 12)
        self.assertEqual(len(list_recent_survival_sessions(
            typequest.DATABASE_PATH, first
        )), 10)
        progress = self.client.get("/progress").data
        self.assertIn(b"Recent Survival sessions", progress)
        self.assertIn(b"12</dd>", progress)

        second = create_profile(typequest.DATABASE_PATH, "Second player")
        self.assertEqual(get_survival_summary(
            typequest.DATABASE_PATH, second
        )["session_count"], 0)
        self.assertIn(b"No Survival runs saved yet.", self.client.get("/progress").data)
        self.assertTrue(select_profile(typequest.DATABASE_PATH, first))
        self.assertIn(b"Recent Survival sessions", self.client.get("/progress").data)

    def test_replay_math_matches_analytic_distance(self):
        self.assertEqual(scroll_distance_seconds(300), 825)
        for distance in (1, 36, 105, 825, 1000):
            self.assertTrue(math.isclose(
                scroll_distance_seconds(time_for_distance_seconds(distance)),
                distance,
                abs_tol=1e-9,
            ))
        result = recompute_survival_result(
            self.chunks, [1], [None] * 36, ""
        )
        self.assertEqual(result["retained_characters"], 0)
        self.assertEqual(result["opportunity_positions"], 36)
        self.assertEqual(result["correct_positions"], 0)


if __name__ == "__main__":
    unittest.main()
