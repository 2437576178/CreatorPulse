"""Tests for real-service execution plan reporting."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.report_real_service_plans import build_report  # noqa: E402


class ReportRealServicePlansTest(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_kafka = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
        os.environ.pop("KAFKA_BOOTSTRAP_SERVERS", None)

    def tearDown(self) -> None:
        if self.previous_kafka is None:
            os.environ.pop("KAFKA_BOOTSTRAP_SERVERS", None)
        else:
            os.environ["KAFKA_BOOTSTRAP_SERVERS"] = self.previous_kafka

    def make_env_file(self) -> Path:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        path = Path(tmpdir.name) / ".env"
        path.write_text(
            "\n".join(
                [
                    "MYSQL_HOST=127.0.0.1",
                    "MYSQL_PORT=3306",
                    "MYSQL_DATABASE=creatorpulse",
                    "MYSQL_USER=test_user",
                    "MYSQL_PASSWORD=test_password",
                    "SPARK_MYSQL_JDBC_URL=jdbc:mysql://127.0.0.1:3306/creatorpulse",
                    "SPARK_MYSQL_USER=test_user",
                    "SPARK_MYSQL_PASSWORD=test_password",
                    "SPARK_MYSQL_DRIVER=com.mysql.cj.jdbc.Driver",
                    "SPARK_MYSQL_WRITE_MODE=append",
                    "KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:9092",
                    "SPARK_STREAM_TRIGGER_SECONDS=30",
                    "SPARK_STREAM_OUTPUT_MODE=update",
                ]
            ),
            encoding="utf-8",
        )
        return path

    def test_build_report_collects_all_dry_run_plans(self) -> None:
        report = build_report(self.make_env_file(), ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json")

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["mode"], "dry-run")
        self.assertEqual(report["stage"], "all")
        self.assertEqual(report["failedPlans"], [])
        self.assertEqual(
            set(report["plans"]),
            {"localMysql", "sparkJdbcStatic", "kafkaClosedLoop", "fullPipelineStreaming"},
        )
        self.assertFalse(report["safety"]["willWriteMySQL"])
        self.assertFalse(report["safety"]["willConnectKafka"])
        self.assertFalse(report["safety"]["willStartStreaming"])

    def test_report_keeps_real_execution_switches_off(self) -> None:
        report = build_report(self.make_env_file(), ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json")

        self.assertFalse(report["plans"]["localMysql"]["executionPlan"]["willWriteMySQL"])
        self.assertFalse(report["plans"]["sparkJdbcStatic"]["executionPlan"]["willWriteMySQL"])
        self.assertFalse(report["plans"]["kafkaClosedLoop"]["executionPlan"]["willConnectKafka"])
        self.assertFalse(report["plans"]["fullPipelineStreaming"]["executionPlan"]["willStartStreaming"])

    def test_stage_filter_limits_report_to_one_plan(self) -> None:
        report = build_report(
            self.make_env_file(),
            ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json",
            stage="kafka",
        )

        self.assertEqual(report["stage"], "kafka")
        self.assertEqual(set(report["plans"]), {"kafkaClosedLoop"})
        self.assertFalse(report["plans"]["kafkaClosedLoop"]["executionPlan"]["willConnectKafka"])

    def test_cli_outputs_json(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/report_real_service_plans.py",
                "--env-file",
                str(self.make_env_file()),
                "--stage",
                "spark-jdbc",
            ],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["stage"], "spark-jdbc")
        self.assertEqual(set(payload["plans"]), {"sparkJdbcStatic"})
        self.assertEqual(payload["plans"]["sparkJdbcStatic"]["executionPlan"]["plannedRows"]["spark_video_follower_contributions"], 10)

    def test_cli_writes_output_file_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "plans.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/report_real_service_plans.py",
                    "--env-file",
                    str(self.make_env_file()),
                    "--stage",
                    "kafka",
                    "--output",
                    str(output),
                ],
                cwd=ROOT_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(result.returncode, 0)
            self.assertTrue(output.exists())
            file_payload = json.loads(output.read_text(encoding="utf-8"))
            stdout_payload = json.loads(result.stdout)
            self.assertEqual(file_payload, stdout_payload)
            self.assertEqual(file_payload["stage"], "kafka")
            self.assertEqual(set(file_payload["plans"]), {"kafkaClosedLoop"})

    def test_missing_streaming_config_returns_partial_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("", encoding="utf-8")
            report = build_report(env_file, ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json")

        self.assertEqual(report["status"], "partial")
        self.assertIn("fullPipelineStreaming", report["failedPlans"])
        self.assertEqual(report["plans"]["fullPipelineStreaming"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
