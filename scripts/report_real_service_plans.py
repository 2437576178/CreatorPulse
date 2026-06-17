"""Aggregate real-service dry-run execution plans for CreatorPulse MVP.

This report is intentionally read-only. It combines the MySQL, Spark JDBC,
Kafka closed-loop, and Kafka -> Spark -> MySQL streaming plans without writing
MySQL rows, connecting to Kafka, or starting Spark Streaming.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from kafka_tools.mock_event_builder import build_events  # noqa: E402
from kafka_tools.mock_producer import event_counts, load_mock  # noqa: E402
from scripts.setup_local_mysql import run_setup  # noqa: E402
from scripts.report_output import format_json_report, write_json_report  # noqa: E402
from spark_jobs.kafka_events_to_mysql import aggregate_platform_metrics, aggregate_video_contributions  # noqa: E402
from spark_jobs.kafka_streaming_to_mysql import dry_run_summary, load_streaming_config  # noqa: E402
from spark_jobs.static_mock_to_mysql import (  # noqa: E402
    build_execution_plan as build_spark_static_plan,
    calculate_platform_summaries,
    calculate_video_contributions,
    load_env_file as load_spark_env_file,
)


DEFAULT_ENV_PATH = ROOT_DIR / ".env"
DEFAULT_DATA_PATH = ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json"
DEFAULT_RUN_ID = "real_service_plan_report_001"

STAGE_PLAN_KEYS = {
    "all": ["localMysql", "sparkJdbcStatic", "kafkaClosedLoop", "fullPipelineStreaming"],
    "mysql": ["localMysql"],
    "spark-jdbc": ["sparkJdbcStatic"],
    "kafka": ["kafkaClosedLoop"],
    "full-pipeline": ["fullPipelineStreaming"],
}

ENV_KEYS = [
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_DATABASE",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "SPARK_MYSQL_JDBC_URL",
    "SPARK_MYSQL_USER",
    "SPARK_MYSQL_PASSWORD",
    "SPARK_MYSQL_DRIVER",
    "SPARK_MYSQL_WRITE_MODE",
    "KAFKA_BOOTSTRAP_SERVERS",
    "KAFKA_TEST_TIMEOUT_SECONDS",
    "SPARK_STREAM_CHECKPOINT_DIR",
    "SPARK_STREAM_TRIGGER_SECONDS",
    "SPARK_STREAM_OUTPUT_MODE",
]


@contextmanager
def preserved_environment() -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in ENV_KEYS}
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def safe_plan(name: str, builder) -> dict[str, Any]:
    try:
        plan = builder()
    except Exception as exc:  # noqa: BLE001 - report should show every failing plan without stopping.
        return {
            "status": "failed",
            "name": name,
            "error": str(exc),
        }
    return {
        "status": "ok",
        "name": name,
        **plan,
    }


def local_mysql_plan(env_file: Path, data_file: Path) -> dict[str, Any]:
    with preserved_environment():
        result = run_setup(env_file, data_file, execute=False, strict_preflight=False)
    return {
        "mode": result["mode"],
        "preflight": result["preflight"],
        "schema": result["schema"],
        "rows": result["rows"],
        "executionPlan": result["executionPlan"],
    }


def spark_jdbc_static_plan(env_file: Path, data_file: Path, run_id: str) -> dict[str, Any]:
    with preserved_environment():
        load_spark_env_file(env_file)
        data = load_mock(data_file)
        calculated_at = datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()
        platform_rows = calculate_platform_summaries(data, run_id, calculated_at)
        contribution_rows = calculate_video_contributions(data, run_id, calculated_at)
        counts = {
            "spark_platform_metric_summaries": len(platform_rows),
            "spark_video_follower_contributions": len(contribution_rows),
        }
        write_mode = os.environ.get("SPARK_MYSQL_WRITE_MODE", "append")

    return {
        "mode": "dry-run",
        "counts": counts,
        "executionPlan": build_spark_static_plan(False, counts, write_mode),
    }


def kafka_closed_loop_plan(data_file: Path, run_id: str) -> dict[str, Any]:
    data = load_mock(data_file)
    events = build_events(data)
    counts = event_counts(events)
    calculated_at = datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()
    platform_rows = aggregate_platform_metrics(events, run_id, calculated_at)
    contribution_rows = aggregate_video_contributions(events, run_id, calculated_at)
    spark_rows = {
        "spark_platform_metric_summaries": len(platform_rows),
        "spark_video_follower_contributions": len(contribution_rows),
    }
    from kafka_tools.run_closed_loop import build_execution_plan as build_kafka_plan

    return {
        "mode": "dry-run",
        "producedEvents": len(events),
        "eventCounts": counts,
        "sparkRows": spark_rows,
        "executionPlan": build_kafka_plan(False, counts, spark_rows),
    }


def full_pipeline_streaming_plan(env_file: Path) -> dict[str, Any]:
    from kafka_tools.check_connectivity import load_env_file

    with preserved_environment():
        load_env_file(env_file)
        config = load_streaming_config()
        result = dry_run_summary(config)

    return {
        "mode": result["mode"],
        "kafka": result["kafka"],
        "mysql": result["mysql"],
        "schemaFields": result["schemaFields"],
        "executionPlan": result["executionPlan"],
    }


def build_report(
    env_file: Path = DEFAULT_ENV_PATH,
    data_file: Path = DEFAULT_DATA_PATH,
    run_id: str = DEFAULT_RUN_ID,
    stage: str = "all",
) -> dict[str, Any]:
    all_plans = {
        "localMysql": safe_plan("localMysql", lambda: local_mysql_plan(env_file, data_file)),
        "sparkJdbcStatic": safe_plan("sparkJdbcStatic", lambda: spark_jdbc_static_plan(env_file, data_file, run_id)),
        "kafkaClosedLoop": safe_plan("kafkaClosedLoop", lambda: kafka_closed_loop_plan(data_file, run_id)),
        "fullPipelineStreaming": safe_plan("fullPipelineStreaming", lambda: full_pipeline_streaming_plan(env_file)),
    }
    plans = {key: all_plans[key] for key in STAGE_PLAN_KEYS[stage]}
    failed = [name for name, plan in plans.items() if plan["status"] != "ok"]
    return {
        "status": "ok" if not failed else "partial",
        "mode": "dry-run",
        "stage": stage,
        "failedPlans": failed,
        "safety": {
            "willWriteMySQL": False,
            "willConnectKafka": False,
            "willStartStreaming": False,
        },
        "plans": plans,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Report read-only real-service execution plans")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output", type=Path, help="Optional path to write the JSON report.")
    parser.add_argument(
        "--stage",
        choices=sorted(STAGE_PLAN_KEYS),
        default="all",
        help="Limit the report to one real-service rollout stage.",
    )
    args = parser.parse_args()

    report = build_report(args.env_file, args.data, args.run_id, args.stage)
    write_json_report(report, args.output)
    print(format_json_report(report))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
