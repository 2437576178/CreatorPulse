"""Tests for mock consumer and event validation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from kafka_tools.mock_consumer import read_ndjson, validate_topic_coverage  # noqa: E402
from kafka_tools.mock_event_builder import build_events  # noqa: E402
from kafka_tools.mock_producer import load_mock, write_ndjson  # noqa: E402


class MockConsumerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.events = build_events(load_mock())

    def test_reads_and_validates_ndjson(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "events.ndjson"
            write_ndjson(self.events, path)

            events = read_ndjson(path)

        self.assertEqual(len(events), len(self.events))
        self.assertEqual(events[0]["event_id"], self.events[0]["event_id"])

    def test_validates_topic_coverage(self) -> None:
        validate_topic_coverage(self.events)

    def test_rejects_missing_event_type_coverage(self) -> None:
        video_only = [event for event in self.events if event["event_type"] == "video_stats"]

        with self.assertRaises(ValueError):
            validate_topic_coverage(video_only)


if __name__ == "__main__":
    unittest.main()
