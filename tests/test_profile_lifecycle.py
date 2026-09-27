import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import app as typequest
from database import (
    create_profile, delete_profile, get_active_profile, get_connection,
    get_profile, initialize_database, list_profiles, rename_profile,
    select_profile,
)


class ProfileLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.previous_database_path = typequest.DATABASE_PATH
        self.database_path = Path(self.temporary_directory.name) / "typequest.sqlite3"
        typequest.DATABASE_PATH = self.database_path
        initialize_database(self.database_path)
        typequest.app.testing = True
        self.client = typequest.app.test_client()

        self.first = create_profile(self.database_path, "First")
        self.second = create_profile(self.database_path, "Second")
        self.assertTrue(select_profile(self.database_path, self.first))
        with closing(get_connection(self.database_path)) as connection, connection:
            connection.execute(
                """INSERT INTO classic_progress
                   (profile_id, level_id, best_stars, best_net_wpm)
                   VALUES (?, 1, 2, 18)""",
                (self.first,),
            )
            connection.execute(
                """INSERT INTO sessions
                   (profile_id, mode, level_id, active_elapsed_ms,
                    retained_characters, correct_positions,
                    opportunity_positions, raw_wpm, accuracy, net_wpm,
                    stars_earned)
                   VALUES (?, 'classic', 1, 60000, 100, 90, 100, 20, 0.9, 18, 2)""",
                (self.first,),
            )
            connection.execute(
                """INSERT INTO sessions
                   (profile_id, mode, selected_duration_seconds, active_elapsed_ms,
                    retained_characters, correct_positions,
                    opportunity_positions, raw_wpm, accuracy, net_wpm,
                    words_typed)
                   VALUES (?, 'time_attack', 30, 30000, 100, 90, 100,
                           40, 0.9, 36, 20)""",
                (self.first,),
            )
            connection.execute(
                """INSERT INTO sessions
                   (profile_id, mode, active_elapsed_ms, retained_characters,
                    correct_positions, opportunity_positions, raw_wpm,
                    accuracy, net_wpm)
                   VALUES (?, 'survival', 22600, 0, 0, 36, 0, 0, 0)""",
                (self.first,),
            )

    def tearDown(self):
        typequest.DATABASE_PATH = self.previous_database_path
        self.temporary_directory.cleanup()

    def database_counts(self):
        with closing(get_connection(self.database_path)) as connection:
            return {
                "modes": [row[0] for row in connection.execute(
                    "SELECT mode FROM sessions WHERE profile_id = ? ORDER BY id",
                    (self.first,),
                )],
                "progress": connection.execute(
                    "SELECT COUNT(*) FROM classic_progress WHERE profile_id = ?",
                    (self.first,),
                ).fetchone()[0],
                "levels": connection.execute(
                    "SELECT COUNT(*) FROM classic_levels"
                ).fetchone()[0],
                "chunks": connection.execute(
                    "SELECT COUNT(*) FROM continuous_chunks"
                ).fetchone()[0],
            }

    def test_rename_preserves_id_active_state_progress_and_all_sessions(self):
        before = self.database_counts()
        response = self.client.post(
            f"/profiles/{self.first}/rename", data={"name": "  Renamed  "}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("notice=renamed", response.headers["Location"])
        self.assertEqual(get_profile(self.database_path, self.first)["name"], "Renamed")
        self.assertEqual(get_active_profile(self.database_path)["id"], self.first)
        self.assertEqual(self.database_counts(), before)
        page = self.client.get(response.headers["Location"]).data
        self.assertIn(b"Profile renamed.", page)
        self.assertIn(b"Active profile: <strong>Renamed</strong>", page)

    def test_same_effective_name_and_case_change_are_allowed(self):
        self.assertTrue(rename_profile(self.database_path, self.first, " First "))
        self.assertTrue(rename_profile(self.database_path, self.first, "FIRST"))
        with closing(get_connection(self.database_path)) as connection:
            name, key = connection.execute(
                "SELECT name, name_key FROM profiles WHERE id = ?", (self.first,)
            ).fetchone()
        self.assertEqual((name, key), ("FIRST", "first"))

    def test_invalid_duplicate_and_unknown_rename(self):
        for name in ("", "   ", "x" * 25, "SECOND"):
            with self.subTest(name=name):
                response = self.client.post(
                    f"/profiles/{self.first}/rename", data={"name": name}
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(b'role="alert"', response.data)
                self.assertEqual(get_profile(self.database_path, self.first)["name"], "First")
        self.assertEqual(self.client.post(
            "/profiles/999/rename", data={"name": "Nobody"}
        ).status_code, 404)

    def test_unicode_casefold_duplicate_is_rejected(self):
        third = create_profile(self.database_path, "Straße")
        self.assertTrue(select_profile(self.database_path, self.first))
        with self.assertRaises(sqlite3.IntegrityError):
            rename_profile(self.database_path, self.first, "STRASSE")
        self.assertEqual(get_profile(self.database_path, third)["name"], "Straße")

    def test_delete_active_cascades_all_modes_and_progress_only(self):
        confirmation = self.client.get(f"/profiles/{self.first}/delete")
        self.assertEqual(confirmation.status_code, 200)
        self.assertIn(b"Yes, delete profile", confirmation.data)
        self.assertIn(b"cannot be undone", confirmation.data)
        unconfirmed = self.client.post(f"/profiles/{self.first}/delete")
        self.assertEqual(unconfirmed.status_code, 400)
        self.assertIsNotNone(get_profile(self.database_path, self.first))

        deleted = self.client.post(
            f"/profiles/{self.first}/delete", data={"confirm_delete": "yes"}
        )
        self.assertEqual(deleted.status_code, 302)
        self.assertIsNone(get_profile(self.database_path, self.first))
        self.assertIsNone(get_active_profile(self.database_path))
        counts = self.database_counts()
        self.assertEqual(counts["modes"], [])
        self.assertEqual(counts["progress"], 0)
        self.assertEqual((counts["levels"], counts["chunks"]), (50, 100))
        with closing(get_connection(self.database_path)) as connection:
            setting = connection.execute(
                "SELECT active_profile_id FROM app_settings WHERE id = 1"
            ).fetchone()
        self.assertIsNotNone(setting)
        self.assertIsNone(setting["active_profile_id"])
        self.assertIsNotNone(get_profile(self.database_path, self.second))
        self.assertIn(b"Profile deleted.", self.client.get(deleted.headers["Location"]).data)
        self.assertIn(b"Choose a profile to see progress", self.client.get("/progress").data)

    def test_delete_inactive_empty_profile_keeps_active_and_unknown_is_404(self):
        self.assertTrue(delete_profile(self.database_path, self.second))
        self.assertIsNone(get_profile(self.database_path, self.second))
        self.assertEqual(get_active_profile(self.database_path)["id"], self.first)
        self.assertEqual(self.client.get("/profiles/999/delete").status_code, 404)
        self.assertEqual(self.client.post(
            "/profiles/999/delete", data={"confirm_delete": "yes"}
        ).status_code, 404)

    def test_profile_cards_and_existing_create_select_flow(self):
        page = self.client.get("/profiles").data
        self.assertIn(f'/profiles/{self.first}/rename'.encode(), page)
        self.assertIn(f'/profiles/{self.first}/delete'.encode(), page)
        self.assertIn(b"Rename", page)
        self.assertIn(b"Select profile", page)
        self.assertIn(b"Active profile", page)
        created = self.client.post("/profiles/create", data={"name": "New player"})
        self.assertEqual(created.status_code, 302)
        self.assertEqual(get_active_profile(self.database_path)["name"], "New player")
        selected = self.client.post(
            "/profiles/select", data={"profile_id": str(self.second)}
        )
        self.assertEqual(selected.status_code, 302)
        self.assertEqual(get_active_profile(self.database_path)["id"], self.second)
        self.assertEqual(len(list_profiles(self.database_path)), 3)


if __name__ == "__main__":
    unittest.main()
