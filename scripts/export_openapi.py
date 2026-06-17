"""Export the CreatorPulse MVP OpenAPI schema to a stable JSON file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from openapi_contract import openapi_schema  # noqa: E402


DEFAULT_OUTPUT_PATH = API_DIR / "openapi.json"


def stable_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def export_openapi(output_path: Path = DEFAULT_OUTPUT_PATH) -> dict[str, Any]:
    schema = openapi_schema()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(stable_json(schema), encoding="utf-8")
    return schema


def is_openapi_current(output_path: Path = DEFAULT_OUTPUT_PATH) -> bool:
    if not output_path.exists():
        return False
    return output_path.read_text(encoding="utf-8") == stable_json(openapi_schema())


def main() -> None:
    parser = argparse.ArgumentParser(description="Export CreatorPulse MVP OpenAPI JSON")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--check", action="store_true", help="Fail if the exported OpenAPI file is missing or stale")
    args = parser.parse_args()

    if args.check:
        current = is_openapi_current(args.output)
        print(json.dumps({"status": "ok" if current else "stale", "output": str(args.output)}, ensure_ascii=False, indent=2))
        if not current:
            raise SystemExit(1)
        return

    schema = export_openapi(args.output)
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(args.output),
                "paths": len(schema["paths"]),
                "schemas": len(schema["components"]["schemas"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
