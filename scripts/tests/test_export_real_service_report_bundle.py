"""Tests for exporting real-service readiness report bundles."""

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

from scripts.export_real_service_report_bundle import build_bundle  # noqa: E402


class ExportRealServiceReportBundleTest(unittest.TestCase):
    def test_build_bundle_writes_all_expected_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "bundle"
            bundle = build_bundle(output_dir=output_dir)

            self.assertEqual(bundle["status"], "ok")
            self.assertEqual(bundle["mode"], "dry-run")
            self.assertEqual(bundle["stage"], "all")
            self.assertFalse(bundle["safety"]["willWriteMySQL"])
            self.assertFalse(bundle["safety"]["willConnectKafka"])
            self.assertFalse(bundle["safety"]["willStartStreaming"])

            report_names = {report["name"] for report in bundle["reports"]}
            self.assertEqual(
                report_names,
                {
                    "status",
                    "envReadiness",
                    "sequence",
                    "executionPlans",
                    "executionChecklist",
                    "readinessAudit",
                },
            )
            for report in bundle["reports"]:
                path = Path(report["path"])
                self.assertTrue(path.exists(), report["name"])
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["mode"], report["mode"])

            manifest_path = output_dir / "manifest.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest, bundle)

    def test_stage_filter_exports_stage_specific_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "bundle"
            bundle = build_bundle(output_dir=output_dir, stage="kafka")

            self.assertEqual(bundle["stage"], "kafka")
            plans = json.loads((output_dir / "execution-plans.json").read_text(encoding="utf-8"))
            checklist = json.loads((output_dir / "execution-checklist.json").read_text(encoding="utf-8"))
            audit = json.loads((output_dir / "readiness-audit.json").read_text(encoding="utf-8"))

            self.assertEqual(plans["stage"], "kafka")
            self.assertEqual(set(plans["plans"]), {"kafkaClosedLoop"})
            self.assertEqual(set(checklist["stages"]), {"kafka"})
            self.assertEqual(list(audit["stages"]), ["kafka"])

    def test_cli_exports_bundle_and_prints_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "bundle"
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/export_real_service_report_bundle.py",
                    "--stage",
                    "mysql",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=ROOT_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["stage"], "mysql")
            self.assertTrue((output_dir / "manifest.json").exists())
            self.assertTrue((output_dir / "execution-checklist.json").exists())
            self.assertIn("executionChecklist", {report["name"] for report in payload["reports"]})


if __name__ == "__main__":
    unittest.main()
