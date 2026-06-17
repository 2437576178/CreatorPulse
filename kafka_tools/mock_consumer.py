"""Validate CreatorPulse Kafka events from NDJSON or a real Kafka topic.

Default mode reads local NDJSON produced by mock_producer.py. Use
--execute-kafka only after VM Kafka connectivity is confirmed.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

try:
    from .check_connectivity import load_env_file, parse_bootstrap_servers
    from .message_contract import TOPICS_BY_EVENT_TYPE, validate_event
    from .mock_producer import DEFAULT_OUTPUT_PATH, event_counts
except ImportError:
    from check_connectivity import load_env_file, parse_bootstrap_servers
    from message_contract import TOPICS_BY_EVENT_TYPE, validate_event
    from mock_producer import DEFAULT_OUTPUT_PATH, event_counts


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT_DIR / ".env"


def read_ndjson(path: Path = DEFAULT_OUTPUT_PATH) -> list[dict[str, Any]]:
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
        validate_event(event)
        events.append(event)
    return events


def validate_topic_coverage(events: list[dict[str, Any]]) -> None:
    expected = set(TOPICS_BY_EVENT_TYPE)
    actual = {event["event_type"] for event in events}
    missing = sorted(expected - actual)
    if missing:
        raise ValueError(f"Missing event types: {', '.join(missing)}")


def consume_from_kafka(bootstrap_servers: str, max_messages: int, timeout_ms: int) -> list[dict[str, Any]]:
    try:
        from kafka import KafkaConsumer
    except ImportError as exc:
        raise RuntimeError("Kafka client is not installed. Install kafka-python before --execute-kafka.") from exc

    servers = [f"{host}:{port}" for host, port in parse_bootstrap_servers(bootstrap_servers)]
    consumer = KafkaConsumer(
        *TOPICS_BY_EVENT_TYPE.values(),
        bootstrap_servers=servers,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=timeout_ms,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )
    events = []
    try:
        for message in consumer:
            event = message.value
            validate_event(event)
            events.append(event)
            if len(events) >= max_messages:
                break
    finally:
        consumer.close()
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate CreatorPulse MVP Kafka events")
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT_PATH, help="NDJSON file to validate")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--execute-kafka", action="store_true", help="Consume and validate events from Kafka")
    parser.add_argument("--max-messages", type=int, default=64)
    parser.add_argument("--timeout-ms", type=int, default=8000)
    args = parser.parse_args()

    mode = "ndjson-validate"
    if args.execute_kafka:
        load_env_file(args.env_file)
        events = consume_from_kafka(os.environ.get("KAFKA_BOOTSTRAP_SERVERS", ""), args.max_messages, args.timeout_ms)
        mode = "kafka-consume"
    else:
        events = read_ndjson(args.input)

    validate_topic_coverage(events)
    print(
        json.dumps(
            {
                "status": "ok",
                "mode": mode,
                "totalEvents": len(events),
                "counts": event_counts(events),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
