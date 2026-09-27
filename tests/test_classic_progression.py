import tempfile
import unittest
from pathlib import Path

import app as typequest
from database import (
    create_profile, get_classic_level, get_connection, initialize_database,
    list_classic_levels, select_profile,
)
from progression import get_classic_block_statuses


def progress_with_stars(total_stars, last_level, speed=10.0):
    rows = []
    remaining = total_stars
    for level_id in range(1, last_level + 1):
        stars = min(3, remaining)
        if stars:
            rows.append({
                "level_id": level_id,
                "best_stars": stars,
                "best_net_wpm": speed,
            })
        remaining -= stars
    return rows


class ClassicContentTests(unittest.TestCase):
    def test_twenty_unique_levels_have_valid_tiers_and_passages(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / "typequest.sqlite3"
            initialize_database(database_path)
            levels = list_classic_levels(database_path)
        self.assertEqual([level["id"] for level in levels], list(range(1, 21)))
        self.assertEqual(len({level["passage"] for level in levels}), 20)
        self.assertEqual(len({level["title"] for level in levels}), 20)

        for level in levels:
            tier = (level["id"] - 1) // 10 + 1
            minimum = 250 if tier == 1 else 100 * tier + 200
            maximum = 400 if tier == 1 else 100 * tier + 300
            self.assertEqual(level["tier"], tier)
            self.assertGreaterEqual(len(level["passage"]), minimum)
            self.assertLessEqual(len(level["passage"]), maximum)
            self.assertTrue(level["passage"].isascii())
            self.assertEqual(level["passage"], " ".join(level["passage"].split()))


class ClassicUnlockTests(unittest.TestCase):
    def test_exact_star_boundaries(self):
        below = get_classic_block_statuses(progress_with_stars(22, 10))[1]
        at = get_classic_block_statuses(progress_with_stars(23, 10))[1]
        self.assertEqual(below["current_stars"], 22)
        self.assertFalse(below["unlocked"])
        self.assertEqual(at["current_stars"], 23)
        self.assertTrue(at["unlocked"])

    def test_first_block_always_unlocked_and_speed_does_not_gate(self):
        blocks = get_classic_block_statuses([])
        self.assertEqual(len(blocks), 2)
        self.assertTrue(blocks[0]["unlocked"])
        self.assertFalse(blocks[1]["unlocked"])
        slow = get_classic_block_statuses(progress_with_stars(23, 10, speed=1.0))
        fast = get_classic_block_statuses(progress_with_stars(23, 10, speed=999.0))
        self.assertEqual(
            [block["unlocked"] for block in slow],
            [block["unlocked"] for block in fast],
        )


class ClassicRouteTests(unittest.TestCase):
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

    def seed_progress(self, profile_id, stars, last_level):
        connection = get_connection(typequest.DATABASE_PATH)
        try:
            with connection:
                connection.executemany(
                    """
                    INSERT INTO classic_progress
                        (profile_id, level_id, best_stars, best_net_wpm)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        (profile_id, row["level_id"], row["best_stars"], row["best_net_wpm"])
                        for row in progress_with_stars(stars, last_level)
                    ),
                )
        finally:
            connection.close()

    def test_no_profile_invalid_id_and_locked_passage(self):
        self.assertEqual(self.client.get("/play/classic/1").status_code, 200)
        selection = self.client.get("/play/classic")
        self.assertEqual(selection.data.count(b'class="card level-card'), 20)
        self.assertIn(b"Level 20", selection.data)
        self.assertNotIn(b"Level 21", selection.data)
        self.assertIn(b"0 / 23", selection.data)
        self.assertNotIn(b'href="/play/classic/11"', selection.data)
        locked = self.client.get("/play/classic/11")
        self.assertEqual(locked.status_code, 403)
        self.assertNotIn(
            get_classic_level(typequest.DATABASE_PATH, 11)["passage"].encode(),
            locked.data,
        )
        self.assertEqual(self.client.get("/play/classic/21").status_code, 404)

    def test_route_enforces_exact_tier_two_boundary(self):
        below_profile = create_profile(typequest.DATABASE_PATH, "Below")
        self.seed_progress(below_profile, 22, 10)
        self.assertEqual(self.client.get("/play/classic/11").status_code, 403)
        at_profile = create_profile(typequest.DATABASE_PATH, "At")
        self.seed_progress(at_profile, 23, 10)
        self.assertEqual(self.client.get("/play/classic/11").status_code, 200)

    def test_profiles_have_separate_unlock_states_and_post_is_guarded(self):
        first_profile = create_profile(typequest.DATABASE_PATH, "First")
        self.seed_progress(first_profile, 23, 10)
        self.assertEqual(self.client.get("/play/classic/11").status_code, 200)

        second_profile = create_profile(typequest.DATABASE_PATH, "Second")
        self.assertEqual(self.client.get("/play/classic/11").status_code, 403)
        response = self.client.post("/api/classic/results", json={
            "level_id": 11,
            "profile_id": second_profile,
            "typed_buffer": get_classic_level(typequest.DATABASE_PATH, 11)["passage"],
            "active_elapsed_ms": 60000,
        })
        self.assertEqual(response.status_code, 403)
        self.assertTrue(select_profile(typequest.DATABASE_PATH, first_profile))
        self.assertEqual(self.client.get("/play/classic/11").status_code, 200)

    def test_all_twenty_routes_when_unlocked_and_progress_total(self):
        profile_id = create_profile(typequest.DATABASE_PATH, "Both tiers")
        self.seed_progress(profile_id, 23, 10)
        for level_id in range(1, 21):
            with self.subTest(level_id=level_id):
                self.assertEqual(
                    self.client.get(f"/play/classic/{level_id}").status_code, 200
                )
        self.assertIn(b"8 of 20", self.client.get("/progress").data)

    def test_existing_level_progress_still_loads(self):
        profile_id = create_profile(typequest.DATABASE_PATH, "Week one")
        self.seed_progress(profile_id, 3, 1)
        selection = self.client.get("/play/classic")
        self.assertIn(b"Level 1", selection.data)
        self.assertIn(b"The Workshop Bell", selection.data)
        self.assertIn(b"Best: 3 stars", selection.data)
        self.assertIn(b"3 / 23", selection.data)
        self.assertIn(b"1 of 20", self.client.get("/progress").data)


if __name__ == "__main__":
    unittest.main()
