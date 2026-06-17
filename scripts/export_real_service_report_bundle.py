"""Export a local bundle of real-service readiness reports.

The bundle is a read-only artifact pack for review before real MySQL, Spark, or
Kafka execution. It does not write external services, connect Kafka, or start
Spark Streaming.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.audit_real_service_readiness import CANONICAL_STAGES, build_audit  # noqa: E402
from scripts.preflight import DEFAULT_ENV_PATH  # noqa: E402
from scripts.report_env_readiness import build_report as build_env_readiness_report  # noqa: E402
from scripts.report_execution_checklist import build_checklist  # noqa: E402
from scripts.report_output import format_json_report, write_json_report  # noqa: E402
from scripts.report_real_service_plans import DEFAULT_DATA_PATH, DEFAULT_RUN_ID, build_report as build_plan_report  # noqa: E402
from scripts.run_real_service_sequence import build_sequence_plan  # noqa: E402
from scripts.status_mvp import build_status  # noqa: E402


DEFAULT_OUTPUT_DIR = ROOT_DIR / "reports" / "real-service-readiness-bundle"

REPORT_FILES = {
    "status": "status.json",
    "envReadiness": "env-readiness.json",
    "sequence": "sequence.json",
    "executionPlans": "execution-plans.json",
    "executionChecklist": "execution-checklist.json",
    "readinessAudit": "readiness-audit.json",
}


def dry_run_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {"mode": "dry-run", **payload}


def report_entry(name: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "path": str(path),
        "mode": payload["mode"],
        "status": payload.get("status", "unknown"),
    }


def build_reports(env_file: Path, data_file: Path, run_id: str, stage: str) -> dict[str, dict[str, Any]]:
    return {
        "status": dry_run_payload(build_status(env_file)),
        "envReadiness": dry_run_payload(build_env_readiness_report(env_file)),
        "sequence": build_sequence_plan(stage=stage),
        "executionPlans": build_plan_report(env_file=env_file, data_file=data_file, run_id=run_id, stage=stage),
        "executionChecklist": build_checklist(env_file=env_file, stage=stage),
        "readinessAudit": build_audit(env_file=env_file, stage=stage),
    }


def build_bundle(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    env_file: Path = DEFAULT_ENV_PATH,
    data_file: Path = DEFAULT_DATA_PATH,
    run_id: str = DEFAULT_RUN_ID,
    stage: str = "all",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = build_reports(env_file, data_file, run_id, stage)
    report_entries = []

    for name, payload in reports.items():
        path = output_dir / REPORT_FILES[name]
        write_json_report(payload, path)
        report_entries.append(report_entry(name, path, payload))

    failed_reports = [
        entry["name"]
        for entry in report_entries
        if entry["status"] not in {"ok", "ready-for-dry-run", "needs-values", "blocked"}
    ]
    manifest = {
        "status": "ok" if not failed_reports else "partial",
        "mode": "dry-run",
        "stage": stage,
        "outputDir": str(output_dir),
        "failedReports": failed_reports,
        "safety": {
            "willWriteMySQL": False,
            "willConnectKafka": False,
            "willStartStreaming": False,
        },
        "reports": report_entries,
    }
    write_json_report(manifest, output_dir / "manifest.json")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a read-only real-service readiness report bundle")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--stage",
        choices=["all", *CANONICAL_STAGES],
        default="all",
        help="Limit stage-aware reports to one rollout stage.",
    )
    args = parser.parse_args()

    manifest = build_bundle(
        output_dir=args.output_dir,
        env_file=args.env_file,
        data_file=args.data,
        run_id=args.run_id,
        stage=args.stage,
    )
    print(format_json_report(manifest))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
