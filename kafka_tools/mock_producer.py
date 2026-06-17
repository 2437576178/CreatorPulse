"""Mock Kafka producer for CreatorPulse MVP events.

By default this script writes NDJSON events locally. Use --execute-kafka only
after Kafka VM connectivity is confirmed.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

try:
    from .check_connectivity import load_env_file, parse_bootstrap_servers
    from .mock_event_builder import build_events
except ImportError:
    from check_connectivity import load_env_file, parse_bootstrap_servers
    from mock_event_builder import build_events


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "kafka_tools" / "out" / "mock_events.ndjson"
DEFAULT_ENV_PATH = ROOT_DIR / ".env"


def load_mock(path: Path = DEFAULT_DATA_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_ndjson(events: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(event, ensure_ascii=False, separators=(",", ":")) for event in events)
    path.write_text(content + "\n", encoding="utf-8")


def event_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        counts[event["event_type"]] = counts.get(event["event_type"], 0) + 1
    return dict(sorted(counts.items()))


def produce_to_kafka(events: list[dict[str, Any]], bootstrap_servers: str) -> None:
    servers = [f"{host}:{port}" for host, port in parse_bootstrap_servers(bootstrap_servers)]

    try:
        from kafka import KafkaProducer
    except ImportError as exc:
        raise RuntimeError("Kafka client is not installed. Install kafka-python before --execute-kafka.") from exc

    producer = KafkaProducer(
        bootstrap_servers=servers,
        value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
        key_serializer=lambda value: value.encode("utf-8"),
    )
    try:
        for event in events:
            producer.send(event["topic"], key=event["content_id"] if "content_id" in event else event["event_id"], value=event)
        producer.flush()
    finally:
        producer.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build MVP mock events and optionally produce them to Kafka")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--execute-kafka", action="store_true", help="Send events to Kafka instead of only writing NDJSON")
    args = parser.parse_args()

    load_env_file(args.env_file)
    data = load_mock(args.data)
    events = build_events(data)
    write_ndjson(events, args.output)

    try:
        mode = "dry-run"
        if args.execute_kafka:
            bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "")
            produce_to_kafka(events, bootstrap_servers)
            mode = "kafka-produce"

        print(
            json.dumps(
                {
                    "status": "ok",
                    "mode": mode,
                    "output": str(args.output),
                    "totalEvents": len(events),
                    "counts": event_counts(events),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    except Exception as exc:  # noqa: BLE001 - CLI returns structured Kafka setup failures.
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
