"""Tests for rule-based insights derived from Spark aggregate outputs."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.import_mock_to_mysql import build_table_rows, load_json  # noqa: E402
from mysql_repository import MySQLRepository  # noqa: E402
from spark_insights import build_spark_insights  # noqa: E402


class SparkInsightsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rows = build_table_rows(load_json())
        cls.contract = MySQLRepository().to_contract(rows)

    def test_builds_platform_and_video_insights(self) -> None:
        insights = build_spark_insights(self.contract)

        self.assertEqual(len(insights), 2)
        self.assertEqual({item["generatedBy"] for item in insights}, {"SPARK_RULE_ENGINE"})
        self.assertIn("content.platform", insights[0]["pageTargets"])
        self.assertIn("video.contribution", insights[1]["pageTargets"])

    def test_merged_contract_exposes_spark_insights_in_view_models(self) -> None:
        insight_ids = {item["insightId"] for item in self.contract["insights"]}

        self.assertIn("insight_spark_platform_efficiency", insight_ids)
        self.assertIn("insight_spark_video_contribution", insight_ids)
        self.assertTrue(
            any(item["generatedBy"] == "SPARK_RULE_ENGINE" for item in self.contract["viewModels"]["videoAnalysis"]["insights"])
        )
        self.assertTrue(
            any(item["generatedBy"] == "SPARK_RULE_ENGINE" for item in self.contract["viewModels"]["contentDistribution"]["insights"])
        )


if __name__ == "__main__":
    unittest.main()
