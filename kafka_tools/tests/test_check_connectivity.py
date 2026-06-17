"""Tests for Kafka connectivity helper parsing."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from kafka_tools.check_connectivity import check_bootstrap_config, parse_bootstrap_servers  # noqa: E402


class KafkaConnectivityTest(unittest.TestCase):
    def test_parses_single_server(self) -> None:
        self.assertEqual(parse_bootstrap_servers("10.0.0.5:9092"), [("10.0.0.5", 9092)])

    def test_parses_multiple_servers(self) -> None:
        self.assertEqual(
            parse_bootstrap_servers("node1:9092,node2:9092"),
            [("node1", 9092), ("node2", 9092)],
        )

    def test_rejects_missing_port(self) -> None:
        with self.assertRaises(ValueError):
            parse_bootstrap_servers("node1")

    def test_rejects_placeholder_server(self) -> None:
        with self.assertRaises(ValueError):
            parse_bootstrap_servers("192.168.56.10:9092")

    def test_rejects_empty_host_or_invalid_port(self) -> None:
        for value in [":9092", "node1:not-a-port", "node1:0", "node1:-1"]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_bootstrap_servers(value)

    def test_check_bootstrap_config_reports_warning_for_placeholder(self) -> None:
        result = check_bootstrap_config("192.168.56.10:9092")

        self.assertEqual(result["status"], "warning")
        self.assertIn("placeholder", result["message"])

    def test_check_bootstrap_config_accepts_valid_servers(self) -> None:
        result = check_bootstrap_config("kafka-vm.local:9092,10.0.0.5:9093")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["servers"], ["kafka-vm.local:9092", "10.0.0.5:9093"])


if __name__ == "__main__":
    unittest.main()
