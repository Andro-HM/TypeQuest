import tempfile
import unittest
from pathlib import Path

import app as typequest
from database import get_classic_level, initialize_database


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
            "/play/classic", "/play/classic/1", "/play/time-attack",
            "/play/time-attack?duration=30", "/play/survival",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"site-nav", response.data)

        levels = self.client.get("/play/classic").data
        self.assertEqual(levels.count(b'class="card level-card'), 50)
        self.assertIn(b'aria-disabled="true"', levels)
        self.assertNotIn(b'href="/play/classic/11"', levels)
        self.assertEqual(self.client.get("/play/classic/11").status_code, 403)
        self.assertIn(b'href="/play/survival"', self.client.get("/play").data)

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


if __name__ == "__main__":
    unittest.main()
