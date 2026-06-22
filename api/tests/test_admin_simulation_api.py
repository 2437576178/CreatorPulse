"""Tests for the admin simulation monitoring API."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app  # noqa: E402
from repository import clear_repository_cache  # noqa: E402


class AdminSimulationAPITest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["CREATORPULSE_DATA_SOURCE"] = "mysql"
        clear_repository_cache()
        self.client = create_app().test_client()

    def tearDown(self) -> None:
        os.environ.pop("CREATORPULSE_DATA_SOURCE", None)
        clear_repository_cache()

    def test_status_returns_pipeline_summary(self) -> None:
        response = self.client.get("/api/admin/simulation/status")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual(payload["dataSource"], "mysql")
        self.assertIn("creatorCount", payload)
        self.assertIn("boundPlatformCount", payload)
        self.assertIn("latestSparkBatch", payload)
        self.assertIn("latestWriteAt", payload)

    def test_creators_returns_platform_bindings_and_recent_batches(self) -> None:
        response = self.client.get("/api/admin/simulation/creators")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        creators = response.get_json()["creators"]
        self.assertTrue(creators)
        first = creators[0]
        self.assertIn("creatorId", first)
        self.assertIn("displayName", first)
        self.assertIn("platforms", first)
        self.assertIn("latestWriteAt", first)

    def test_events_returns_recent_spark_rows(self) -> None:
        response = self.client.get("/api/admin/simulation/events")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertIn("events", payload)
        if payload["events"]:
            event = payload["events"][0]
            self.assertIn("runId", event)
            self.assertIn("creatorId", event)
            self.assertIn("platform", event)
            self.assertIn("newFollowers", event)

    def test_offline_status_returns_batch_and_report_summary(self) -> None:
        response = self.client.get("/api/admin/offline/status")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual(payload["dataSource"], "mysql")
        self.assertIn("rawEventCount", payload)
        self.assertIn("creatorDailyCount", payload)
        self.assertIn("reportCount", payload)
        self.assertIn("pendingRecomputeCount", payload)
        self.assertIn("recentRuns", payload)
        self.assertIn("recentReports", payload)

    def test_offline_recompute_creates_pending_request(self) -> None:
        response = self.client.post(
            "/api/admin/offline/recompute",
            json={
                "creatorId": "creator_001",
                "periodStart": "2026-06-14",
                "periodEnd": "2026-06-14",
                "recomputeScope": "ALL",
                "requestedBy": "test",
            },
        )

        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertTrue(payload["requestId"].startswith("recompute_"))
        self.assertEqual(payload["creatorId"], "creator_001")
        self.assertEqual(payload["status"], "PENDING")
        self.assertEqual(payload["recomputeScope"], "ALL")


if __name__ == "__main__":
    unittest.main()
