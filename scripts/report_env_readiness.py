"""Report redacted local .env readiness for CreatorPulse real-service phases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.preflight import (  # noqa: E402
    DEFAULT_ENV_PATH,
    KAFKA_ENV_KEYS,
    MYSQL_ENV_KEYS,
    PLACEHOLDER_VALUES,
    SPARK_ENV_KEYS,
    load_env,
)
from scripts.report_output import format_json_report, write_json_report  # noqa: E402


SECRET_KEY_PARTS = ("PASSWORD", "SECRET", "TOKEN", "KEY")

OPTIONAL_STAGE_KEYS = {
    "sparkJdbc": ["SPARK_MYSQL_WRITE_MODE", "CREATORPULSE_RUN_SPARK_JDBC_LIVE"],
    "kafka": ["KAFKA_TEST_TIMEOUT_SECONDS", "CREATORPULSE_RUN_KAFKA_LIVE"],
    "fullPipeline": [
        "SPARK_STREAM_TRIGGER_SECONDS",
        "SPARK_STREAM_CHECKPOINT_DIR",
        "SPARK_STREAM_OUTPUT_MODE",
        "CREATORPULSE_RUN_FULL_PIPELINE_LIVE",
    ],
}

STAGE_DEFINITIONS = {
    "localMysql": {
        "description": "Local MySQL schema setup, mock import, and Flask MySQL data source",
        "requiredKeys": MYSQL_ENV_KEYS,
        "optionalKeys": [],
    },
    "sparkJdbc": {
        "description": "Spark JDBC write into MySQL result tables",
        "requiredKeys": SPARK_ENV_KEYS,
        "optionalKeys": OPTIONAL_STAGE_KEYS["sparkJdbc"],
    },
    "kafka": {
        "description": "Windows host to VM Kafka producer and consumer connectivity",
        "requiredKeys": KAFKA_ENV_KEYS,
        "optionalKeys": OPTIONAL_STAGE_KEYS["kafka"],
    },
    "fullPipeline": {
        "description": "Kafka -> Spark Streaming -> MySQL full pipeline",
        "requiredKeys": MYSQL_ENV_KEYS + SPARK_ENV_KEYS + KAFKA_ENV_KEYS,
        "optionalKeys": OPTIONAL_STAGE_KEYS["sparkJdbc"] + OPTIONAL_STAGE_KEYS["kafka"] + OPTIONAL_STAGE_KEYS["fullPipeline"],
    },
}


def is_secret_key(key: str) -> bool:
    upper_key = key.upper()
    return any(part in upper_key for part in SECRET_KEY_PARTS)


def redact_value(key: str, value: str | None) -> str | None:
    if value is None:
        return None
    if is_secret_key(key):
        return "***"
    return value


def key_status(key: str, values: dict[str, str], required: bool) -> dict[str, Any]:
    value = values.get(key)
    missing = value is None or value == ""
    placeholder = bool(value in PLACEHOLDER_VALUES)
    if missing:
        status = "missing" if required else "not-set"
    elif placeholder:
        status = "placeholder"
    else:
        status = "configured"

    return {
        "key": key,
        "status": status,
        "required": required,
        "isSecret": is_secret_key(key),
        "value": redact_value(key, value),
    }


def build_stage_report(stage: str, values: dict[str, str]) -> dict[str, Any]:
    definition = STAGE_DEFINITIONS[stage]
    required = [key_status(key, values, True) for key in definition["requiredKeys"]]
    optional = [key_status(key, values, False) for key in definition["optionalKeys"]]
    blocking = [item["key"] for item in required if item["status"] in {"missing", "placeholder"}]
    return {
        "stage": stage,
        "description": definition["description"],
        "status": "ready-for-strict-preflight" if not blocking else "needs-values",
        "blockingKeys": blocking,
        "required": required,
        "optional": optional,
    }


def build_report(env_file: Path = DEFAULT_ENV_PATH) -> dict[str, Any]:
    values = load_env(env_file)
    stages = {stage: build_stage_report(stage, values) for stage in STAGE_DEFINITIONS}
    blocking_by_stage = {stage: report["blockingKeys"] for stage, report in stages.items() if report["blockingKeys"]}
    return {
        "status": "ready-for-strict-preflight" if not blocking_by_stage else "needs-values",
        "envFile": str(env_file),
        "envFileExists": env_file.exists(),
        "safety": {
            "redactsSecrets": True,
            "doesNetworkChecks": False,
            "writesExternalServices": False,
        },
        "blockingByStage": blocking_by_stage,
        "stages": stages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Report redacted .env readiness for CreatorPulse real-service phases")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--output", type=Path, help="Optional path to write the JSON report.")
    args = parser.parse_args()

    report = build_report(args.env_file)
    write_json_report(report, args.output)
    print(format_json_report(report))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
