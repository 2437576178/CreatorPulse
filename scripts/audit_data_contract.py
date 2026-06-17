"""Audit the MVP schema, mock import rows, ViewModels, and OpenAPI contract.

This is a dry-run safety check before real MySQL/Kafka/Spark execution. It
answers one practical question: do the fields we plan to store still match the
fields the API and pages expect?
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "api"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from api.openapi_contract import LEGACY_CREATOR_PAGE_ENDPOINTS, PAGE_ENDPOINTS, openapi_schema  # noqa: E402
from api.view_model_contract import VIEW_MODEL_REQUIRED_FIELDS, validate_view_models  # noqa: E402
from database.import_mock_to_mysql import (  # noqa: E402
    TABLE_ORDER,
    build_table_rows,
    load_json,
    row_counts,
    validate_rows,
)
from api.mysql_repository import MySQLRepository  # noqa: E402


DEFAULT_SCHEMA_PATH = ROOT_DIR / "database" / "schema.sql"
AUTO_SCHEMA_COLUMNS = {"created_at", "updated_at"}
NON_COLUMN_PREFIXES = {"CONSTRAINT", "PRIMARY", "UNIQUE", "KEY", "INDEX", "FOREIGN", "ON"}


class DataContractAuditError(RuntimeError):
    """Raised when a dry-run data-contract audit fails."""


def parse_schema_tables(schema_path: Path = DEFAULT_SCHEMA_PATH) -> dict[str, set[str]]:
    sql = schema_path.read_text(encoding="utf-8")
    tables: dict[str, set[str]] = {}
    pattern = re.compile(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+`?([A-Za-z0-9_]+)`?\s*\((.*?)\)\s*ENGINE\s*=",
        re.IGNORECASE | re.DOTALL,
    )

    for match in pattern.finditer(sql):
        table_name = match.group(1)
        columns: set[str] = set()
        for raw_line in match.group(2).splitlines():
            line = raw_line.strip().rstrip(",")
            if not line:
                continue
            first_token = line.split(maxsplit=1)[0].strip("`").upper()
            if first_token in NON_COLUMN_PREFIXES:
                continue
            column_name = line.split(maxsplit=1)[0].strip("`")
            columns.add(column_name)
        tables[table_name] = columns

    if not tables:
        raise DataContractAuditError(f"No CREATE TABLE statements found in {schema_path}")
    return tables


def table_audit_rows(schema_tables: dict[str, set[str]], rows: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    audits: list[dict[str, Any]] = []
    for table in TABLE_ORDER:
        if table not in schema_tables:
            raise DataContractAuditError(f"Schema missing table used by import mapping: {table}")
        table_rows = rows.get(table, [])
        import_columns = set(table_rows[0]) if table_rows else set()
        schema_columns = schema_tables[table]
        required_schema_columns = schema_columns - AUTO_SCHEMA_COLUMNS
        missing_from_schema = sorted(import_columns - schema_columns)
        missing_from_import = sorted(required_schema_columns - import_columns)
        audits.append(
            {
                "name": table,
                "schemaColumnCount": len(schema_columns),
                "importColumnCount": len(import_columns),
                "rowCount": len(table_rows),
                "importColumnsMissingFromSchema": missing_from_schema,
                "requiredSchemaColumnsMissingFromImport": missing_from_import,
            }
        )
    return audits


def validate_openapi_contract(schema: dict[str, Any]) -> None:
    for path, view_model_name in PAGE_ENDPOINTS.items():
        if path not in schema["paths"]:
            raise DataContractAuditError(f"OpenAPI missing path: {path}")
        required = schema["components"]["schemas"][view_model_name]["required"]
        expected = list(VIEW_MODEL_REQUIRED_FIELDS[view_model_name])
        if required != expected:
            raise DataContractAuditError(
                f"OpenAPI required fields drifted for {view_model_name}: expected {expected}, got {required}"
            )


def build_audit_report(schema_path: Path = DEFAULT_SCHEMA_PATH) -> dict[str, Any]:
    data = load_json()
    rows = build_table_rows(data)
    validate_rows(rows)

    schema_tables = parse_schema_tables(schema_path)
    table_audits = table_audit_rows(schema_tables, rows)
    column_errors = [
        {
            "table": item["name"],
            "importColumnsMissingFromSchema": item["importColumnsMissingFromSchema"],
            "requiredSchemaColumnsMissingFromImport": item["requiredSchemaColumnsMissingFromImport"],
        }
        for item in table_audits
        if item["importColumnsMissingFromSchema"] or item["requiredSchemaColumnsMissingFromImport"]
    ]
    if column_errors:
        raise DataContractAuditError(f"Schema/import column drift detected: {json.dumps(column_errors, ensure_ascii=False)}")

    contract = MySQLRepository().to_contract(rows)
    validate_view_models(contract["viewModels"])

    schema = openapi_schema()
    validate_openapi_contract(schema)

    return {
        "status": "ok",
        "schema": {
            "path": str(schema_path),
            "tableCount": len(table_audits),
            "tables": table_audits,
        },
        "mysqlImport": {
            "contractCheck": "ok",
            "rowCounts": row_counts(rows),
        },
        "viewModels": {
            "contractCheck": "ok",
            "names": list(contract["viewModels"]),
        },
        "openapi": {
            "contractCheck": "ok",
            "sessionScopedPagePaths": list(PAGE_ENDPOINTS),
            "legacyCreatorPagePaths": list(LEGACY_CREATOR_PAGE_ENDPOINTS),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit CreatorPulse MVP data-contract coverage")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    args = parser.parse_args()

    try:
        report = build_audit_report(args.schema)
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1) from exc

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
