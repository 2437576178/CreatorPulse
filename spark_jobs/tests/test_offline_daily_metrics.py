"""Tests for offline daily metric aggregation."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from kafka_tools.mock_event_builder import build_events  # noqa: E402
from kafka_tools.mock_producer import load_mock  # noqa: E402
from spark_jobs.kafka_events_to_mysql import archive_raw_video_stat_events  # noqa: E402
from spark_jobs.offline_daily_metrics import (  # noqa: E402
    aggregate_daily_metrics,
    build_batch_run,
    filter_raw_events,
)


class OfflineDailyMetricsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_mock()
        cls.events = build_events(cls.data)
        cls.raw_rows = archive_raw_video_stat_events(cls.events)

    def test_filters_raw_events_by_date_and_creator(self) -> None:
        rows = filter_raw_events(self.raw_rows, "2026-06-14", "2026-06-14", "creator_001")

        self.assertEqual(len(rows), 27)
        self.assertTrue(all(row["creator_id"] == "creator_001" for row in rows))
        self.assertTrue(all(row["event_date"] == "2026-06-14" for row in rows))

    def test_builds_batch_run_metadata(self) -> None:
        run = build_batch_run("run_001", "2026-06-14", "2026-06-14", input_count=27, output_count=40)

        self.assertEqual(run["batch_run_id"], "run_001")
        self.assertEqual(run["job_type"], "DAILY_AGGREGATION")
        self.assertEqual(run["status"], "SUCCESS")
        self.assertEqual(run["input_event_count"], 27)
        self.assertEqual(run["output_row_count"], 40)

    def test_aggregates_creator_platform_video_and_content_type_daily_metrics(self) -> None:
        result = aggregate_daily_metrics(
            self.raw_rows,
            self.data["videos"],
            batch_run_id="run_001",
            start_date="2026-06-14",
            end_date="2026-06-14",
        )

        self.assertEqual(len(result["offline_creator_daily_metrics"]), 1)
        self.assertEqual(len(result["offline_platform_daily_metrics"]), 3)
        self.assertEqual(len(result["offline_video_daily_metrics"]), 27)
        self.assertGreaterEqual(len(result["offline_content_type_daily_metrics"]), 1)

        creator_row = result["offline_creator_daily_metrics"][0]
        self.assertEqual(creator_row["creator_id"], "creator_001")
        self.assertEqual(creator_row["metric_date"], "2026-06-14")
        self.assertEqual(creator_row["total_views_delta"], sum(row["play_delta"] for row in self.raw_rows))
        self.assertEqual(creator_row["new_followers_delta"], sum(row["new_follower_delta"] for row in self.raw_rows))
        self.assertEqual(creator_row["lost_followers_delta"], 0)
        self.assertEqual(creator_row["net_followers_delta"], creator_row["new_followers_delta"])
        self.assertGreaterEqual(creator_row["stickiness_score"], 0)
        self.assertLessEqual(creator_row["stickiness_score"], 100)
        self.assertGreaterEqual(creator_row["growth_health_score"], 0)
        self.assertLessEqual(creator_row["growth_health_score"], 100)
        expected_stickiness = min(100, round((creator_row["total_interactions_delta"] / creator_row["total_views_delta"]) * 180, 2))
        expected_health = min(
            100,
            round(
                creator_row["view_to_follower_rate"] * 900
                + (creator_row["new_followers_delta"] / creator_row["profile_visits_delta"]) * 100
                + expected_stickiness * 0.25,
                2,
            ),
        )
        self.assertEqual(creator_row["stickiness_score"], expected_stickiness)
        self.assertEqual(creator_row["growth_health_score"], expected_health)

        platform_views = sum(row["views_delta"] for row in result["offline_platform_daily_metrics"])
        video_views = sum(row["views_delta"] for row in result["offline_video_daily_metrics"])
        content_type_views = sum(row["views_delta"] for row in result["offline_content_type_daily_metrics"])
        self.assertEqual(platform_views, creator_row["total_views_delta"])
        self.assertEqual(video_views, creator_row["total_views_delta"])
        self.assertEqual(content_type_views, creator_row["total_views_delta"])

    def test_cli_dry_run_outputs_planned_rows(self) -> None:
        result = subprocess.run(
            [sys.executable, "spark_jobs/offline_daily_metrics.py"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "dry-run")
        self.assertEqual(payload["counts"]["offline_creator_daily_metrics"], 1)
        self.assertEqual(payload["counts"]["offline_video_daily_metrics"], 27)


if __name__ == "__main__":
    unittest.main()
