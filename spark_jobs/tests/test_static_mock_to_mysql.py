"""Tests for static mock Spark JDBC smoke job calculations."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from spark_jobs.static_mock_to_mysql import (  # noqa: E402
    build_execution_plan,
    calculate_platform_summaries,
    calculate_video_contributions,
    require_jdbc_config,
    load_mock,
)


class StaticMockToMySQLTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_mock()

    def test_calculates_one_summary_per_platform(self) -> None:
        rows = calculate_platform_summaries(self.data, "test_run", "2026-06-15T00:00:00")

        self.assertEqual(len(rows), 3)
        self.assertEqual({row["platform"] for row in rows}, {"DOUYIN", "BILIBILI", "XIAOHONGSHU"})
        self.assertEqual(sum(row["video_count"] for row in rows), 27)
        self.assertEqual(sum(row["total_views"] for row in rows), sum(item["views"] for item in self.data["videoMetricSnapshots"]))
        self.assertEqual(
            sum(row["new_followers"] for row in rows),
            sum(item["newFollowers"] for item in self.data["videoMetricSnapshots"]),
        )

    def test_calculates_top_video_contributions(self) -> None:
        rows = calculate_video_contributions(self.data, "test_run", "2026-06-15T00:00:00", limit=5)

        self.assertEqual(len(rows), 5)
        self.assertEqual([row["rank_position"] for row in rows], [1, 2, 3, 4, 5])
        self.assertGreaterEqual(rows[0]["new_followers"], rows[-1]["new_followers"])
        self.assertTrue(rows[0]["title"])

    def test_require_jdbc_config_rejects_placeholder_credentials_and_bad_mode(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "SPARK_MYSQL_JDBC_URL": "jdbc:mysql://127.0.0.1:3306/creatorpulse",
                "SPARK_MYSQL_USER": "your_user",
                "SPARK_MYSQL_PASSWORD": "your_password",
                "SPARK_MYSQL_DRIVER": "com.mysql.cj.jdbc.Driver",
                "SPARK_MYSQL_WRITE_MODE": "overwrite",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "placeholder|write mode"):
                require_jdbc_config()

    def test_require_jdbc_config_accepts_valid_mysql_append_config(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "SPARK_MYSQL_JDBC_URL": "jdbc:mysql://127.0.0.1:3306/creatorpulse",
                "SPARK_MYSQL_USER": "spark_user",
                "SPARK_MYSQL_PASSWORD": "spark_password",
                "SPARK_MYSQL_DRIVER": "com.mysql.cj.jdbc.Driver",
                "SPARK_MYSQL_WRITE_MODE": "append",
            },
            clear=True,
        ):
            jdbc = require_jdbc_config()

        self.assertEqual(jdbc["SPARK_MYSQL_WRITE_MODE"], "append")

    def test_build_execution_plan_describes_dry_run_jdbc_write(self) -> None:
        counts = {
            "spark_platform_metric_summaries": 3,
            "spark_video_follower_contributions": 10,
        }

        plan = build_execution_plan(False, counts, "append")

        self.assertEqual(plan["willWriteMySQL"], False)
        self.assertEqual(plan["writeMode"], "append")
        self.assertEqual(
            plan["targetTables"],
            ["spark_platform_metric_summaries", "spark_video_follower_contributions"],
        )
        self.assertEqual(plan["plannedRows"], counts)
        self.assertIn("require Spark JDBC config", plan["steps"][0])

    def test_cli_dry_run_includes_execution_plan(self) -> None:
        result = subprocess.run(
            [sys.executable, "spark_jobs/static_mock_to_mysql.py"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["executionPlan"]["willWriteMySQL"], False)
        self.assertEqual(payload["executionPlan"]["plannedRows"]["spark_video_follower_contributions"], 10)

    def test_cli_execute_reports_config_failure_as_json_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "SPARK_MYSQL_JDBC_URL=jdbc:mysql://127.0.0.1:3306/creatorpulse",
                        "SPARK_MYSQL_USER=your_user",
                        "SPARK_MYSQL_PASSWORD=your_password",
                        "SPARK_MYSQL_DRIVER=com.mysql.cj.jdbc.Driver",
                    ]
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "spark_jobs/static_mock_to_mysql.py",
                    "--env-file",
                    str(env_file),
                    "--execute",
                ],
                cwd=ROOT_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("Spark JDBC config failed", payload["error"])


if __name__ == "__main__":
    unittest.main()
