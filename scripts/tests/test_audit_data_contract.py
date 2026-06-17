"""Tests for the MVP data-contract audit report."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.audit_data_contract import build_audit_report  # noqa: E402


class AuditDataContractTest(unittest.TestCase):
    def test_report_confirms_schema_import_and_view_model_contracts(self) -> None:
        report = build_audit_report()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["schema"]["tableCount"], 13)
        self.assertEqual(report["mysqlImport"]["contractCheck"], "ok")
        self.assertEqual(report["mysqlImport"]["rowCounts"]["videos"], 27)
        self.assertEqual(report["mysqlImport"]["rowCounts"]["spark_video_follower_contributions"], 10)
        self.assertEqual(report["viewModels"]["contractCheck"], "ok")
        self.assertEqual(set(report["viewModels"]["names"]), {
            "growthDashboard",
            "fansAnalysis",
            "videoAnalysis",
            "contentDistribution",
            "opportunities",
            "profile",
        })
        self.assertEqual(report["openapi"]["contractCheck"], "ok")

    def test_import_columns_do_not_drift_from_schema(self) -> None:
        report = build_audit_report()

        for table in report["schema"]["tables"]:
            with self.subTest(table=table["name"]):
                self.assertEqual(table["importColumnsMissingFromSchema"], [])
                self.assertEqual(table["requiredSchemaColumnsMissingFromImport"], [])


if __name__ == "__main__":
    unittest.main()
