"""Tests for real-service execution checklist reporting."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.report_execution_checklist import build_checklist  # noqa: E402


class ReportExecutionChecklistTest(unittest.TestCase):
    def make_env_file(self, content: str) -> Path:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        path = Path(tmpdir.name) / ".env"
        path.write_text(content, encoding="utf-8")
        return path

    def test_current_placeholder_env_blocks_execution_without_side_effects(self) -> None:
        env_file = self.make_env_file(
            "\n".join(
                [
                    "MYSQL_HOST=127.0.0.1",
                    "MYSQL_PORT=3306",
                    "MYSQL_DATABASE=creatorpulse",
                    "MYSQL_USER=your_user",
                    "MYSQL_PASSWORD=your_password",
                ]
            )
        )

        checklist = build_checklist(env_file)

        self.assertEqual(checklist["mode"], "dry-run")
        self.assertEqual(checklist["stage"], "all")
        self.assertFalse(checklist["safety"]["willWriteMySQL"])
        self.assertFalse(checklist["safety"]["willConnectKafka"])
        self.assertFalse(checklist["safety"]["willStartStreaming"])
        self.assertIn("mysql", checklist["blockedStages"])
        self.assertIn("MYSQL_USER", checklist["stages"]["mysql"]["envBlockingKeys"])
        self.assertFalse(checklist["stages"]["mysql"]["readyForExecute"])

    def test_configured_env_can_be_ready_for_strict_preflight_but_not_execute_when_tcp_or_login_warns(self) -> None:
        env_file = self.make_env_file(
            "\n".join(
                [
                    "MYSQL_HOST=127.0.0.1",
                    "MYSQL_PORT=1",
                    "MYSQL_DATABASE=creatorpulse",
                    "MYSQL_USER=creatorpulse",
                    "MYSQL_PASSWORD=mysql_secret",
                    "SPARK_MYSQL_JDBC_URL=jdbc:mysql://127.0.0.1:1/creatorpulse",
                    "SPARK_MYSQL_USER=spark_user",
                    "SPARK_MYSQL_PASSWORD=spark_secret",
                    "SPARK_MYSQL_DRIVER=com.mysql.cj.jdbc.Driver",
                    "KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:1",
                ]
            )
        )

        checklist = build_checklist(env_file)

        self.assertTrue(checklist["stages"]["mysql"]["readyForStrictPreflight"])
        self.assertFalse(checklist["stages"]["mysql"]["readyForExecute"])
        self.assertEqual(checklist["stages"]["mysql"]["envBlockingKeys"], [])
        self.assertGreater(checklist["stages"]["mysql"]["preflightSummary"]["counts"]["warning"], 0)
        self.assertNotIn("mysql_secret", json.dumps(checklist))

    def test_stage_filter_limits_report_to_one_stage(self) -> None:
        checklist = build_checklist(ROOT_DIR / ".env", stage="kafka")

        self.assertEqual(checklist["stage"], "kafka")
        self.assertEqual(set(checklist["stages"]), {"kafka"})
        self.assertEqual(checklist["blockedStages"], ["kafka"])
        self.assertIn("KAFKA_BOOTSTRAP_SERVERS", checklist["stages"]["kafka"]["envBlockingKeys"])

    def test_cli_outputs_json(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/report_execution_checklist.py", "--stage", "mysql"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "dry-run")
        self.assertEqual(payload["stage"], "mysql")
        self.assertIn("nextRecommendedStep", payload)
        self.assertEqual(set(payload["stages"]), {"mysql"})
        self.assertFalse(payload["stages"]["mysql"]["steps"][-1]["willExecute"])

    def test_cli_writes_output_file_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "checklist.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/report_execution_checklist.py",
                    "--stage",
                    "spark-jdbc",
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
            self.assertEqual(file_payload["stage"], "spark-jdbc")
            self.assertEqual(set(file_payload["stages"]), {"spark-jdbc"})


if __name__ == "__main__":
    unittest.main()
