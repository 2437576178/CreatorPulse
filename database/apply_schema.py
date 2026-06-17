"""Apply the CreatorPulse MVP MySQL schema.

Default mode is dry-run: parse and validate schema statements without
connecting to MySQL. Use --execute after filling .env to create tables.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from import_mock_to_mysql import DEFAULT_ENV_PATH, ImportConfigError, MySQLConfig, load_env_file


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = ROOT_DIR / "database" / "schema.sql"


class SchemaError(RuntimeError):
    """Raised when schema SQL cannot be parsed or executed."""


def strip_line_comment(line: str) -> str:
    line = line.lstrip("\ufeff")
    stripped = line.lstrip()
    if stripped.startswith("--"):
        return ""
    return line


def split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False
    escape_next = False

    for raw_line in sql.splitlines():
        line = strip_line_comment(raw_line)
        if not line.strip():
            continue

        for char in line:
            current.append(char)
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
                continue
            if char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
                continue
            if char == ";" and not in_single_quote and not in_double_quote:
                statement = "".join(current).strip().rstrip(";").strip()
                if statement:
                    statements.append(statement)
                current = []
        current.append("\n")

    trailing = "".join(current).strip()
    if trailing:
        raise SchemaError("Schema SQL has a trailing statement without semicolon")

    return statements


def validate_schema_statements(statements: list[str]) -> None:
    if not statements:
        raise SchemaError("Schema SQL contains no executable statements")

    required_prefixes = [
        "CREATE DATABASE IF NOT EXISTS",
        "USE ",
        "CREATE TABLE IF NOT EXISTS creators",
        "CREATE TABLE IF NOT EXISTS users",
        "CREATE TABLE IF NOT EXISTS platform_accounts",
        "CREATE TABLE IF NOT EXISTS videos",
        "CREATE TABLE IF NOT EXISTS video_metric_snapshots",
        "CREATE TABLE IF NOT EXISTS video_traffic_source_metrics",
        "CREATE TABLE IF NOT EXISTS creator_metric_snapshots",
        "CREATE TABLE IF NOT EXISTS audience_profile_snapshots",
        "CREATE TABLE IF NOT EXISTS topic_trend_snapshots",
        "CREATE TABLE IF NOT EXISTS insights",
        "CREATE TABLE IF NOT EXISTS insight_evidence_metrics",
        "CREATE TABLE IF NOT EXISTS recommended_actions",
        "CREATE TABLE IF NOT EXISTS spark_platform_metric_summaries",
        "CREATE TABLE IF NOT EXISTS spark_video_follower_contributions",
    ]
    normalized = [" ".join(statement.split()) for statement in statements]
    normalized_prefixes = [" ".join(prefix.split()) for prefix in required_prefixes]
    missing = [
        prefix
        for prefix in normalized_prefixes
        if not any(statement.startswith(prefix) for statement in normalized)
    ]
    if missing:
        raise SchemaError(f"Schema SQL missing required statements: {', '.join(missing)}")

    destructive = ["DROP TABLE", "DROP DATABASE", "TRUNCATE", "DELETE FROM"]
    for statement in normalized:
        upper = statement.upper()
        if any(token in upper for token in destructive):
            raise SchemaError(f"Schema SQL contains destructive statement: {statement[:80]}")


def load_schema_statements(path: Path = DEFAULT_SCHEMA_PATH) -> list[str]:
    if not path.exists():
        raise SchemaError(f"Schema file not found: {path}")
    statements = split_sql_statements(path.read_text(encoding="utf-8"))
    validate_schema_statements(statements)
    return statements


def apply_schema(statements: list[str], config: MySQLConfig) -> None:
    try:
        import pymysql
    except ImportError as exc:
        raise ImportConfigError("PyMySQL is not installed. Run: pip install -r requirements.txt") from exc

    connection = pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
    finally:
        connection.close()


def statement_counts(statements: list[str]) -> dict[str, int]:
    return {
        "total": len(statements),
        "createDatabase": sum(1 for statement in statements if statement.upper().startswith("CREATE DATABASE")),
        "useDatabase": sum(1 for statement in statements if statement.upper().startswith("USE ")),
        "createTables": sum(1 for statement in statements if statement.upper().startswith("CREATE TABLE")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply CreatorPulse MVP MySQL schema")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--execute", action="store_true", help="Actually execute schema SQL against MySQL")
    args = parser.parse_args()

    statements = load_schema_statements(args.schema)
    mode = "dry-run"
    if args.execute:
        load_env_file(args.env_file)
        config = MySQLConfig.from_env()
        apply_schema(statements, config)
        mode = "mysql-schema"

    print(json.dumps({"status": "ok", "mode": mode, "counts": statement_counts(statements)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
