"""Tests for real-service readiness audit."""

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

from scripts.audit_real_service_readiness import build_audit  # noqa: E402


class AuditRealServiceReadinessTest(unittest.TestCase):
    def test_audit_passes_with_consistent_stage_filters_and_safe_defaults(self) -> None:
        audit = build_audit()

        self.assertEqual(audit["status"], "ok")
        self.assertEqual(audit["canonicalStages"], ["mysql", "spark-jdbc", "kafka", "full-pipeline"])
        self.assertEqual(audit["summary"]["failedChecks"], [])
        self.assertTrue(audit["safety"]["willWriteMySQL"] is False)
        self.assertTrue(audit["safety"]["willConnectKafka"] is False)
        self.assertTrue(audit["safety"]["willStartStreaming"] is False)

        for stage in ["mysql", "spark-jdbc", "kafka", "full-pipeline"]:
            with self.subTest(stage=stage):
                stage_report = audit["stages"][stage]
                self.assertEqual(stage_report["sequence"]["stage"], stage)
                self.assertEqual(stage_report["plans"]["stage"], stage)
                self.assertEqual(stage_report["checklist"]["stage"], stage)
                self.assertEqual(stage_report["sequence"]["willExecuteValues"], [False])
                self.assertEqual(stage_report["plans"]["unsafeFlags"], [])
                self.assertEqual(stage_report["checklist"]["unsafeFlags"], [])
                self.assertFalse(stage_report["failures"])

    def test_audit_stage_filter_returns_only_selected_stage(self) -> None:
        audit = build_audit(stage="kafka")

        self.assertEqual(audit["status"], "ok")
        self.assertEqual(list(audit["stages"]), ["kafka"])
        self.assertEqual(audit["stages"]["kafka"]["plans"]["planKeys"], ["kafkaClosedLoop"])
        self.assertEqual(
            audit["stages"]["kafka"]["sequence"]["stepNames"],
            ["kafkaPreflight", "kafkaLiveTest"],
        )
        self.assertEqual(audit["stages"]["kafka"]["checklist"]["checklistKeys"], ["kafka"])

    def test_cli_writes_output_file_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "readiness-audit.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/audit_real_service_readiness.py",
                    "--stage",
                    "full-pipeline",
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
            self.assertEqual(file_payload["stage"], "full-pipeline")
            self.assertEqual(list(file_payload["stages"]), ["full-pipeline"])


if __name__ == "__main__":
    unittest.main()
