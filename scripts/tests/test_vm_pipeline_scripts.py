"""Static tests for VM pipeline management scripts."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT_DIR / "scripts" / "vm_pipeline"


class VMPipelineScriptsTest(unittest.TestCase):
    def test_start_script_manages_expected_processes(self) -> None:
        content = (SCRIPT_DIR / "start_pipeline.sh").read_text(encoding="utf-8")

        self.assertIn("set -euo pipefail", content)
        self.assertIn("flume-ng agent", content)
        self.assertIn("mock_generator/generate_events.py", content)
        self.assertIn("--require-db", content)
        self.assertIn("spark-submit --master local[2]", content)
        self.assertIn("kafka_streaming_to_mysql_py36.py", content)
        self.assertIn("require_port 2181", content)
        self.assertIn("require_port 9092", content)
        self.assertIn("creatorpulse-flume.pid", content)
        self.assertIn("creatorpulse-mock-generator.pid", content)
        self.assertIn("creatorpulse-spark-streaming.pid", content)

    def test_stop_script_stops_reverse_dependency_order(self) -> None:
        content = (SCRIPT_DIR / "stop_pipeline.sh").read_text(encoding="utf-8")

        spark_index = content.index('stop_process "Spark Streaming"')
        generator_index = content.index('stop_process "Mock generator"')
        flume_index = content.index('stop_process "Flume"')
        self.assertLess(spark_index, generator_index)
        self.assertLess(generator_index, flume_index)

    def test_status_script_reports_all_managed_processes(self) -> None:
        content = (SCRIPT_DIR / "status_pipeline.sh").read_text(encoding="utf-8")

        self.assertIn('show_process "Flume"', content)
        self.assertIn('show_process "Mock generator"', content)
        self.assertIn('show_process "Spark Streaming"', content)


if __name__ == "__main__":
    unittest.main()
