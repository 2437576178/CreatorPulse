"""Process pending offline recompute requests.

The worker is intentionally small: Flask writes a row into
offline_recompute_requests, and this script picks it up later. That keeps the
Windows API process decoupled from the VM Spark/offline runtime.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT_DIR / ".env"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.import_mock_to_mysql import MySQLConfig, load_env_file  # noqa: E402
from spark_jobs.offline_daily_metrics import (  # noqa: E402
    aggregate_daily_metrics,
    connect_mysql,
    read_mysql_inputs,
    safe_id,
    write_mysql_rows,
)
from spark_jobs.offline_reports import (  # noqa: E402
    build_report_batch_run,
    generate_reports_from_mysql,
    read_mysql_report_inputs,
    write_report_rows,
)


REPORT_TYPES = ["DAILY", "WEEKLY", "MONTHLY"]


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()


def fetch_pending_requests(config: MySQLConfig, limit: int) -> list[dict[str, Any]]:
    connection = connect_mysql(config)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM offline_recompute_requests
                WHERE status = 'PENDING'
                ORDER BY requested_at ASC, request_id ASC
                LIMIT %s
                """,
                [limit],
            )
            return list(cursor.fetchall())
    finally:
        connection.close()


def update_request_status(
    config: MySQLConfig,
    request_id: str,
    status: str,
    batch_run_id: str | None = None,
    error_message: str | None = None,
    mark_started: bool = False,
    mark_finished: bool = False,
) -> None:
    fields = ["status = %s", "batch_run_id = %s", "error_message = %s"]
    values: list[Any] = [status, batch_run_id, error_message]
    if mark_started:
        fields.append("started_at = %s")
        values.append(now_iso())
    if mark_finished:
        fields.append("finished_at = %s")
        values.append(now_iso())
    values.append(request_id)

    connection = connect_mysql(config)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE offline_recompute_requests SET {', '.join(fields)} WHERE request_id = %s",
                values,
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def run_daily_recompute(config: MySQLConfig, request: dict[str, Any], batch_run_id: str) -> dict[str, int]:
    start_date = str(request["period_start"])
    end_date = str(request["period_end"])
    creator_id = request["creator_id"]
    raw_events, videos = read_mysql_inputs(config, start_date, end_date, creator_id)
    metrics = aggregate_daily_metrics(raw_events, videos, batch_run_id, start_date, end_date, creator_id)
    write_mysql_rows(metrics, config)
    return {table: len(rows) for table, rows in metrics.items()}


def run_report_recompute(config: MySQLConfig, request: dict[str, Any], batch_run_id: str) -> dict[str, int]:
    start_date = str(request["period_start"])
    end_date = str(request["period_end"])
    creator_id = request["creator_id"]
    total_reports = 0
    total_inputs = 0
    all_reports = []
    for report_type in REPORT_TYPES:
        daily_metrics, creators = read_mysql_report_inputs(config, start_date, end_date, creator_id)
        reports = generate_reports_from_mysql(
            daily_metrics,
            creators,
            report_type=report_type,
            period_start=start_date,
            period_end=end_date,
            batch_run_id=batch_run_id,
            creator_id=creator_id,
        )
        all_reports.extend(reports)
        total_inputs += len(daily_metrics["offline_creator_daily_metrics"])
        total_reports += len(reports)
    batch_run = build_report_batch_run(
        batch_run_id,
        "ALL",
        start_date,
        end_date,
        input_count=total_inputs,
        output_count=total_reports,
        triggered_by="MANUAL",
    )
    batch_run["job_name"] = "offline_reports_all"
    write_report_rows(batch_run, all_reports, config)
    return {"offline_report_inputs": total_inputs, "creator_reports": total_reports}


def process_request(config: MySQLConfig, request: dict[str, Any]) -> dict[str, Any]:
    request_id = request["request_id"]
    scope = request["recompute_scope"]
    batch_run_id = safe_id("offline_recompute", request_id, now_iso())
    update_request_status(config, request_id, "RUNNING", mark_started=True)

    try:
        counts: dict[str, int] = {}
        if scope in {"CREATOR_DAILY", "PLATFORM_DAILY", "VIDEO_DAILY", "CONTENT_TYPE_DAILY", "ALL"}:
            counts.update(run_daily_recompute(config, request, batch_run_id))
        if scope in {"REPORTS", "ALL"}:
            counts.update(run_report_recompute(config, request, batch_run_id))
        update_request_status(config, request_id, "SUCCESS", batch_run_id=batch_run_id, mark_finished=True)
        return {"requestId": request_id, "status": "SUCCESS", "batchRunId": batch_run_id, "counts": counts}
    except Exception as exc:
        update_request_status(config, request_id, "FAILED", batch_run_id=batch_run_id, error_message=str(exc), mark_finished=True)
        return {"requestId": request_id, "status": "FAILED", "batchRunId": batch_run_id, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Process pending CreatorPulse offline recompute requests")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    load_env_file(args.env_file)
    config = MySQLConfig.from_env()
    requests = fetch_pending_requests(config, max(args.limit, 1))
    results = [process_request(config, request) for request in requests]
    print(json.dumps({"status": "ok", "processed": len(results), "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
