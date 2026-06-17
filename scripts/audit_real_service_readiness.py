"""Audit real-service rollout reports for consistent safe dry-run behavior."""

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
from scripts.report_execution_checklist import build_checklist  # noqa: E402
from scripts.report_output import format_json_report, write_json_report  # noqa: E402
from scripts.report_real_service_plans import build_report as build_plan_report  # noqa: E402
from scripts.run_real_service_sequence import build_sequence_plan  # noqa: E402


CANONICAL_STAGES = ["mysql", "spark-jdbc", "kafka", "full-pipeline"]

EXPECTED_PLAN_KEYS = {
    "mysql": ["localMysql"],
    "spark-jdbc": ["sparkJdbcStatic"],
    "kafka": ["kafkaClosedLoop"],
    "full-pipeline": ["fullPipelineStreaming"],
}

EXPECTED_SEQUENCE_STEPS = {
    "mysql": ["localMysqlPreflight", "localMysqlImport"],
    "spark-jdbc": ["sparkJdbcPreflight", "sparkJdbcLiveTest"],
    "kafka": ["kafkaPreflight", "kafkaLiveTest"],
    "full-pipeline": ["fullPipelinePreflight", "fullPipelineStreaming"],
}

SAFE_FLAGS = {
    "willWriteMySQL",
    "willConnectKafka",
    "willStartStreaming",
}


def unsafe_safety_flags(report: dict[str, Any]) -> list[str]:
    safety = report.get("safety", {})
    return [key for key in SAFE_FLAGS if safety.get(key) is not False]


def unsafe_execution_flags_from_steps(steps: list[dict[str, Any]]) -> list[Any]:
    values = sorted({step.get("willExecute") for step in steps}, key=str)
    return [value for value in values if value is not False]


def unsafe_execution_flags_from_plans(plans: dict[str, Any]) -> list[str]:
    unsafe = []
    for plan_name, plan in plans.items():
        execution_plan = plan.get("executionPlan", {})
        for key in ["willWriteMySQL", "willConnectKafka", "willStartStreaming"]:
            if key in execution_plan and execution_plan[key] is not False:
                unsafe.append(f"{plan_name}.{key}")
    return unsafe


def audit_stage(env_file: Path, stage: str) -> dict[str, Any]:
    sequence = build_sequence_plan(stage=stage)
    plans = build_plan_report(env_file=env_file, stage=stage)
    checklist = build_checklist(env_file=env_file, stage=stage)

    sequence_step_names = [step["name"] for step in sequence["steps"]]
    plan_keys = list(plans["plans"])
    checklist_keys = list(checklist["stages"])
    sequence_will_execute = sorted({step.get("willExecute") for step in sequence["steps"]}, key=str)

    failures = []
    if sequence.get("mode") != "dry-run":
        failures.append("sequence mode is not dry-run")
    if plans.get("mode") != "dry-run":
        failures.append("plans mode is not dry-run")
    if checklist.get("mode") != "dry-run":
        failures.append("checklist mode is not dry-run")
    if sequence_step_names != EXPECTED_SEQUENCE_STEPS[stage]:
        failures.append("sequence stage filter returned unexpected steps")
    if plan_keys != EXPECTED_PLAN_KEYS[stage]:
        failures.append("plan stage filter returned unexpected plans")
    if checklist_keys != [stage]:
        failures.append("checklist stage filter returned unexpected stages")

    sequence_unsafe = unsafe_execution_flags_from_steps(sequence["steps"])
    plan_report_unsafe = unsafe_safety_flags(plans)
    plan_execution_unsafe = unsafe_execution_flags_from_plans(plans["plans"])
    checklist_unsafe = unsafe_safety_flags(checklist)
    checklist_execution_unsafe = unsafe_execution_flags_from_steps(
        step
        for stage_report in checklist["stages"].values()
        for step in stage_report["steps"]
    )
    if sequence_unsafe:
        failures.append("sequence contains executable steps")
    if plan_report_unsafe or plan_execution_unsafe:
        failures.append("plans contain unsafe execution flags")
    if checklist_unsafe or checklist_execution_unsafe:
        failures.append("checklist contains unsafe execution flags")

    return {
        "stage": stage,
        "failures": failures,
        "sequence": {
            "stage": sequence["stage"],
            "mode": sequence["mode"],
            "stepNames": sequence_step_names,
            "willExecuteValues": sequence_will_execute,
            "unsafeFlags": sequence_unsafe,
        },
        "plans": {
            "stage": plans["stage"],
            "mode": plans["mode"],
            "planKeys": plan_keys,
            "unsafeFlags": plan_report_unsafe + plan_execution_unsafe,
        },
        "checklist": {
            "stage": checklist["stage"],
            "mode": checklist["mode"],
            "checklistKeys": checklist_keys,
            "unsafeFlags": checklist_unsafe + checklist_execution_unsafe,
        },
    }


def build_audit(env_file: Path = DEFAULT_ENV_PATH, stage: str = "all") -> dict[str, Any]:
    selected_stages = CANONICAL_STAGES if stage == "all" else [stage]
    stages = {stage_name: audit_stage(env_file, stage_name) for stage_name in selected_stages}
    failed_checks = [
        f"{stage_name}: {failure}"
        for stage_name, stage_report in stages.items()
        for failure in stage_report["failures"]
    ]
    return {
        "status": "ok" if not failed_checks else "failed",
        "mode": "dry-run",
        "stage": stage,
        "canonicalStages": CANONICAL_STAGES,
        "summary": {
            "checkedStages": selected_stages,
            "failedChecks": failed_checks,
        },
        "safety": {
            "willWriteMySQL": False,
            "willConnectKafka": False,
            "willStartStreaming": False,
        },
        "stages": stages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit real-service dry-run readiness reports")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--output", type=Path, help="Optional path to write the JSON report.")
    parser.add_argument(
        "--stage",
        choices=["all", *CANONICAL_STAGES],
        default="all",
        help="Limit the audit to one rollout stage.",
    )
    args = parser.parse_args()

    audit = build_audit(args.env_file, args.stage)
    write_json_report(audit, args.output)
    print(format_json_report(audit))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
