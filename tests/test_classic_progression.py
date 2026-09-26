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
    def test_fifty_unique_levels_have_valid_tiers_and_passages(self):
        with tempfile.TemporaryDirectory() as folder:
            database_path = Path(folder) / "typequest.sqlite3"
            initialize_database(database_path)
            levels = list_classic_levels(database_path)
        self.assertEqual([level["id"] for level in levels], list(range(1, 51)))
        self.assertEqual(len({level["passage"] for level in levels}), 50)
        self.assertEqual(len({level["title"] for level in levels}), 50)

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
        for previous_last, required, block_index in (
            (10, 23, 1), (20, 45, 2), (30, 68, 3), (40, 90, 4)
        ):
            with self.subTest(required=required):
                below = get_classic_block_statuses(
                    progress_with_stars(required - 1, previous_last)
                )[block_index]
                at = get_classic_block_statuses(
                    progress_with_stars(required, previous_last)
                )[block_index]
                self.assertEqual(below["current_stars"], required - 1)
                self.assertFalse(below["unlocked"])
                self.assertEqual(at["current_stars"], required)
                self.assertTrue(at["unlocked"])

    def test_first_block_always_unlocked_and_speed_does_not_gate(self):
        self.assertTrue(get_classic_block_statuses([])[0]["unlocked"])
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
        self.assertIn(b"Level 50: The Final Route Check", selection.data)
        self.assertIn(b"0 / 23", selection.data)
        self.assertNotIn(b'href="/play/classic/11"', selection.data)
        locked = self.client.get("/play/classic/11")
        self.assertEqual(locked.status_code, 403)
        self.assertNotIn(
            get_classic_level(typequest.DATABASE_PATH, 11)["passage"].encode(),
            locked.data,
        )
        self.assertEqual(self.client.get("/play/classic/51").status_code, 404)

    def test_route_enforces_each_exact_boundary(self):
        for previous_last, required, first_locked_level in (
            (10, 23, 11), (20, 45, 21), (30, 68, 31), (40, 90, 41)
        ):
            with self.subTest(required=required):
                below_profile = create_profile(
                    typequest.DATABASE_PATH, f"Below {required}"
                )
                self.seed_progress(below_profile, required - 1, previous_last)
                self.assertEqual(
                    self.client.get(f"/play/classic/{first_locked_level}").status_code,
                    403,
                )
                at_profile = create_profile(typequest.DATABASE_PATH, f"At {required}")
                self.seed_progress(at_profile, required, previous_last)
                self.assertEqual(
                    self.client.get(f"/play/classic/{first_locked_level}").status_code,
                    200,
                )

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

    def test_all_fifty_routes_when_unlocked_and_progress_total(self):
        profile_id = create_profile(typequest.DATABASE_PATH, "All tiers")
        self.seed_progress(profile_id, 120, 40)
        for level_id in range(1, 51):
            with self.subTest(level_id=level_id):
                self.assertEqual(
                    self.client.get(f"/play/classic/{level_id}").status_code, 200
                )
        self.assertIn(b"40 of 50", self.client.get("/progress").data)

    def test_existing_level_progress_still_loads(self):
        profile_id = create_profile(typequest.DATABASE_PATH, "Week one")
        self.seed_progress(profile_id, 3, 1)
        selection = self.client.get("/play/classic")
        self.assertIn(b"Level 1: The Workshop Bell", selection.data)
        self.assertIn(b"Best: 3 stars", selection.data)
        self.assertIn(b"3 / 23", selection.data)
        self.assertIn(b"1 of 50", self.client.get("/progress").data)


if __name__ == "__main__":
    unittest.main()
