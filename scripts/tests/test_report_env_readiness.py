"""Tests for redacted .env readiness reporting."""

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

from scripts.report_env_readiness import build_report  # noqa: E402


class ReportEnvReadinessTest(unittest.TestCase):
    def make_env_file(self, content: str) -> Path:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        path = Path(tmpdir.name) / ".env"
        path.write_text(content, encoding="utf-8")
        return path

    def test_reports_missing_env_without_network_or_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            report = build_report(env_file)

        self.assertEqual(report["status"], "needs-values")
        self.assertFalse(report["envFileExists"])
        self.assertFalse(report["safety"]["doesNetworkChecks"])
        self.assertFalse(report["safety"]["writesExternalServices"])
        self.assertIn("localMysql", report["blockingByStage"])
        self.assertIn("MYSQL_USER", report["blockingByStage"]["localMysql"])

    def test_redacts_passwords_and_marks_placeholders(self) -> None:
        env_file = self.make_env_file(
            "\n".join(
                [
                    "MYSQL_HOST=127.0.0.1",
                    "MYSQL_PORT=3306",
                    "MYSQL_DATABASE=creatorpulse",
                    "MYSQL_USER=your_user",
                    "MYSQL_PASSWORD=secret_password",
                    "SPARK_MYSQL_JDBC_URL=jdbc:mysql://127.0.0.1:3306/creatorpulse",
                    "SPARK_MYSQL_USER=spark_user",
                    "SPARK_MYSQL_PASSWORD=spark_secret",
                    "SPARK_MYSQL_DRIVER=com.mysql.cj.jdbc.Driver",
                    "KAFKA_BOOTSTRAP_SERVERS=192.168.56.10:9092",
                ]
            )
        )

        report = build_report(env_file)
        mysql_required = {item["key"]: item for item in report["stages"]["localMysql"]["required"]}
        kafka_required = {item["key"]: item for item in report["stages"]["kafka"]["required"]}

        self.assertEqual(mysql_required["MYSQL_PASSWORD"]["value"], "***")
        self.assertEqual(mysql_required["MYSQL_PASSWORD"]["status"], "configured")
        self.assertEqual(mysql_required["MYSQL_USER"]["status"], "placeholder")
        self.assertEqual(kafka_required["KAFKA_BOOTSTRAP_SERVERS"]["status"], "placeholder")
        self.assertNotIn("secret_password", json.dumps(report))
        self.assertNotIn("spark_secret", json.dumps(report))

    def test_ready_report_when_required_values_are_configured(self) -> None:
        env_file = self.make_env_file(
            "\n".join(
                [
                    "MYSQL_HOST=127.0.0.1",
                    "MYSQL_PORT=3306",
                    "MYSQL_DATABASE=creatorpulse",
                    "MYSQL_USER=creatorpulse",
                    "MYSQL_PASSWORD=mysql_secret",
                    "SPARK_MYSQL_JDBC_URL=jdbc:mysql://127.0.0.1:3306/creatorpulse",
                    "SPARK_MYSQL_USER=spark_user",
                    "SPARK_MYSQL_PASSWORD=spark_secret",
                    "SPARK_MYSQL_DRIVER=com.mysql.cj.jdbc.Driver",
                    "KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:9092",
                ]
            )
        )

        report = build_report(env_file)

        self.assertEqual(report["status"], "ready-for-strict-preflight")
        self.assertEqual(report["blockingByStage"], {})
        self.assertEqual(report["stages"]["fullPipeline"]["status"], "ready-for-strict-preflight")

    def test_cli_outputs_redacted_json(self) -> None:
        env_file = self.make_env_file(
            "\n".join(
                [
                    "MYSQL_HOST=127.0.0.1",
                    "MYSQL_PORT=3306",
                    "MYSQL_DATABASE=creatorpulse",
                    "MYSQL_USER=creatorpulse",
                    "MYSQL_PASSWORD=mysql_secret",
                ]
            )
        )

        result = subprocess.run(
            [sys.executable, "scripts/report_env_readiness.py", "--env-file", str(env_file)],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["stages"]["localMysql"]["required"][4]["value"], "***")
        self.assertNotIn("mysql_secret", result.stdout)

    def test_cli_writes_output_file_when_requested(self) -> None:
        env_file = self.make_env_file("MYSQL_PASSWORD=mysql_secret\n")
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "readiness.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/report_env_readiness.py",
                    "--env-file",
                    str(env_file),
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
            self.assertNotIn("mysql_secret", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
