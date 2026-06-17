"""Tests for MVP data-object coverage reporting."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.audit_object_coverage import build_object_coverage_report  # noqa: E402


class AuditObjectCoverageTest(unittest.TestCase):
    def test_report_maps_core_objects_to_mysql_and_page_view_models(self) -> None:
        report = build_object_coverage_report()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["summary"]["totalObjects"], 11)
        self.assertEqual(report["summary"]["missingMySQLCoverage"], [])
        self.assertEqual(report["summary"]["unexpectedMissingPageExposure"], [])

        by_name = {item["name"]: item for item in report["objects"]}
        self.assertEqual(by_name["videos"]["mockCount"], 27)
        self.assertEqual(by_name["videos"]["mysqlRowCounts"]["videos"], 27)
        self.assertIn({"viewModel": "videoAnalysis", "field": "videos", "count": 27}, by_name["videos"]["viewModelExposures"])

        self.assertEqual(by_name["creatorMetricSnapshots"]["mockCount"], 7)
        self.assertIn(
            {"viewModel": "fansAnalysis", "field": "trend", "count": 7},
            by_name["creatorMetricSnapshots"]["viewModelExposures"],
        )

    def test_report_distinguishes_stored_only_objects_from_missing_coverage(self) -> None:
        report = build_object_coverage_report()
        by_name = {item["name"]: item for item in report["objects"]}

        traffic = by_name["videoTrafficSourceMetrics"]
        self.assertEqual(traffic["coverageStatus"], "stored-only")
        self.assertEqual(traffic["mysqlRowCounts"]["video_traffic_source_metrics"], 135)
        self.assertEqual(traffic["viewModelExposures"], [])
        self.assertIn("stored for later source-quality analysis", traffic["notes"])

    def test_spark_outputs_are_tracked_as_runtime_objects(self) -> None:
        report = build_object_coverage_report()
        by_name = {item["name"]: item for item in report["objects"]}

        platform = by_name["sparkPlatformMetricSummaries"]
        contribution = by_name["sparkVideoFollowerContributions"]

        self.assertEqual(platform["mockCount"], 3)
        self.assertEqual(platform["mysqlRowCounts"]["spark_platform_metric_summaries"], 3)
        self.assertIn(
            {"viewModel": "contentDistribution", "field": "sparkPlatformSummaries", "count": 3},
            platform["viewModelExposures"],
        )
        self.assertEqual(contribution["mockCount"], 10)
        self.assertIn(
            {"viewModel": "videoAnalysis", "field": "sparkContributions", "count": 10},
            contribution["viewModelExposures"],
        )


if __name__ == "__main__":
    unittest.main()
