"""Run the CreatorPulse Kafka MVP closed-loop check.

Default mode is fully local and does not connect to Kafka:
mock data -> NDJSON producer -> NDJSON consumer validation -> offline Spark-style aggregation.

Use --execute-kafka only after VM Kafka connectivity is confirmed. In that mode
the script checks TCP reachability, produces to Kafka, then consumes and
validates the expected event contract.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from kafka_tools.check_connectivity import check_tcp, load_env_file, parse_bootstrap_servers  # noqa: E402
from kafka_tools.mock_consumer import consume_from_kafka, read_ndjson, validate_topic_coverage  # noqa: E402
from kafka_tools.mock_event_builder import build_events  # noqa: E402
from kafka_tools.mock_producer import DEFAULT_DATA_PATH, DEFAULT_OUTPUT_PATH, event_counts, load_mock, produce_to_kafka, write_ndjson  # noqa: E402
from spark_jobs.kafka_events_to_mysql import aggregate_platform_metrics, aggregate_video_contributions  # noqa: E402


DEFAULT_ENV_PATH = ROOT_DIR / ".env"
LOCAL_LOOP_STEPS = [
    "build mock events",
    "write NDJSON mock events",
    "validate NDJSON consumer contract",
    "run offline Spark-style aggregation",
]
KAFKA_LOOP_STEPS = [
    "build mock events",
    "write NDJSON mock events",
    "check Kafka TCP reachability",
    "produce events to Kafka",
    "consume events from Kafka",
    "validate Kafka event contract",
]


def build_execution_plan(
    execute_kafka: bool,
    event_counts_by_type: dict[str, int],
    spark_rows: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "willConnectKafka": execute_kafka,
        "requiresExecuteKafkaFlag": True,
        "steps": KAFKA_LOOP_STEPS if execute_kafka else LOCAL_LOOP_STEPS,
        "plannedEvents": sum(event_counts_by_type.values()),
        "plannedEventCounts": event_counts_by_type,
        "plannedSparkRows": spark_rows or {},
    }


def build_local_loop(data_path: Path, output_path: Path, run_id: str) -> dict[str, Any]:
    data = load_mock(data_path)
    events = build_events(data)
    write_ndjson(events, output_path)
    consumed_events = read_ndjson(output_path)
    validate_topic_coverage(consumed_events)

    calculated_at = datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()
    platform_rows = aggregate_platform_metrics(consumed_events, run_id, calculated_at)
    contribution_rows = aggregate_video_contributions(consumed_events, run_id, calculated_at)
    counts = event_counts(consumed_events)
    spark_rows = {
        "spark_platform_metric_summaries": len(platform_rows),
        "spark_video_follower_contributions": len(contribution_rows),
    }

    return {
        "mode": "dry-run",
        "output": str(output_path),
        "producedEvents": len(events),
        "consumedEvents": len(consumed_events),
        "eventCounts": counts,
        "sparkRows": spark_rows,
        "executionPlan": build_execution_plan(False, counts, spark_rows),
    }


def build_kafka_loop(
    data_path: Path,
    output_path: Path,
    bootstrap_servers: str,
    timeout_seconds: float,
    max_messages: int,
    timeout_ms: int,
) -> dict[str, Any]:
    data = load_mock(data_path)
    events = build_events(data)
    write_ndjson(events, output_path)
    expected_counts = event_counts(events)

    servers = parse_bootstrap_servers(bootstrap_servers)
    checks = [check_tcp(host, port, timeout_seconds) for host, port in servers]
    if not all(item["reachable"] for item in checks):
        return {
            "mode": "kafka-closed-loop",
            "status": "failed",
            "executionPlan": build_execution_plan(True, expected_counts),
            "connectivity": checks,
            "producedEvents": 0,
            "consumedEvents": 0,
        }

    produce_to_kafka(events, bootstrap_servers)
    consumed_events = consume_from_kafka(bootstrap_servers, max_messages=max_messages, timeout_ms=timeout_ms)
    validate_topic_coverage(consumed_events)

    return {
        "mode": "kafka-closed-loop",
        "executionPlan": build_execution_plan(True, expected_counts),
        "connectivity": checks,
        "producedEvents": len(events),
        "consumedEvents": len(consumed_events),
        "eventCounts": event_counts(consumed_events),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CreatorPulse Kafka MVP closed-loop check")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--run-id", default="kafka_closed_loop_001")
    parser.add_argument("--execute-kafka", action="store_true", help="Use real Kafka producer/consumer")
    parser.add_argument("--bootstrap-servers", default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--max-messages", type=int, default=64)
    parser.add_argument("--timeout-ms", type=int, default=8000)
    args = parser.parse_args()

    load_env_file(args.env_file)
    try:
        if args.execute_kafka:
            bootstrap_servers = args.bootstrap_servers or os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "")
            timeout_seconds = args.timeout if args.timeout is not None else float(os.environ.get("KAFKA_TEST_TIMEOUT_SECONDS", "5"))
            result = build_kafka_loop(
                args.data,
                args.output,
                bootstrap_servers,
                timeout_seconds,
                args.max_messages,
                args.timeout_ms,
            )
        else:
            result = build_local_loop(args.data, args.output, args.run_id)

        status = result.get("status", "ok")
        print(json.dumps({"status": status, **result}, ensure_ascii=False, indent=2))
        if status != "ok":
            raise SystemExit(1)
    except Exception as exc:  # noqa: BLE001 - CLI returns structured Kafka setup failures.
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1) from None


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
