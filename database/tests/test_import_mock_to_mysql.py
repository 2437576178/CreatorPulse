"""Tests for MVP mock-to-MySQL row mapping."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from database.import_mock_to_mysql import build_table_rows, insert_sql, load_json, row_counts, validate_rows


class ImportMockToMySQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_json()
        cls.rows = build_table_rows(cls.data)

    def test_maps_expected_table_counts(self) -> None:
        counts = row_counts(self.rows)

        self.assertEqual(counts["creators"], 1)
        self.assertEqual(counts["platform_accounts"], 3)
        self.assertEqual(counts["videos"], 27)
        self.assertEqual(counts["video_metric_snapshots"], 27)
        self.assertEqual(counts["video_traffic_source_metrics"], 135)
        self.assertEqual(counts["creator_metric_snapshots"], 7)
        self.assertEqual(counts["audience_profile_snapshots"], 1)
        self.assertEqual(counts["topic_trend_snapshots"], 10)
        self.assertEqual(counts["insights"], len(self.data["insights"]))
        self.assertEqual(
            counts["insight_evidence_metrics"],
            sum(len(item["evidenceMetrics"]) for item in self.data["insights"]),
        )
        self.assertEqual(
            counts["recommended_actions"],
            sum(len(item["recommendedActions"]) for item in self.data["insights"]),
        )
        self.assertEqual(counts["spark_platform_metric_summaries"], 3)
        self.assertEqual(counts["spark_video_follower_contributions"], 10)

    def test_references_are_valid(self) -> None:
        validate_rows(self.rows)

    def test_json_columns_are_serialized_as_valid_json(self) -> None:
        creator = self.rows["creators"][0]
        self.assertEqual(json.loads(creator["niche_tags"]), self.data["creator"]["nicheTags"])

        audience = self.rows["audience_profile_snapshots"][0]
        self.assertEqual(json.loads(audience["gender"]), self.data["audienceProfileSnapshot"]["gender"])

        topic = self.rows["topic_trend_snapshots"][0]
        self.assertEqual(json.loads(topic["platforms"]), self.data["topicTrendSnapshots"][0]["platforms"])

    def test_insert_sql_uses_upsert(self) -> None:
        sql = insert_sql("creators", self.rows["creators"][0])

        self.assertIn("INSERT INTO `creators`", sql)
        self.assertIn("ON DUPLICATE KEY UPDATE", sql)
        self.assertNotIn("`creator_id` = VALUES(`creator_id`)", sql)

    def test_spark_result_rows_are_mapped_for_mysql_import(self) -> None:
        platform_rows = self.rows["spark_platform_metric_summaries"]
        contribution_rows = self.rows["spark_video_follower_contributions"]

        self.assertEqual({row["platform"] for row in platform_rows}, {"DOUYIN", "BILIBILI", "XIAOHONGSHU"})
        self.assertEqual([row["rank_position"] for row in contribution_rows], list(range(1, 11)))
        self.assertGreaterEqual(contribution_rows[0]["new_followers"], contribution_rows[-1]["new_followers"])


class SchemaFileTest(unittest.TestCase):
    def test_schema_contains_mvp_tables(self) -> None:
        schema = (ROOT_DIR / "database" / "schema.sql").read_text(encoding="utf-8")

        for table in [
            "creators",
            "users",
            "platform_accounts",
            "videos",
            "video_metric_snapshots",
            "video_traffic_source_metrics",
            "creator_metric_snapshots",
            "audience_profile_snapshots",
            "topic_trend_snapshots",
            "insights",
            "insight_evidence_metrics",
            "recommended_actions",
            "spark_platform_metric_summaries",
            "spark_video_follower_contributions",
        ]:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {table}", schema)


if __name__ == "__main__":
    unittest.main()
