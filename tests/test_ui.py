import tempfile
import unittest
from pathlib import Path

import app as typequest
from database import get_classic_level, get_connection, initialize_database


class BaselineUiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.previous_database_path = typequest.DATABASE_PATH
        typequest.DATABASE_PATH = Path(self.temporary_directory.name) / "typequest.sqlite3"
        initialize_database(typequest.DATABASE_PATH)
        typequest.app.testing = True
        self.client = typequest.app.test_client()

    def tearDown(self):
        typequest.DATABASE_PATH = self.previous_database_path
        self.temporary_directory.cleanup()

    def test_pages_navigation_and_locked_cards(self):
        for path in (
            "/", "/play", "/progress", "/profiles", "/settings",
            "/play/classic", "/play/classic/1",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"site-nav", response.data)

        levels = self.client.get("/play/classic").data
        self.assertEqual(levels.count(b'class="card level-card'), 20)
        self.assertIn(b'aria-disabled="true"', levels)
        for level_id in range(1, 11):
            self.assertIn(f'href="/play/classic/{level_id}"'.encode(), levels)
        for level_id in range(11, 21):
            self.assertNotIn(f'href="/play/classic/{level_id}"'.encode(), levels)
        self.assertEqual(self.client.get("/play/classic/11").status_code, 403)
        self.assertEqual(self.client.get("/play/classic/21").status_code, 404)
        self.assertEqual(self.client.get("/play/time-attack").status_code, 404)
        self.assertEqual(
            self.client.post("/api/time-attack/results", json={}).status_code, 404
        )
        self.assertNotIn(b'href="/play/time-attack"', self.client.get("/play").data)
        self.assertIn(b"Not available yet", self.client.get("/play").data)

    def test_profile_and_classic_result_appear_in_progress_table(self):
        response = self.client.post("/profiles/create", data={"name": "UI Tester"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(b"Active profile", self.client.get("/profiles").data)
        self.client.post("/profiles/create", data={"name": "Second Player"})
        switched = self.client.post("/profiles/select", data={"profile_id": "1"})
        self.assertEqual(switched.status_code, 302)
        self.assertIn(b"Active profile: <strong>UI Tester</strong>",
                      self.client.get("/profiles").data)

        target = get_classic_level(typequest.DATABASE_PATH, 1)["passage"]
        saved = self.client.post("/api/classic/results", json={
            "profile_id": 1,
            "level_id": 1,
            "typed_buffer": target,
            "active_elapsed_ms": 60000,
        })
        self.assertEqual(saved.status_code, 201)
        progress = self.client.get("/progress").data
        self.assertIn(b'<th scope="row">Level 1</th>', progress)
        self.assertIn(b"3 / 3", progress)
        self.assertIn(b"<time datetime=", progress)
        self.assertNotIn(b" UTC:", progress)
        self.assertIn(b"1 of 20", progress)
        self.assertNotIn(b"Recent Time Attack sessions", progress)

    def test_server_recomputes_classic_result_instead_of_trusting_client_metrics(self):
        profile_id = self.client.post(
            "/profiles/create", data={"name": "Verifier"}
        )
        self.assertEqual(profile_id.status_code, 302)
        target = get_classic_level(typequest.DATABASE_PATH, 1)["passage"]
        typed = "x" * len(target)
        saved = self.client.post("/api/classic/results", json={
            "profile_id": 1,
            "level_id": 1,
            "typed_buffer": typed,
            "active_elapsed_ms": 60000,
            "raw_wpm": 999,
            "accuracy": 1,
            "net_wpm": 999,
            "stars_earned": 3,
        })
        self.assertEqual(saved.status_code, 201)
        connection = get_connection(typequest.DATABASE_PATH)
        try:
            session = connection.execute(
                "SELECT * FROM sessions WHERE profile_id = 1"
            ).fetchone()
            self.assertEqual(session["retained_characters"], len(target))
            self.assertEqual(session["correct_positions"], sum(
                character == target[index] for index, character in enumerate(typed)
            ))
            self.assertEqual(session["raw_wpm"], len(target) / 5)
            self.assertEqual(session["accuracy"],
                             session["correct_positions"] / len(target))
            self.assertEqual(session["net_wpm"],
                             session["raw_wpm"] * session["accuracy"])
            self.assertEqual(session["stars_earned"], 1)
        finally:
            connection.close()

    def test_best_stars_and_speed_can_come_from_different_runs(self):
        self.client.post("/profiles/create", data={"name": "Two runs"})
        target = get_classic_level(typequest.DATABASE_PATH, 1)["passage"]
        wrong_count = round(len(target) * 0.07)
        fast_buffer = "@" * wrong_count + target[wrong_count:]
        fast = self.client.post("/api/classic/results", json={
            "profile_id": 1,
            "level_id": 1,
            "typed_buffer": fast_buffer,
            "active_elapsed_ms": 10000,
        })
        self.assertEqual(fast.status_code, 201)
        slow = self.client.post("/api/classic/results", json={
            "profile_id": 1,
            "level_id": 1,
            "typed_buffer": target,
            "active_elapsed_ms": 60000,
        })
        self.assertEqual(slow.status_code, 201)

        connection = get_connection(typequest.DATABASE_PATH)
        try:
            sessions = connection.execute(
                "SELECT stars_earned, net_wpm FROM sessions ORDER BY id"
            ).fetchall()
            self.assertEqual([row["stars_earned"] for row in sessions], [2, 3])
            self.assertGreater(sessions[0]["net_wpm"], sessions[1]["net_wpm"])
            best = connection.execute(
                "SELECT best_stars, best_net_wpm FROM classic_progress"
            ).fetchone()
            self.assertEqual(best["best_stars"], 3)
            self.assertEqual(best["best_net_wpm"], sessions[0]["net_wpm"])
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
