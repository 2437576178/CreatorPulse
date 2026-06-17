"""Tests for the Kafka closed-loop orchestrator."""

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

from kafka_tools.mock_producer import DEFAULT_DATA_PATH  # noqa: E402
from kafka_tools.run_closed_loop import build_execution_plan, build_local_loop  # noqa: E402


class KafkaClosedLoopTest(unittest.TestCase):
    def test_local_closed_loop_generates_valid_events_and_spark_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "mock_events.ndjson"
            result = build_local_loop(DEFAULT_DATA_PATH, output, "test_closed_loop")

        self.assertEqual(result["mode"], "dry-run")
        self.assertEqual(result["executionPlan"]["willConnectKafka"], False)
        self.assertEqual(result["executionPlan"]["plannedEvents"], 64)
        self.assertEqual(result["executionPlan"]["plannedSparkRows"]["spark_video_follower_contributions"], 10)
        self.assertIn("write NDJSON mock events", result["executionPlan"]["steps"])
        self.assertEqual(result["producedEvents"], 64)
        self.assertEqual(result["consumedEvents"], 64)
        self.assertEqual(result["eventCounts"]["video_stats"], 27)
        self.assertEqual(result["eventCounts"]["creator_stats"], 7)
        self.assertEqual(result["eventCounts"]["comment"], 12)
        self.assertEqual(result["eventCounts"]["danmaku"], 8)
        self.assertEqual(result["eventCounts"]["topic_trend"], 10)
        self.assertEqual(result["sparkRows"]["spark_platform_metric_summaries"], 3)
        self.assertEqual(result["sparkRows"]["spark_video_follower_contributions"], 10)

    def test_build_execution_plan_describes_real_kafka_mode(self) -> None:
        plan = build_execution_plan(
            execute_kafka=True,
            event_counts_by_type={"video_stats": 27, "creator_stats": 7},
            spark_rows={"spark_platform_metric_summaries": 3, "spark_video_follower_contributions": 10},
        )

        self.assertEqual(plan["willConnectKafka"], True)
        self.assertEqual(plan["requiresExecuteKafkaFlag"], True)
        self.assertIn("check Kafka TCP reachability", plan["steps"])
        self.assertEqual(plan["plannedEvents"], 34)

    def test_cli_dry_run_includes_execution_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "mock_events.ndjson"
            result = subprocess.run(
                [
                    sys.executable,
                    "kafka_tools/run_closed_loop.py",
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
        payload = json.loads(result.stdout)
        self.assertEqual(payload["executionPlan"]["willConnectKafka"], False)
        self.assertEqual(payload["executionPlan"]["plannedEvents"], 64)

    def test_cli_execute_kafka_reports_placeholder_bootstrap_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            output = Path(tmpdir) / "mock_events.ndjson"
            env_file.write_text("KAFKA_BOOTSTRAP_SERVERS=192.168.56.10:9092\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "kafka_tools/run_closed_loop.py",
                    "--env-file",
                    str(env_file),
                    "--output",
                    str(output),
                    "--execute-kafka",
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
        self.assertIn("placeholder", payload["error"])


if __name__ == "__main__":
    unittest.main()
