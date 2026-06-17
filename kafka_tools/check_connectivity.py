"""Check basic connectivity to Kafka brokers running in a VM.

This intentionally does not produce or consume Kafka messages yet. It only
verifies host:port reachability so Kafka networking stays decoupled from
Flask, Vue, MySQL, and Spark JDBC work.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT_DIR / ".env"
PLACEHOLDER_BOOTSTRAP_SERVERS = {"192.168.56.10:9092"}


def load_env_file(path: Path = DEFAULT_ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def parse_bootstrap_servers(value: str) -> list[tuple[str, int]]:
    if value.strip() in PLACEHOLDER_BOOTSTRAP_SERVERS:
        raise ValueError("Kafka bootstrap server is still a placeholder value")

    servers = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"Kafka bootstrap server must be host:port, got: {item}")
        host, port_text = item.rsplit(":", 1)
        if not host.strip():
            raise ValueError(f"Kafka bootstrap server host is empty: {item}")
        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValueError(f"Kafka bootstrap server port must be an integer: {item}") from exc
        if port <= 0 or port > 65535:
            raise ValueError(f"Kafka bootstrap server port out of range: {item}")
        servers.append((host, port))
    if not servers:
        raise ValueError("At least one Kafka bootstrap server is required")
    return servers


def check_bootstrap_config(value: str) -> dict:
    try:
        servers = parse_bootstrap_servers(value)
    except ValueError as exc:
        return {"status": "warning", "message": str(exc), "servers": []}
    return {
        "status": "ok",
        "message": "Kafka bootstrap config shape ok",
        "servers": [f"{host}:{port}" for host, port in servers],
    }


def check_tcp(host: str, port: int, timeout_seconds: float) -> dict:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return {"host": host, "port": port, "reachable": True, "error": None}
    except OSError as exc:
        return {"host": host, "port": port, "reachable": False, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Kafka VM host:port reachability")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--bootstrap-servers", default=None, help="Comma-separated host:port list")
    parser.add_argument("--timeout", type=float, default=None, help="TCP timeout in seconds")
    args = parser.parse_args()

    load_env_file(args.env_file)
    bootstrap_servers = args.bootstrap_servers or os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "")
    timeout = args.timeout
    if timeout is None:
        timeout = float(os.environ.get("KAFKA_TEST_TIMEOUT_SECONDS", "5"))

    config = check_bootstrap_config(bootstrap_servers)
    if config["status"] != "ok":
        print(json.dumps({"status": "failed", "error": config["message"], "checks": []}, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    servers = parse_bootstrap_servers(bootstrap_servers)
    checks = [check_tcp(host, port, timeout) for host, port in servers]
    status = "ok" if all(item["reachable"] for item in checks) else "failed"
    print(json.dumps({"status": status, "checks": checks}, ensure_ascii=False, indent=2))

    if status != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
