"""Create a local .env from .env.example without exposing credentials."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLE_PATH = ROOT_DIR / ".env.example"
DEFAULT_ENV_PATH = ROOT_DIR / ".env"


def init_env(example_path: Path = DEFAULT_EXAMPLE_PATH, env_path: Path = DEFAULT_ENV_PATH, force: bool = False) -> dict:
    if not example_path.exists():
        raise FileNotFoundError(f"Missing template: {example_path}")

    if env_path.exists() and not force:
        return {
            "status": "exists",
            "envFile": str(env_path),
            "message": ".env already exists; rerun with --force only if you intentionally want to replace it.",
        }

    env_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example_path, env_path)
    return {
        "status": "overwritten" if force else "created",
        "envFile": str(env_path),
        "template": str(example_path),
        "nextCommand": "python scripts\\preflight.py --target local-mysql --strict",
        "manualFollowUp": "Fill MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE, MYSQL_USER, and MYSQL_PASSWORD before running strict preflight.",
    }


def preview_init_env(example_path: Path = DEFAULT_EXAMPLE_PATH, env_path: Path = DEFAULT_ENV_PATH) -> dict:
    if not example_path.exists():
        raise FileNotFoundError(f"Missing template: {example_path}")

    if env_path.exists():
        return {
            "status": "exists",
            "envFile": str(env_path),
            "message": ".env already exists; init command would leave it unchanged.",
        }

    return {
        "status": "would-create",
        "envFile": str(env_path),
        "template": str(example_path),
        "message": ".env is missing; run python scripts\\init_env.py to create it from .env.example.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize CreatorPulse local .env from .env.example")
    parser.add_argument("--example", type=Path, default=DEFAULT_EXAMPLE_PATH)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing .env from the template")
    parser.add_argument("--check", action="store_true", help="Report what would happen without writing .env")
    args = parser.parse_args()

    result = preview_init_env(args.example, args.env_file) if args.check else init_env(args.example, args.env_file, args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
