"""CreatorPulse local environment preflight checks.

Preflight reports whether the local machine is ready for the MVP paths. By
default, optional external services such as MySQL and VM Kafka produce warnings
instead of failing. Use --strict to fail on warnings.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT_DIR / ".env"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

MYSQL_ENV_KEYS = [
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_DATABASE",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
]

SPARK_ENV_KEYS = [
    "SPARK_MYSQL_JDBC_URL",
    "SPARK_MYSQL_USER",
    "SPARK_MYSQL_PASSWORD",
    "SPARK_MYSQL_DRIVER",
]
SPARK_ALLOWED_WRITE_MODES = {"append"}
SPARK_STREAM_ALLOWED_OUTPUT_MODES = {"append", "update"}

KAFKA_ENV_KEYS = [
    "KAFKA_BOOTSTRAP_SERVERS",
]

REQUIRED_ENV_KEYS = MYSQL_ENV_KEYS + SPARK_ENV_KEYS + KAFKA_ENV_KEYS

PLACEHOLDER_VALUES = {"your_user", "your_password", "192.168.56.10:9092"}


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    message: str


def load_env(path: Path = DEFAULT_ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def check_command(name: str, command: str, required: bool = True) -> CheckResult:
    path = shutil.which(command)
    if path:
        return CheckResult(name, "ok", path)
    status = "error" if required else "warning"
    return CheckResult(name, status, f"{command} not found on PATH")


def check_file(name: str, path: Path) -> CheckResult:
    if path.exists():
        return CheckResult(name, "ok", str(path))
    return CheckResult(name, "error", f"Missing file: {path}")


def check_env_file(path: Path = DEFAULT_ENV_PATH) -> CheckResult:
    if path.exists():
        return CheckResult("env file", "ok", str(path))
    return CheckResult("env file", "warning", ".env not found; copy .env.example before real MySQL/Kafka execution")


def check_env_values(values: dict[str, str], keys: list[str] | None = None) -> list[CheckResult]:
    results = []
    for key in keys or REQUIRED_ENV_KEYS:
        value = values.get(key)
        if not value:
            results.append(CheckResult(f"env {key}", "warning", "missing; required for real external execution"))
        elif value in PLACEHOLDER_VALUES:
            results.append(CheckResult(f"env {key}", "warning", "placeholder value still present"))
        else:
            results.append(CheckResult(f"env {key}", "ok", "configured"))
    return results


def parse_host_port(value: str) -> tuple[str, int] | None:
    if not value or ":" not in value:
        return None
    host, port_text = value.rsplit(":", 1)
    try:
        return host, int(port_text)
    except ValueError:
        return None


def parse_jdbc_database_name(value: str) -> str | None:
    prefix = "jdbc:mysql://"
    if not value.startswith(prefix):
        return None
    path = value[len(prefix) :].split("/", 1)
    if len(path) != 2:
        return None
    database = path[1].split("?", 1)[0].strip()
    return database or None


def can_connect(host: str, port: int, timeout_seconds: float = 0.35) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_seconds)
        return sock.connect_ex((host, port)) == 0


def check_tcp(name: str, host: str | None, port: int | None) -> CheckResult:
    if not host or port is None:
        return CheckResult(name, "warning", "host/port not configured")
    if can_connect(host, port):
        return CheckResult(name, "ok", f"{host}:{port} reachable")
    return CheckResult(name, "warning", f"{host}:{port} not reachable now")


def mysql_values_ready(values: dict[str, str]) -> bool:
    return all(values.get(key) and values.get(key) not in PLACEHOLDER_VALUES for key in MYSQL_ENV_KEYS)


def pymysql_connect(values: dict[str, str]):
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("PyMySQL is not installed. Run: pip install -r requirements.txt") from exc

    return pymysql.connect(
        host=values["MYSQL_HOST"],
        port=int(values["MYSQL_PORT"]),
        user=values["MYSQL_USER"],
        password=values["MYSQL_PASSWORD"],
        charset="utf8mb4",
        connect_timeout=3,
        read_timeout=3,
        write_timeout=3,
        autocommit=True,
    )


def check_mysql_login(values: dict[str, str]) -> CheckResult:
    if not mysql_values_ready(values):
        return CheckResult("mysql login", "warning", "MySQL credentials missing or placeholder; cannot verify login yet")

    try:
        connection = pymysql_connect(values)
    except Exception as exc:  # noqa: BLE001 - preflight reports the concrete connection failure as data.
        return CheckResult("mysql login", "warning", f"MySQL login failed: {exc}")

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.execute(
                "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = %s",
                (values["MYSQL_DATABASE"],),
            )
            database_exists = cursor.fetchone() is not None
    finally:
        connection.close()

    suffix = "database exists" if database_exists else "database will be created by setup script"
    return CheckResult("mysql login", "ok", f"MySQL login ok; {suffix}")


def check_spark_jdbc_config(values: dict[str, str]) -> CheckResult:
    issues = []
    url = values.get("SPARK_MYSQL_JDBC_URL", "")
    driver = values.get("SPARK_MYSQL_DRIVER", "")
    write_mode = values.get("SPARK_MYSQL_WRITE_MODE", "append")

    if not url or url in PLACEHOLDER_VALUES:
        issues.append("JDBC URL missing")
    elif not url.startswith("jdbc:mysql://"):
        issues.append("JDBC URL must start with jdbc:mysql://")

    if not driver or driver in PLACEHOLDER_VALUES:
        issues.append("driver missing")
    elif driver not in {"com.mysql.cj.jdbc.Driver", "com.mysql.jdbc.Driver"}:
        issues.append("driver must be a MySQL Connector/J driver")

    if write_mode not in SPARK_ALLOWED_WRITE_MODES:
        issues.append("write mode must be append")

    if issues:
        return CheckResult("spark jdbc config", "warning", "; ".join(issues))
    return CheckResult("spark jdbc config", "ok", f"JDBC config shape ok; write mode {write_mode}")


def check_kafka_bootstrap_config(values: dict[str, str]) -> CheckResult:
    try:
        from kafka_tools.check_connectivity import check_bootstrap_config
    except ImportError as exc:
        return CheckResult("kafka bootstrap config", "warning", f"cannot import Kafka config checker: {exc}")

    result = check_bootstrap_config(values.get("KAFKA_BOOTSTRAP_SERVERS", ""))
    return CheckResult("kafka bootstrap config", result["status"], result["message"])


def check_streaming_output_mode(values: dict[str, str]) -> CheckResult:
    output_mode = values.get("SPARK_STREAM_OUTPUT_MODE", "update")
    if output_mode not in SPARK_STREAM_ALLOWED_OUTPUT_MODES:
        return CheckResult("streaming output mode", "warning", "SPARK_STREAM_OUTPUT_MODE must be append or update")
    return CheckResult("streaming output mode", "ok", output_mode)


def check_database_name_alignment(values: dict[str, str]) -> CheckResult:
    mysql_database = values.get("MYSQL_DATABASE", "").strip()
    jdbc_database = parse_jdbc_database_name(values.get("SPARK_MYSQL_JDBC_URL", ""))

    if not mysql_database or not jdbc_database:
        return CheckResult("database name alignment", "warning", "MYSQL_DATABASE or SPARK_MYSQL_JDBC_URL database name missing")
    if mysql_database != jdbc_database:
        return CheckResult(
            "database name alignment",
            "warning",
            f"MYSQL_DATABASE ({mysql_database}) differs from SPARK_MYSQL_JDBC_URL database ({jdbc_database})",
        )
    return CheckResult("database name alignment", "ok", mysql_database)


def mysql_target(values: dict[str, str]) -> tuple[str | None, int | None]:
    host = values.get("MYSQL_HOST")
    try:
        port = int(values.get("MYSQL_PORT", ""))
    except ValueError:
        return host, None
    return host, port


def kafka_target(values: dict[str, str]) -> tuple[str | None, int | None]:
    servers = values.get("KAFKA_BOOTSTRAP_SERVERS", "")
    first = servers.split(",", 1)[0].strip()
    parsed = parse_host_port(first)
    if not parsed:
        return None, None
    return parsed


def run_checks(env_path: Path = DEFAULT_ENV_PATH, target: str = "all") -> list[CheckResult]:
    values = load_env(env_path)
    mysql_host, mysql_port = mysql_target(values)
    kafka_host, kafka_port = kafka_target(values)

    if target == "local-mysql":
        return [
            check_file("env example", ROOT_DIR / ".env.example"),
            check_env_file(env_path),
            check_file("mock data", ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json"),
            check_file("mysql schema", ROOT_DIR / "database" / "schema.sql"),
            check_command("python", "python"),
            check_tcp("mysql tcp", mysql_host, mysql_port),
            *check_env_values(values, MYSQL_ENV_KEYS),
            check_mysql_login(values),
        ]

    if target == "spark-jdbc":
        return [
            check_file("env example", ROOT_DIR / ".env.example"),
            check_env_file(env_path),
            check_file("mock data", ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json"),
            check_file("mysql schema", ROOT_DIR / "database" / "schema.sql"),
            check_command("python", "python"),
            check_command("spark-submit", "spark-submit", required=False),
            check_tcp("mysql tcp", mysql_host, mysql_port),
            *check_env_values(values, SPARK_ENV_KEYS),
            check_spark_jdbc_config(values),
            check_mysql_login(values),
        ]

    if target == "kafka":
        return [
            check_file("env example", ROOT_DIR / ".env.example"),
            check_env_file(env_path),
            check_file("mock data", ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json"),
            check_command("python", "python"),
            check_kafka_bootstrap_config(values),
            check_tcp("kafka tcp", kafka_host, kafka_port),
            *check_env_values(values, KAFKA_ENV_KEYS),
        ]

    if target == "full-pipeline":
        return [
            check_file("env example", ROOT_DIR / ".env.example"),
            check_env_file(env_path),
            check_file("mock data", ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json"),
            check_file("mysql schema", ROOT_DIR / "database" / "schema.sql"),
            check_command("python", "python"),
            check_command("spark-submit", "spark-submit", required=False),
            check_tcp("mysql tcp", mysql_host, mysql_port),
            check_tcp("kafka tcp", kafka_host, kafka_port),
            *check_env_values(values, MYSQL_ENV_KEYS + SPARK_ENV_KEYS + KAFKA_ENV_KEYS),
            check_spark_jdbc_config(values),
            check_kafka_bootstrap_config(values),
            check_streaming_output_mode(values),
            check_database_name_alignment(values),
            check_mysql_login(values),
        ]

    results = [
        check_file("env example", ROOT_DIR / ".env.example"),
        check_env_file(env_path),
        check_file("mock data", ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json"),
        check_file("mysql schema", ROOT_DIR / "database" / "schema.sql"),
        check_command("python", "python"),
        check_command("node", "node"),
        check_command("npm", "npm"),
        check_command("git", "git"),
        check_command("spark-submit", "spark-submit", required=False),
        check_tcp("mysql tcp", mysql_host, mysql_port),
        check_tcp("kafka tcp", kafka_host, kafka_port),
    ]
    results.extend(check_env_values(values))
    results.append(check_spark_jdbc_config(values))
    results.append(check_kafka_bootstrap_config(values))
    results.append(check_mysql_login(values))
    return results


def summarize(results: list[CheckResult]) -> dict:
    counts = {"ok": 0, "warning": 0, "error": 0}
    for result in results:
        counts[result.status] += 1
    return {"status": "ok" if counts["error"] == 0 else "failed", "counts": counts}


def main() -> None:
    parser = argparse.ArgumentParser(description="Check local readiness for CreatorPulse MVP")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument(
        "--target",
        choices=["all", "local-mysql", "spark-jdbc", "kafka", "full-pipeline"],
        default="all",
        help="Limit checks to one setup target so real services can be verified independently.",
    )
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    args = parser.parse_args()

    results = run_checks(args.env_file, args.target)
    summary = summarize(results)
    payload = {**summary, "checks": [asdict(result) for result in results]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if summary["counts"]["error"] > 0 or (args.strict and summary["counts"]["warning"] > 0):
        raise SystemExit(1)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
