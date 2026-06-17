"""Report the guarded checklist before CreatorPulse real-service execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.preflight import DEFAULT_ENV_PATH  # noqa: E402
from scripts.report_output import format_json_report, write_json_report  # noqa: E402
from scripts.run_real_service_sequence import build_sequence_plan  # noqa: E402
from scripts.status_mvp import build_status  # noqa: E402


STAGE_TO_PREFLIGHT_TARGET = {
    "mysql": "localMysql",
    "spark-jdbc": "sparkJdbc",
    "kafka": "kafka",
    "full-pipeline": "fullPipeline",
}

STAGE_TO_ENV_TARGET = {
    "mysql": "localMysql",
    "spark-jdbc": "sparkJdbc",
    "kafka": "kafka",
    "full-pipeline": "fullPipeline",
}

STAGE_EXECUTION_GATES = {
    "mysql": [
        "Run local-mysql strict preflight with zero warnings.",
        "Only then run scripts/setup_local_mysql.py --execute.",
    ],
    "spark-jdbc": [
        "Complete MySQL import first.",
        "Set CREATORPULSE_RUN_SPARK_JDBC_LIVE=1 only for the optional live test.",
    ],
    "kafka": [
        "Confirm VM Kafka advertised.listeners, firewall, and port reachability.",
        "Set CREATORPULSE_RUN_KAFKA_LIVE=1 only for the optional live test.",
    ],
    "full-pipeline": [
        "Complete MySQL import, Spark JDBC live check, and Kafka live check first.",
        "Set CREATORPULSE_RUN_FULL_PIPELINE_LIVE=1 only before starting streaming writes.",
    ],
}

CHECKLIST_STAGES = ["mysql", "spark-jdbc", "kafka", "full-pipeline"]


def preflight_summary_for_stage(status: dict[str, Any], stage: str) -> dict[str, Any]:
    target = STAGE_TO_PREFLIGHT_TARGET[stage]
    return status["preflight"][target]["summary"]


def env_report_for_stage(status: dict[str, Any], stage: str) -> dict[str, Any]:
    target = STAGE_TO_ENV_TARGET[stage]
    return status["envReadiness"]["stages"][target]


def blocking_preflight_checks(status: dict[str, Any], stage: str) -> list[dict[str, str]]:
    target = STAGE_TO_PREFLIGHT_TARGET[stage]
    return [
        item
        for item in status["preflight"][target]["checks"]
        if item["status"] in {"warning", "error"}
    ]


def build_stage_checklist(status: dict[str, Any], stage: str) -> dict[str, Any]:
    env_report = env_report_for_stage(status, stage)
    preflight_summary = preflight_summary_for_stage(status, stage)
    plan = build_sequence_plan(stage=stage)
    env_blocking = env_report["blockingKeys"]
    preflight_blocking = blocking_preflight_checks(status, stage)
    ready_for_strict_preflight = not env_blocking
    ready_for_execute = ready_for_strict_preflight and preflight_summary["counts"]["warning"] == 0 and preflight_summary["counts"]["error"] == 0

    return {
        "stage": stage,
        "status": "ready-for-execute" if ready_for_execute else "blocked",
        "readyForStrictPreflight": ready_for_strict_preflight,
        "readyForExecute": ready_for_execute,
        "envBlockingKeys": env_blocking,
        "preflightSummary": preflight_summary,
        "preflightBlockingChecks": preflight_blocking,
        "manualGates": STAGE_EXECUTION_GATES[stage],
        "prerequisites": plan["prerequisites"],
        "steps": plan["steps"],
    }


def build_checklist(env_file: Path = DEFAULT_ENV_PATH, stage: str = "all") -> dict[str, Any]:
    status = build_status(env_file)
    selected_stages = CHECKLIST_STAGES if stage == "all" else [stage]
    stages = {
        stage: build_stage_checklist(status, stage)
        for stage in selected_stages
    }
    ready_stages = [stage for stage, checklist in stages.items() if checklist["readyForExecute"]]
    blocked_stages = [stage for stage, checklist in stages.items() if not checklist["readyForExecute"]]
    return {
        "status": "ready-for-execute" if not blocked_stages else "blocked",
        "mode": "dry-run",
        "stage": stage,
        "safety": {
            "willWriteMySQL": False,
            "willConnectKafka": False,
            "willStartStreaming": False,
        },
        "nextRecommendedStep": status["nextRecommendedStep"],
        "nextRolloutStage": status["nextRolloutStage"],
        "readyStages": ready_stages,
        "blockedStages": blocked_stages,
        "stages": stages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Report real-service execution checklist without executing anything")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--output", type=Path, help="Optional path to write the JSON report.")
    parser.add_argument(
        "--stage",
        choices=["all", *CHECKLIST_STAGES],
        default="all",
        help="Limit the checklist to one real-service rollout stage.",
    )
    args = parser.parse_args()

    checklist = build_checklist(args.env_file, args.stage)
    write_json_report(checklist, args.output)
    print(format_json_report(checklist))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
