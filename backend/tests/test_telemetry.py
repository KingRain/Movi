"""Telemetry ingestion and tier mapping tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import db as db_module
import telemetry


class TelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        self._orig = db_module.DB_PATH
        db_module.DB_PATH = self.db_path
        db_module.init_db()
        with db_module.connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, salt) VALUES ('tester', 'hash', 'salt')"
            )
            conn.commit()
            self.user_id = int(cur.lastrowid)

    def tearDown(self) -> None:
        db_module.DB_PATH = self._orig
        self.tmp.cleanup()

    def test_hover_below_threshold_stored_as_hover_not_deep(self) -> None:
        telemetry.insert_interactions(
            [{"tmdb_id": 550, "event_type": "hover", "duration_ms": 2000}],
            user_id=None,
            guest_token="guest-test",
        )
        agg = telemetry.aggregate_for_subject(guest_token="guest-test")
        self.assertIn(550, agg)
        self.assertNotIn("r_hover_deep", agg[550]["relations"])

    def test_hover_deep_tier(self) -> None:
        telemetry.insert_interactions(
            [{"tmdb_id": 550, "event_type": "hover", "duration_ms": 3200}],
            user_id=None,
            guest_token="guest-test",
        )
        agg = telemetry.aggregate_for_subject(guest_token="guest-test")
        self.assertIn("r_hover_deep", agg[550]["relations"])

    def test_trailer_complete_tier(self) -> None:
        telemetry.insert_interactions(
            [
                {
                    "tmdb_id": 155,
                    "event_type": "trailer_progress",
                    "duration_ms": 8000,
                    "completion_ratio": 0.62,
                }
            ],
            user_id=None,
            guest_token="guest-test",
        )
        agg = telemetry.aggregate_for_subject(guest_token="guest-test")
        self.assertIn("r_trailer_complete", agg[155]["relations"])

    def test_batch_insert_count(self) -> None:
        n = telemetry.insert_interactions(
            [
                {"tmdb_id": 1, "event_type": "hover", "duration_ms": 4000},
                {"tmdb_id": 2, "event_type": "trailer_complete", "duration_ms": 5000, "completion_ratio": 1.0},
            ],
            user_id=self.user_id,
            guest_token=None,
        )
        self.assertEqual(n, 2)
        with db_module.connect() as conn:
            count = conn.execute("SELECT COUNT(*) AS c FROM user_interactions").fetchone()["c"]
        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
