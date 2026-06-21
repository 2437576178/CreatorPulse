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
    aggregate_creator_metric_snapshots,
    aggregate_platform_metrics,
    aggregate_video_metric_snapshots,
    aggregate_video_traffic_source_metrics,
    aggregate_video_contributions,
    normalize_source,
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

    def test_aggregates_video_metric_snapshots_from_events(self) -> None:
        rows = aggregate_video_metric_snapshots(self.events, "2026-06-15T00:00:00")

        self.assertEqual(len(rows), 27)
        first_event = video_stats_events(self.events)[0]
        first_row = next(row for row in rows if row["video_id"] == first_event["content_id"])
        self.assertEqual(first_row["creator_id"], first_event["creator_id"])
        self.assertEqual(first_row["platform"], first_event["platform"])
        self.assertEqual(first_row["views"], first_event["stats"]["play_count"])
        self.assertEqual(first_row["likes"], first_event["stats"]["like_count"])
        self.assertEqual(first_row["comments"], first_event["stats"]["comment_count"])
        self.assertEqual(first_row["shares"], first_event["stats"]["share_count"])
        self.assertEqual(first_row["saves"], first_event["stats"]["save_count"])
        self.assertEqual(first_row["profile_visits"], first_event["growth"]["profile_visits"])
        self.assertEqual(first_row["new_followers"], first_event["growth"]["new_followers"])
        self.assertEqual(first_row["conversion_rate"], round(first_event["growth"]["new_followers"] / first_event["stats"]["play_count"], 6))
        self.assertEqual(first_row["collected_at"], "2026-06-15T00:00:00")

    def test_aggregates_video_traffic_source_metrics_from_events(self) -> None:
        rows = aggregate_video_traffic_source_metrics(self.events)
        expected_sources = sum(len(event.get("traffic_source", {})) for event in video_stats_events(self.events))

        self.assertEqual(len(rows), expected_sources)
        first_event = video_stats_events(self.events)[0]
        source_name, source_metrics = next(iter(first_event["traffic_source"].items()))
        normalized_source = normalize_source(source_name)
        source_row = next(row for row in rows if row["video_id"] == first_event["content_id"] and row["source"] == normalized_source)
        self.assertEqual(source_row["views"], source_metrics["views"])
        self.assertEqual(source_row["new_followers"], source_metrics["new_followers"])
        self.assertEqual(source_row["conversion_rate"], source_metrics["conversion_rate"])

    def test_aggregates_creator_metric_snapshots_from_events(self) -> None:
        rows = aggregate_creator_metric_snapshots(self.events, "2026-06-15")

        self.assertEqual(len(rows), 1)
        row = rows[0]
        video_events = video_stats_events(self.events)
        total_views = sum(event["stats"]["play_count"] for event in video_events)
        total_play_delta = sum(event["growth"]["play_growth_5s"] for event in video_events)
        new_followers = sum(event["growth"]["new_followers"] for event in video_events)
        total_interactions = sum(
            event["stats"]["like_count"] + event["stats"]["comment_count"] + event["stats"]["share_count"] + event["stats"]["save_count"]
            for event in video_events
        )
        profile_visits = sum(event["growth"]["profile_visits"] for event in video_events)

        self.assertEqual(row["creator_id"], video_events[0]["creator_id"])
        self.assertEqual(row["metric_date"], "2026-06-15")
        self.assertEqual(row["total_views"], total_views)
        self.assertEqual(row["new_followers"], new_followers)
        self.assertEqual(row["lost_followers"], 0)
        self.assertEqual(row["net_followers"], new_followers)
        self.assertEqual(row["total_interactions"], total_interactions)
        self.assertEqual(row["profile_visits"], profile_visits)
        self.assertEqual(row["view_to_follower_rate"], round(new_followers / total_play_delta, 6))
        self.assertGreater(row["view_to_follower_rate"], round(new_followers / total_views, 6))
        self.assertGreaterEqual(row["stickiness_score"], 0)
        self.assertLessEqual(row["stickiness_score"], 100)
        self.assertGreaterEqual(row["growth_health_score"], 0)
        self.assertLessEqual(row["growth_health_score"], 100)


if __name__ == "__main__":
    unittest.main()
