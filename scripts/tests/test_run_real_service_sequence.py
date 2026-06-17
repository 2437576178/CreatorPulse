"""Tests for the real-service sequence helper."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.run_real_service_sequence import build_sequence_plan  # noqa: E402


class RunRealServiceSequenceTest(unittest.TestCase):
    def test_build_sequence_plan_lists_real_service_steps_in_order(self) -> None:
        plan = build_sequence_plan()

        step_names = [step["name"] for step in plan["steps"]]
        self.assertEqual(
            step_names,
            [
                "localMysqlPreflight",
                "localMysqlImport",
                "sparkJdbcPreflight",
                "sparkJdbcLiveTest",
                "kafkaPreflight",
                "kafkaLiveTest",
                "fullPipelinePreflight",
                "fullPipelineStreaming",
            ],
        )
        self.assertEqual(plan["mode"], "dry-run")
        self.assertEqual(plan["stage"], "all")
        self.assertTrue(all(step["willExecute"] is False for step in plan["steps"]))

    def test_build_sequence_plan_can_focus_mysql_stage(self) -> None:
        plan = build_sequence_plan(stage="mysql")

        self.assertEqual(plan["stage"], "mysql")
        self.assertEqual(
            [step["name"] for step in plan["steps"]],
            ["localMysqlPreflight", "localMysqlImport"],
        )
        self.assertTrue(all(step["willExecute"] is False for step in plan["steps"]))

    def test_build_sequence_plan_can_focus_full_pipeline_stage(self) -> None:
        plan = build_sequence_plan(stage="full-pipeline")

        self.assertEqual(plan["stage"], "full-pipeline")
        self.assertEqual(
            [step["name"] for step in plan["steps"]],
            ["fullPipelinePreflight", "fullPipelineStreaming"],
        )
        self.assertIn("MySQL import", plan["prerequisites"][0])

    def test_cli_default_is_dry_run_json(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/run_real_service_sequence.py"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "dry-run")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["stage"], "all")
        self.assertIn("fullPipelineStreaming", [step["name"] for step in payload["steps"]])

    def test_cli_stage_filter_is_dry_run_json(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/run_real_service_sequence.py", "--stage", "kafka"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["stage"], "kafka")
        self.assertEqual(
            [step["name"] for step in payload["steps"]],
            ["kafkaPreflight", "kafkaLiveTest"],
        )


if __name__ == "__main__":
    unittest.main()
