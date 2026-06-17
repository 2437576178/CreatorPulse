"""Tests for Kafka Structured Streaming job configuration."""

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

from spark_jobs.kafka_streaming_to_mysql import (  # noqa: E402
    VIDEO_STATS_SCHEMA_JSON,
    build_execution_plan,
    dry_run_summary,
    load_streaming_config,
    require_streaming_config,
)


class KafkaStreamingToMySQLTest(unittest.TestCase):
    def setUp(self) -> None:
        self.old_env = dict(os.environ)
        os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "127.0.0.1:9092"
        os.environ["SPARK_STREAM_TRIGGER_SECONDS"] = "15"

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.old_env)

    def test_loads_streaming_config_from_env(self) -> None:
        config = load_streaming_config()

        self.assertEqual(config.bootstrap_servers, "127.0.0.1:9092")
        self.assertEqual(config.trigger_seconds, 15)
        self.assertEqual(config.platform_table, "spark_platform_metric_summaries")

    def test_dry_run_summary_exposes_expected_targets(self) -> None:
        summary = dry_run_summary(load_streaming_config())

        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["kafka"]["topic"], "video_stats_topic")
        self.assertEqual(summary["mysql"]["platformTable"], "spark_platform_metric_summaries")
        self.assertEqual(summary["executionPlan"]["willStartStreaming"], False)
        self.assertEqual(summary["executionPlan"]["requiresExecuteFlag"], True)
        self.assertEqual(summary["executionPlan"]["requiresFullPipelineLiveFlag"], True)
        self.assertEqual(summary["executionPlan"]["sourceTopic"], "video_stats_topic")
        self.assertEqual(
            summary["executionPlan"]["targetTables"],
            ["spark_platform_metric_summaries", "spark_video_follower_contributions"],
        )
        self.assertIn("stats", summary["schemaFields"])
        self.assertIn("growth", summary["schemaFields"])

    def test_build_execution_plan_describes_execute_mode(self) -> None:
        config = load_streaming_config()
        plan = build_execution_plan(config, execute=True)

        self.assertEqual(plan["willStartStreaming"], True)
        self.assertEqual(plan["checkpointDir"], config.checkpoint_dir)
        self.assertIn("read video_stats_topic from Kafka", plan["steps"])

    def test_schema_contains_video_stats_fields(self) -> None:
        field_names = [field["name"] for field in VIDEO_STATS_SCHEMA_JSON["fields"]]

        self.assertIn("event_type", field_names)
        self.assertIn("creator_id", field_names)
        self.assertIn("content_id", field_names)
        self.assertIn("stats", field_names)
        self.assertIn("growth", field_names)

    def test_require_streaming_config_rejects_placeholder_bootstrap(self) -> None:
        os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "192.168.56.10:9092"

        with self.assertRaisesRegex(RuntimeError, "placeholder"):
            require_streaming_config()

    def test_require_streaming_config_rejects_bad_output_mode(self) -> None:
        os.environ["SPARK_STREAM_OUTPUT_MODE"] = "complete"

        with self.assertRaisesRegex(RuntimeError, "output mode"):
            require_streaming_config()

    def test_cli_execute_reports_placeholder_bootstrap_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "KAFKA_BOOTSTRAP_SERVERS=192.168.56.10:9092",
                        "SPARK_STREAM_TRIGGER_SECONDS=30",
                        "SPARK_STREAM_OUTPUT_MODE=update",
                    ]
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, "spark_jobs/kafka_streaming_to_mysql.py", "--env-file", str(env_file), "--execute"],
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

    def test_cli_execute_requires_full_pipeline_live_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "CREATORPULSE_RUN_FULL_PIPELINE_LIVE=0",
                        "KAFKA_BOOTSTRAP_SERVERS=10.0.0.5:9092",
                        "SPARK_STREAM_TRIGGER_SECONDS=30",
                        "SPARK_STREAM_OUTPUT_MODE=update",
                        "SPARK_MYSQL_JDBC_URL=jdbc:mysql://127.0.0.1:3306/creatorpulse",
                        "SPARK_MYSQL_USER=spark_user",
                        "SPARK_MYSQL_PASSWORD=spark_password",
                        "SPARK_MYSQL_DRIVER=com.mysql.cj.jdbc.Driver",
                    ]
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, "spark_jobs/kafka_streaming_to_mysql.py", "--env-file", str(env_file), "--execute"],
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
        self.assertIn("CREATORPULSE_RUN_FULL_PIPELINE_LIVE=1", payload["error"])


if __name__ == "__main__":
    unittest.main()
