"""Tests for the MVP verification command list."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.verify_mvp import CORE_COMMANDS  # noqa: E402


class VerifyMVPTest(unittest.TestCase):
    def test_full_pipeline_preflight_is_included_in_core_verification(self) -> None:
        command_args = [command.args for command in CORE_COMMANDS]

        self.assertIn(
            [sys.executable, "scripts/preflight.py", "--target", "full-pipeline"],
            command_args,
        )

    def test_real_service_sequence_plan_is_included_in_core_verification(self) -> None:
        command_args = [command.args for command in CORE_COMMANDS]

        self.assertIn(
            [sys.executable, "scripts/tests/test_run_real_service_sequence.py"],
            command_args,
        )
        self.assertIn(
            [sys.executable, "scripts/run_real_service_sequence.py"],
            command_args,
        )

    def test_real_service_execution_plan_report_is_included_in_core_verification(self) -> None:
        command_args = [command.args for command in CORE_COMMANDS]

        self.assertIn(
            [sys.executable, "scripts/tests/test_report_real_service_plans.py"],
            command_args,
        )
        self.assertIn(
            [sys.executable, "scripts/report_real_service_plans.py"],
            command_args,
        )

    def test_env_readiness_report_is_included_in_core_verification(self) -> None:
        command_args = [command.args for command in CORE_COMMANDS]

        self.assertIn(
            [sys.executable, "scripts/tests/test_report_env_readiness.py"],
            command_args,
        )
        self.assertIn(
            [sys.executable, "scripts/report_env_readiness.py"],
            command_args,
        )

    def test_real_service_execution_checklist_is_included_in_core_verification(self) -> None:
        command_args = [command.args for command in CORE_COMMANDS]

        self.assertIn(
            [sys.executable, "scripts/tests/test_report_execution_checklist.py"],
            command_args,
        )
        self.assertIn(
            [sys.executable, "scripts/report_execution_checklist.py"],
            command_args,
        )


if __name__ == "__main__":
    unittest.main()
