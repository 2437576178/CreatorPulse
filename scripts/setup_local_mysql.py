"""Prepare local MySQL for the CreatorPulse MVP.

Default mode is dry-run: validate preflight, schema parsing, mock row mapping,
and MySQL repository contract mapping without connecting to MySQL. Use
--execute after filling .env to apply schema, import mock rows, and verify the
Flask API through the MySQL repository.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "api"
DATABASE_DIR = ROOT_DIR / "database"

for path in [str(API_DIR), str(DATABASE_DIR), str(ROOT_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

from app import create_app  # noqa: E402
from apply_schema import apply_schema, load_schema_statements, statement_counts  # noqa: E402
from import_mock_to_mysql import (  # noqa: E402
    DEFAULT_DATA_PATH,
    DEFAULT_ENV_PATH,
    MySQLConfig,
    build_table_rows,
    load_env_file,
    load_json,
    row_counts,
    validate_rows,
    write_mysql,
)
from mysql_repository import MySQLRepository  # noqa: E402
from repository import clear_repository_cache  # noqa: E402
from scripts.preflight import run_checks, summarize  # noqa: E402


API_ENDPOINTS = [
    "/api/health",
    "/api/creators/demo/dashboard/growth",
    "/api/creators/demo/fans",
    "/api/creators/demo/videos",
    "/api/creators/demo/distribution",
    "/api/creators/demo/opportunities",
    "/api/creators/demo/profile",
]

MYSQL_SETUP_STEPS = [
    "local-mysql strict preflight",
    "apply schema statements",
    "upsert mock rows",
    "verify MySQL row counts",
    "verify Flask API in mysql mode",
]


def fail_on_preflight_errors(results: list[Any], strict: bool) -> None:
    summary = summarize(results)
    if summary["counts"]["error"] > 0 or (strict and summary["counts"]["warning"] > 0):
        raise RuntimeError("Local MySQL preflight failed; run scripts/preflight.py --target local-mysql for details")


def verify_mysql_api() -> dict[str, int]:
    previous_source = os.environ.get("CREATORPULSE_DATA_SOURCE")
    os.environ["CREATORPULSE_DATA_SOURCE"] = "mysql"
    clear_repository_cache()

    try:
        app = create_app()
        client = app.test_client()
        statuses: dict[str, int] = {}
        for endpoint in API_ENDPOINTS:
            response = client.get(endpoint)
            statuses[endpoint] = response.status_code
            if response.status_code != 200:
                payload = response.get_json(silent=True)
                raise RuntimeError(f"MySQL API verification failed for {endpoint}: {response.status_code} {payload}")
        return statuses
    finally:
        if previous_source is None:
            os.environ.pop("CREATORPULSE_DATA_SOURCE", None)
        else:
            os.environ["CREATORPULSE_DATA_SOURCE"] = previous_source
        clear_repository_cache()


def dry_run_contract_check(rows: dict[str, list[dict[str, Any]]]) -> None:
    contract = MySQLRepository().to_contract(rows)
    required = ["growthDashboard", "fansAnalysis", "videoAnalysis", "contentDistribution", "opportunities", "profile"]
    missing = [key for key in required if key not in contract["viewModels"]]
    if missing:
        raise RuntimeError(f"MySQL dry-run contract missing view models: {', '.join(missing)}")


def pymysql_connect(config: MySQLConfig):
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("PyMySQL is not installed. Run: pip install -r requirements.txt") from exc

    return pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.database,
        charset="utf8mb4",
        connect_timeout=3,
        read_timeout=3,
        write_timeout=3,
        autocommit=True,
    )


def verify_mysql_row_counts(expected_counts: dict[str, int], config: MySQLConfig) -> dict[str, int]:
    connection = pymysql_connect(config)
    actual_counts: dict[str, int] = {}
    try:
        with connection.cursor() as cursor:
            for table, expected in expected_counts.items():
                cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                row = cursor.fetchone()
                actual = int(row[0])
                actual_counts[table] = actual
                if actual != expected:
                    raise RuntimeError(f"MySQL row count mismatch for {table}: expected {expected}, got {actual}")
    finally:
        connection.close()

    return actual_counts


def build_execution_plan(execute: bool, schema: dict[str, int], rows: dict[str, int]) -> dict[str, Any]:
    return {
        "willWriteMySQL": execute,
        "requiresStrictPreflight": True,
        "steps": MYSQL_SETUP_STEPS,
        "schemaStatements": schema["total"],
        "targetTables": len(rows),
        "plannedRows": rows,
    }


def run_setup(env_file: Path, data_file: Path, execute: bool, strict_preflight: bool) -> dict[str, Any]:
    load_env_file(env_file)
    preflight = run_checks(env_file, target="local-mysql")
    effective_strict = strict_preflight or execute
    fail_on_preflight_errors(preflight, effective_strict)

    statements = load_schema_statements()
    data = load_json(data_file)
    rows = build_table_rows(data)
    validate_rows(rows)

    payload: dict[str, Any] = {
        "status": "ok",
        "mode": "mysql-setup" if execute else "dry-run",
        "preflight": summarize(preflight),
        "schema": statement_counts(statements),
        "rows": row_counts(rows),
    }
    payload["executionPlan"] = build_execution_plan(execute, payload["schema"], payload["rows"])

    if execute:
        config = MySQLConfig.from_env()
        apply_schema(statements, config)
        write_mysql(rows, config)
        payload["mysqlRowCounts"] = verify_mysql_row_counts(payload["rows"], config)
        payload["apiStatusCodes"] = verify_mysql_api()
    else:
        dry_run_contract_check(rows)
        payload["contractCheck"] = "ok"

    payload["preflightChecks"] = [asdict(item) for item in preflight]
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare local MySQL for CreatorPulse MVP")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--execute", action="store_true", help="Apply schema, import mock rows, and verify MySQL API")
    parser.add_argument("--strict-preflight", action="store_true", help="Fail on preflight warnings")
    args = parser.parse_args()

    try:
        result = run_setup(args.env_file, args.data, args.execute, args.strict_preflight)
    except Exception as exc:  # noqa: BLE001 - CLI should return structured setup failure details.
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1) from None

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
