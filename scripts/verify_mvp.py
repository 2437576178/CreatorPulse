"""Run CreatorPulse MVP verification end to end.

The script keeps the existing tests as source of truth, then starts temporary
Flask and Vite dev servers for the browser smoke test.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class Command:
    name: str
    args: list[str]
    cwd: Path = ROOT_DIR
    needs_server: bool = False


CORE_COMMANDS = [
    Command("env init tests", [sys.executable, "scripts/tests/test_init_env.py"]),
    Command("env init check", [sys.executable, "scripts/init_env.py", "--check"]),
    Command("preflight tests", [sys.executable, "scripts/tests/test_preflight.py"]),
    Command("env readiness report tests", [sys.executable, "scripts/tests/test_report_env_readiness.py"]),
    Command("preflight dry-run", [sys.executable, "scripts/preflight.py"]),
    Command("env readiness report", [sys.executable, "scripts/report_env_readiness.py"]),
    Command("full pipeline preflight dry-run", [sys.executable, "scripts/preflight.py", "--target", "full-pipeline"]),
    Command("real service sequence tests", [sys.executable, "scripts/tests/test_run_real_service_sequence.py"]),
    Command("real service execution plan report tests", [sys.executable, "scripts/tests/test_report_real_service_plans.py"]),
    Command("real service execution checklist tests", [sys.executable, "scripts/tests/test_report_execution_checklist.py"]),
    Command("real service readiness audit tests", [sys.executable, "scripts/tests/test_audit_real_service_readiness.py"]),
    Command("real service report bundle tests", [sys.executable, "scripts/tests/test_export_real_service_report_bundle.py"]),
    Command("mvp status tests", [sys.executable, "scripts/tests/test_status_mvp.py"]),
    Command("mvp verify command tests", [sys.executable, "scripts/tests/test_verify_mvp.py"]),
    Command("mvp status report", [sys.executable, "scripts/status_mvp.py"]),
    Command("real service sequence dry-run", [sys.executable, "scripts/run_real_service_sequence.py"]),
    Command("real service execution plan report", [sys.executable, "scripts/report_real_service_plans.py"]),
    Command("real service execution checklist", [sys.executable, "scripts/report_execution_checklist.py"]),
    Command("real service readiness audit", [sys.executable, "scripts/audit_real_service_readiness.py"]),
    Command(
        "real service report artifact export",
        [
            sys.executable,
            "scripts/report_execution_checklist.py",
            "--stage",
            "mysql",
            "--output",
            "reports/mvp-execution-checklist-smoke.json",
        ],
    ),
    Command(
        "real service report bundle export",
        [
            sys.executable,
            "scripts/export_real_service_report_bundle.py",
            "--stage",
            "mysql",
            "--output-dir",
            "reports/mvp-real-service-bundle-smoke",
        ],
    ),
    Command("openapi export tests", [sys.executable, "scripts/tests/test_export_openapi.py"]),
    Command("openapi export check", [sys.executable, "scripts/export_openapi.py", "--check"]),
    Command("data contract audit tests", [sys.executable, "scripts/tests/test_audit_data_contract.py"]),
    Command("data contract audit dry-run", [sys.executable, "scripts/audit_data_contract.py"]),
    Command("object coverage audit tests", [sys.executable, "scripts/tests/test_audit_object_coverage.py"]),
    Command("object coverage audit dry-run", [sys.executable, "scripts/audit_object_coverage.py"]),
    Command("data quality audit tests", [sys.executable, "scripts/tests/test_audit_data_quality.py"]),
    Command("data quality audit dry-run", [sys.executable, "scripts/audit_data_quality.py"]),
    Command("local mysql setup tests", [sys.executable, "scripts/tests/test_setup_local_mysql.py"]),
    Command("local mysql setup dry-run", [sys.executable, "scripts/setup_local_mysql.py"]),
    Command("database schema tests", [sys.executable, "database/tests/test_apply_schema.py"]),
    Command("database schema dry-run", [sys.executable, "database/apply_schema.py"]),
    Command("database import tests", [sys.executable, "database/tests/test_import_mock_to_mysql.py"]),
    Command("database import dry-run", [sys.executable, "database/import_mock_to_mysql.py"]),
    Command("mock data validation", [sys.executable, "mvp_mock/validate_mock.py"]),
    Command("mock API tests", [sys.executable, "api/tests/test_mock_api.py"]),
    Command("openapi contract tests", [sys.executable, "api/tests/test_openapi_contract.py"]),
    Command("view model contract tests", [sys.executable, "api/tests/test_view_model_contract.py"]),
    Command("frontend API service contract tests", [sys.executable, "frontend/tests/test_api_service_contract.py"]),
    Command("static frontend hosting tests", [sys.executable, "api/tests/test_static_frontend.py"]),
    Command("repository factory tests", [sys.executable, "api/tests/test_repository_factory.py"]),
    Command("mysql repository mapping tests", [sys.executable, "api/tests/test_mysql_repository_mapping.py"]),
    Command("mysql API integration optional test", [sys.executable, "api/tests/test_mysql_api_integration.py"]),
    Command("spark insight tests", [sys.executable, "api/tests/test_spark_insights.py"]),
    Command("spark static tests", [sys.executable, "spark_jobs/tests/test_static_mock_to_mysql.py"]),
    Command("spark JDBC optional integration test", [sys.executable, "spark_jobs/tests/test_static_mysql_jdbc_integration.py"]),
    Command("spark static dry-run", [sys.executable, "spark_jobs/static_mock_to_mysql.py"]),
    Command("kafka connectivity tests", [sys.executable, "kafka_tools/tests/test_check_connectivity.py"]),
    Command("kafka mock event tests", [sys.executable, "kafka_tools/tests/test_mock_events.py"]),
    Command("kafka mock consumer tests", [sys.executable, "kafka_tools/tests/test_mock_consumer.py"]),
    Command("kafka closed-loop tests", [sys.executable, "kafka_tools/tests/test_run_closed_loop.py"]),
    Command("kafka optional integration test", [sys.executable, "kafka_tools/tests/test_kafka_live_integration.py"]),
    Command("kafka mock producer dry-run", [sys.executable, "kafka_tools/mock_producer.py"]),
    Command("kafka mock consumer dry-run", [sys.executable, "kafka_tools/mock_consumer.py"]),
    Command("kafka closed-loop dry-run", [sys.executable, "kafka_tools/run_closed_loop.py"]),
    Command("spark kafka-event tests", [sys.executable, "spark_jobs/tests/test_kafka_events_to_mysql.py"]),
    Command("spark kafka-event dry-run", [sys.executable, "spark_jobs/kafka_events_to_mysql.py"]),
    Command("spark streaming config tests", [sys.executable, "spark_jobs/tests/test_kafka_streaming_to_mysql.py"]),
    Command("spark streaming dry-run", [sys.executable, "spark_jobs/kafka_streaming_to_mysql.py"]),
    Command("frontend build", ["npm", "run", "build"], FRONTEND_DIR),
]

BROWSER_COMMAND = Command("frontend browser smoke", ["npm", "run", "test:smoke"], FRONTEND_DIR, needs_server=True)
DIFF_COMMAND = Command("git diff check", ["git", "diff", "--check"], ROOT_DIR)


def print_step(message: str) -> None:
    print(f"\n==> {message}", flush=True)


def run_command(command: Command, extra_env: dict[str, str] | None = None) -> None:
    print_step(command.name)
    env = os.environ.copy()
    env.setdefault("CREATORPULSE_DATA_SOURCE", "mock")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9092")
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        resolve_command(command.args),
        cwd=command.cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", flush=True)
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, command.args)


def resolve_command(args: list[str]) -> list[str]:
    executable = shutil.which(args[0])
    if executable is None:
        raise RuntimeError(f"Executable not found on PATH: {args[0]}")
    return [executable, *args[1:]]


def port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.35)
        return sock.connect_ex((host, port)) == 0


def wait_for_port(host: str, port: int, name: str, timeout_seconds: float = 30) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if port_open(host, port):
            return
        time.sleep(0.25)
    raise RuntimeError(f"{name} did not start on {host}:{port} within {timeout_seconds}s")


def start_process(name: str, args: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen:
    print_step(f"start {name}")
    return subprocess.Popen(
        resolve_command(args),
        cwd=cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=8)


def run_browser_smoke() -> None:
    env = os.environ.copy()
    env.setdefault("CREATORPULSE_DATA_SOURCE", "mock")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["APP_URL"] = "http://127.0.0.1:5173"

    started_api = None
    started_frontend = None
    try:
        if not port_open("127.0.0.1", 5000):
            started_api = start_process("Flask API", [sys.executable, "api/app.py"], ROOT_DIR, env)
            wait_for_port("127.0.0.1", 5000, "Flask API")

        if not port_open("127.0.0.1", 5173):
            started_frontend = start_process("Vite dev server", ["npm", "run", "dev"], FRONTEND_DIR, env)
            wait_for_port("127.0.0.1", 5173, "Vite dev server")

        run_command(BROWSER_COMMAND, {"APP_URL": env["APP_URL"]})
    finally:
        stop_process(started_frontend)
        stop_process(started_api)


def run_flask_frontend_smoke() -> None:
    env = os.environ.copy()
    env.setdefault("CREATORPULSE_DATA_SOURCE", "mock")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["APP_URL"] = "http://127.0.0.1:5000"

    started_api = None
    try:
        if not port_open("127.0.0.1", 5000):
            started_api = start_process("Flask frontend/API", [sys.executable, "api/app.py"], ROOT_DIR, env)
            wait_for_port("127.0.0.1", 5000, "Flask frontend/API")

        run_command(BROWSER_COMMAND, {"APP_URL": env["APP_URL"]})
    finally:
        stop_process(started_api)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CreatorPulse MVP verification")
    parser.add_argument("--skip-browser", action="store_true", help="Skip browser smoke test and temporary dev servers")
    args = parser.parse_args()

    for command in CORE_COMMANDS:
        run_command(command)

    if not args.skip_browser:
        run_browser_smoke()
        run_flask_frontend_smoke()

    run_command(DIFF_COMMAND)
    print("\nMVP verification passed", flush=True)


if __name__ == "__main__":
    main()
