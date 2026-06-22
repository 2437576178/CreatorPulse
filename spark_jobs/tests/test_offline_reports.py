"""Tests for offline report generation."""

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
from spark_jobs.offline_daily_metrics import aggregate_daily_metrics  # noqa: E402
from spark_jobs.offline_reports import generate_reports  # noqa: E402


class OfflineReportsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_mock()
        raw_rows = archive_raw_video_stat_events(build_events(cls.data))
        cls.daily_metrics = aggregate_daily_metrics(
            raw_rows,
            cls.data["videos"],
            batch_run_id="run_daily_001",
            start_date="2026-06-14",
            end_date="2026-06-14",
        )

    def test_generates_daily_report_from_offline_daily_metrics(self) -> None:
        reports = generate_reports(
            self.daily_metrics,
            self.data,
            report_type="DAILY",
            period_start="2026-06-14",
            period_end="2026-06-14",
            batch_run_id="report_run_001",
        )

        self.assertEqual(len(reports), 1)
        report = reports[0]
        self.assertEqual(report["creator_id"], "creator_001")
        self.assertEqual(report["report_type"], "DAILY")
        self.assertEqual(report["period_start"], "2026-06-14")
        self.assertEqual(report["period_end"], "2026-06-14")
        self.assertEqual(report["status"], "GENERATED")
        self.assertIn("日报", report["title"])
        self.assertIn("你的账号", report["summary"])
        self.assertGreater(len(json.loads(report["highlights_json"])), 0)
        self.assertGreater(len(json.loads(report["actions_json"])), 0)
        metrics = json.loads(report["metrics_json"])
        self.assertEqual(metrics["newFollowers"], self.daily_metrics["offline_creator_daily_metrics"][0]["new_followers_delta"])

    def test_generates_empty_report_when_no_metrics_exist(self) -> None:
        reports = generate_reports(
            {"offline_creator_daily_metrics": [], "offline_platform_daily_metrics": [], "offline_video_daily_metrics": [], "offline_content_type_daily_metrics": []},
            self.data,
            report_type="WEEKLY",
            period_start="2026-06-08",
            period_end="2026-06-14",
            batch_run_id="report_run_empty",
        )

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["status"], "EMPTY")
        self.assertIn("等待离线任务生成", reports[0]["summary"])

    def test_cli_dry_run_outputs_report_counts(self) -> None:
        result = subprocess.run(
            [sys.executable, "spark_jobs/offline_reports.py", "--report-type", "DAILY"],
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
        self.assertEqual(payload["counts"]["creator_reports"], 1)
        self.assertEqual(payload["sample"]["report"]["reportType"], "DAILY")


if __name__ == "__main__":
    unittest.main()
