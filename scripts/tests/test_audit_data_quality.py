"""Tests for MVP mock data quality audit report."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.audit_data_quality import build_quality_report  # noqa: E402


class AuditDataQualityTest(unittest.TestCase):
    def test_report_confirms_core_business_formulas(self) -> None:
        report = build_quality_report()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["summary"]["failedChecks"], [])
        self.assertEqual(report["checks"]["videoSnapshotFormulas"]["status"], "ok")
        self.assertEqual(report["checks"]["videoSnapshotFormulas"]["checkedRows"], 27)
        self.assertEqual(report["checks"]["trafficSourceRollups"]["status"], "ok")
        self.assertEqual(report["checks"]["trafficSourceRollups"]["checkedVideos"], 27)
        self.assertEqual(report["checks"]["creatorTrendFormulas"]["status"], "ok")
        self.assertEqual(report["checks"]["creatorTrendFormulas"]["checkedRows"], 7)

    def test_report_confirms_spark_dry_run_matches_snapshot_rollups(self) -> None:
        report = build_quality_report()

        spark = report["checks"]["sparkRollupParity"]
        self.assertEqual(spark["status"], "ok")
        self.assertEqual(spark["platformRows"], 3)
        self.assertEqual(spark["contributionRows"], 10)
        self.assertGreater(spark["totalViews"], 0)
        self.assertGreater(spark["newFollowers"], 0)

    def test_report_tracks_insight_quality_and_page_target_coverage(self) -> None:
        report = build_quality_report()

        insights = report["checks"]["insightQuality"]
        self.assertEqual(insights["status"], "ok")
        self.assertGreaterEqual(insights["checkedInsights"], 20)
        self.assertEqual(insights["insightsMissingEvidence"], [])
        self.assertEqual(insights["insightsMissingActions"], [])
        self.assertEqual(insights["missingPagePrefixes"], [])


if __name__ == "__main__":
    unittest.main()
