"""Shared helpers for writing optional JSON report artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def format_json_report(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def write_json_report(payload: dict[str, Any], output: Path | None) -> None:
    if output is None:
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_json_report(payload) + "\n", encoding="utf-8")
