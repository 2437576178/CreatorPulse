"""Tests for CreatorPulse MVP Kafka mock events."""

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

from kafka_tools.message_contract import MessageContractError, validate_events  # noqa: E402
from kafka_tools.mock_event_builder import build_events  # noqa: E402
from kafka_tools.mock_producer import event_counts, load_mock, write_ndjson  # noqa: E402


class MockKafkaEventsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = load_mock()
        cls.events = build_events(cls.data)

    def test_builds_all_mvp_event_types(self) -> None:
        counts = event_counts(self.events)

        self.assertEqual(counts["video_stats"], 27)
        self.assertEqual(counts["creator_stats"], 7)
        self.assertEqual(counts["comment"], 12)
        self.assertEqual(counts["danmaku"], 8)
        self.assertEqual(counts["topic_trend"], 10)

    def test_events_satisfy_contract(self) -> None:
        validate_events(self.events)

    def test_invalid_event_is_rejected(self) -> None:
        bad_event = {"event_type": "video_stats", "event_id": "evt_bad"}

        with self.assertRaises(MessageContractError):
            validate_events([bad_event])

    def test_writes_ndjson(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "events.ndjson"
            write_ndjson(self.events[:3], output)

            lines = output.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 3)
            self.assertEqual(json.loads(lines[0])["event_type"], self.events[0]["event_type"])

    def test_cli_execute_kafka_reports_placeholder_bootstrap_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            output = Path(tmpdir) / "events.ndjson"
            env_file.write_text("KAFKA_BOOTSTRAP_SERVERS=192.168.56.10:9092\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "kafka_tools/mock_producer.py",
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
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("placeholder", payload["error"])


if __name__ == "__main__":
    unittest.main()
