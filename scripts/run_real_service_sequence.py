"""Print the safe real-service execution sequence for CreatorPulse MVP.

Default mode is a dry-run plan. It does not write MySQL, connect Kafka, or start
Spark streaming. The goal is to keep the real-service rollout order executable
and machine-checkable instead of only documented in README.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]


REAL_SERVICE_STEPS = [
    {
        "name": "localMysqlPreflight",
        "command": "python scripts\\preflight.py --target local-mysql --strict",
        "purpose": "Verify local MySQL TCP, credentials, and login before creating or importing data.",
    },
    {
        "name": "localMysqlImport",
        "command": "python scripts\\setup_local_mysql.py --execute",
        "purpose": "Apply schema, import mock rows, verify MySQL row counts, and verify API contract in MySQL mode.",
    },
    {
        "name": "sparkJdbcPreflight",
        "command": "python scripts\\preflight.py --target spark-jdbc --strict",
        "purpose": "Verify spark-submit, JDBC config, MySQL login, and append write mode before Spark writes.",
    },
    {
        "name": "sparkJdbcLiveTest",
        "command": "$env:CREATORPULSE_RUN_SPARK_JDBC_LIVE='1'; python spark_jobs\\tests\\test_static_mysql_jdbc_integration.py",
        "purpose": "Run the opt-in Spark JDBC live write test.",
    },
    {
        "name": "kafkaPreflight",
        "command": "python scripts\\preflight.py --target kafka --strict",
        "purpose": "Verify VM Kafka bootstrap shape and TCP reachability.",
    },
    {
        "name": "kafkaLiveTest",
        "command": "$env:CREATORPULSE_RUN_KAFKA_LIVE='1'; python kafka_tools\\tests\\test_kafka_live_integration.py",
        "purpose": "Run the opt-in Kafka produce/consume live test.",
    },
    {
        "name": "fullPipelinePreflight",
        "command": "python scripts\\preflight.py --target full-pipeline --strict",
        "purpose": "Verify combined Kafka, Spark JDBC, MySQL, streaming mode, and database-name alignment.",
    },
    {
        "name": "fullPipelineStreaming",
        "command": "$env:CREATORPULSE_RUN_FULL_PIPELINE_LIVE='1'; spark-submit spark_jobs\\kafka_streaming_to_mysql.py --execute",
        "purpose": "Start the long-running Kafka -> Spark -> MySQL streaming write job.",
    },
]

STAGE_STEP_NAMES = {
    "all": [step["name"] for step in REAL_SERVICE_STEPS],
    "mysql": ["localMysqlPreflight", "localMysqlImport"],
    "spark-jdbc": ["sparkJdbcPreflight", "sparkJdbcLiveTest"],
    "kafka": ["kafkaPreflight", "kafkaLiveTest"],
    "full-pipeline": ["fullPipelinePreflight", "fullPipelineStreaming"],
}

STAGE_PREREQUISITES = {
    "all": [
        "Fill .env values only when moving from dry-run into real execution.",
        "Run each strict preflight immediately before its matching live step.",
    ],
    "mysql": [
        "Fill MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE, MYSQL_USER, and MYSQL_PASSWORD in .env.",
    ],
    "spark-jdbc": [
        "Complete the MySQL import first.",
        "Fill SPARK_MYSQL_JDBC_URL, SPARK_MYSQL_USER, SPARK_MYSQL_PASSWORD, and SPARK_MYSQL_DRIVER in .env.",
    ],
    "kafka": [
        "Confirm the VM Kafka IP, port, firewall, and advertised.listeners before live produce/consume.",
        "Fill KAFKA_BOOTSTRAP_SERVERS in .env.",
    ],
    "full-pipeline": [
        "MySQL import, Spark JDBC live check, and Kafka live check must succeed first.",
        "Run full-pipeline strict preflight before enabling streaming writes.",
    ],
}


def steps_for_stage(stage: str) -> list[dict[str, str]]:
    selected_names = set(STAGE_STEP_NAMES[stage])
    return [step for step in REAL_SERVICE_STEPS if step["name"] in selected_names]


def build_sequence_plan(execute: bool = False, stage: str = "all") -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": "execute" if execute else "dry-run",
        "stage": stage,
        "message": "Dry-run only; commands are not executed." if not execute else "Execution mode is not implemented yet.",
        "prerequisites": STAGE_PREREQUISITES[stage],
        "steps": [{**step, "willExecute": False} for step in steps_for_stage(stage)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Show the CreatorPulse real-service rollout sequence")
    parser.add_argument(
        "--stage",
        choices=sorted(STAGE_STEP_NAMES),
        default="all",
        help="Limit the dry-run plan to one rollout stage",
    )
    parser.add_argument("--execute", action="store_true", help="Reserved for a future explicit orchestrated execution mode")
    args = parser.parse_args()

    if args.execute:
        print(json.dumps(build_sequence_plan(execute=True, stage=args.stage), ensure_ascii=False, indent=2))
        raise SystemExit(1)

    print(json.dumps(build_sequence_plan(stage=args.stage), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
