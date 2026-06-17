"""Tests for Kafka event parsing and aggregate row preparation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from kafka_tools.mock_event_builder import build_events  # noqa: E402
from kafka_tools.mock_producer import load_mock  # noqa: E402
from spark_jobs.kafka_events_to_mysql import (  # noqa: E402
    aggregate_platform_metrics,
    aggregate_video_contributions,
    video_stats_events,
)


class KafkaEventsToMySQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_mock()
        cls.events = build_events(cls.data)

    def test_filters_video_stats_events(self) -> None:
        rows = video_stats_events(self.events)

        self.assertEqual(len(rows), 27)
        self.assertTrue(all(event["event_type"] == "video_stats" for event in rows))

    def test_aggregates_platform_metrics_from_events(self) -> None:
        rows = aggregate_platform_metrics(self.events, "test_run", "2026-06-15T00:00:00")

        self.assertEqual(len(rows), 3)
        self.assertEqual(sum(row["video_count"] for row in rows), 27)
        self.assertEqual(
            sum(row["total_views"] for row in rows),
            sum(item["views"] for item in self.data["videoMetricSnapshots"]),
        )
        self.assertEqual(
            sum(row["new_followers"] for row in rows),
            sum(item["newFollowers"] for item in self.data["videoMetricSnapshots"]),
        )

    def test_aggregates_video_contributions_from_events(self) -> None:
        rows = aggregate_video_contributions(self.events, "test_run", "2026-06-15T00:00:00", limit=5)

        self.assertEqual(len(rows), 5)
        self.assertEqual([row["rank_position"] for row in rows], [1, 2, 3, 4, 5])
        self.assertGreaterEqual(rows[0]["new_followers"], rows[-1]["new_followers"])


if __name__ == "__main__":
    unittest.main()
