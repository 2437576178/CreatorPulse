"""Repository for CreatorPulse MVP mock data."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json"


class MockDataError(RuntimeError):
    """Raised when the mock data file cannot satisfy the API contract."""


@lru_cache(maxsize=1)
def load_mock_data(path: str | None = None) -> dict[str, Any]:
    data_path = Path(path) if path else DEFAULT_DATA_PATH
    if not data_path.exists():
        raise MockDataError(f"Mock data file not found: {data_path}")

    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MockDataError(f"Mock data is not valid JSON: {data_path}") from exc

    required_keys = {
        "meta",
        "creator",
        "platformAccounts",
        "videos",
        "videoMetricSnapshots",
        "creatorMetricSnapshots",
        "audienceProfileSnapshot",
        "topicTrendSnapshots",
        "insights",
        "viewModels",
    }
    missing = sorted(required_keys - set(data))
    if missing:
        raise MockDataError(f"Mock data missing keys: {', '.join(missing)}")
    return data


def get_creator_payload(creator_id: str) -> dict[str, Any]:
    data = load_mock_data()
    if creator_id != "demo" and creator_id != data["creator"]["creatorId"]:
        raise KeyError(creator_id)
    return data


def get_view_model(creator_id: str, key: str) -> dict[str, Any]:
    data = get_creator_payload(creator_id)
    view_models = data["viewModels"]
    if key not in view_models:
        raise KeyError(key)

    return {
        "meta": data["meta"],
        "creator": data["creator"],
        "data": view_models[key],
    }


def get_health() -> dict[str, Any]:
    data = load_mock_data()
    return {
        "status": "ok",
        "schemaVersion": data["meta"]["schemaVersion"],
        "generatedAt": data["meta"]["generatedAt"],
        "counts": {
            "platforms": len(data["platformAccounts"]),
            "videos": len(data["videos"]),
            "videoMetricSnapshots": len(data["videoMetricSnapshots"]),
            "creatorMetricSnapshots": len(data["creatorMetricSnapshots"]),
            "topicTrendSnapshots": len(data["topicTrendSnapshots"]),
            "insights": len(data["insights"]),
        },
    }
