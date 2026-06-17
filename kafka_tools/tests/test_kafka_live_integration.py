"""Optional live Kafka closed-loop integration test.

This test is skipped unless .env contains real KAFKA_BOOTSTRAP_SERVERS and
CREATORPULSE_RUN_KAFKA_LIVE=1 is set. It produces and consumes the MVP mock
events through the configured Kafka broker.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from kafka_tools.check_connectivity import DEFAULT_ENV_PATH, load_env_file, parse_bootstrap_servers  # noqa: E402


PLACEHOLDER_VALUES = {"192.168.56.10:9092"}


def kafka_env_ready() -> tuple[bool, str]:
    load_env_file(DEFAULT_ENV_PATH)
    if os.environ.get("CREATORPULSE_RUN_KAFKA_LIVE") != "1":
        return False, "set CREATORPULSE_RUN_KAFKA_LIVE=1 to allow live Kafka produce/consume"

    if not DEFAULT_ENV_PATH.exists():
        return False, ".env not found"

    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "")
    if not bootstrap_servers:
        return False, "missing KAFKA_BOOTSTRAP_SERVERS"
    if bootstrap_servers in PLACEHOLDER_VALUES:
        return False, "placeholder KAFKA_BOOTSTRAP_SERVERS"

    try:
        parse_bootstrap_servers(bootstrap_servers)
    except ValueError as exc:
        return False, str(exc)

    return True, "ready"


class KafkaLiveIntegrationTest(unittest.TestCase):
    def test_skip_helper_requires_explicit_opt_in(self) -> None:
        original = os.environ.pop("CREATORPULSE_RUN_KAFKA_LIVE", None)
        try:
            ready, reason = kafka_env_ready()
        finally:
            if original is not None:
                os.environ["CREATORPULSE_RUN_KAFKA_LIVE"] = original

        self.assertFalse(ready)
        self.assertIn("CREATORPULSE_RUN_KAFKA_LIVE=1", reason)

    def test_live_kafka_closed_loop_produces_and_consumes_mvp_events(self) -> None:
        ready, reason = kafka_env_ready()
        if not ready:
            self.skipTest(f"Live Kafka integration skipped: {reason}")

        result = subprocess.run(
            [
                sys.executable,
                str(ROOT_DIR / "kafka_tools" / "run_closed_loop.py"),
                "--execute-kafka",
            ],
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "kafka-closed-loop")
        self.assertEqual(payload["producedEvents"], 64)
        self.assertEqual(payload["consumedEvents"], 64)
        self.assertEqual(payload["eventCounts"]["video_stats"], 27)
        self.assertEqual(payload["eventCounts"]["creator_stats"], 7)


if __name__ == "__main__":
    unittest.main()
