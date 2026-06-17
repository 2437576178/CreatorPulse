"""Repository for CreatorPulse MVP mock data."""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from spark_jobs.static_mock_to_mysql import calculate_platform_summaries, calculate_video_contributions  # noqa: E402
from spark_insights import merge_spark_insights  # noqa: E402
from view_model_builder import make_view_models  # noqa: E402

DEFAULT_DATA_PATH = ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json"


class MockDataError(RuntimeError):
    """Raised when the mock data file cannot satisfy the API contract."""


class MockRepository:
    """Repository implementation backed by the MVP mock JSON file."""

    def get_health(self) -> dict[str, Any]:
        return get_health()

    def get_view_model(self, creator_id: str, key: str) -> dict[str, Any]:
        return get_view_model(creator_id, key)


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

    data = with_runtime_outputs(data)
    return data


def with_runtime_outputs(data: dict[str, Any]) -> dict[str, Any]:
    enriched = {**data}
    enriched["sparkOutputs"] = data.get("sparkOutputs") or {
        "platformMetricSummaries": [
            {
                "runId": item["run_id"],
                "creatorId": item["creator_id"],
                "platform": item["platform"],
                "totalViews": item["total_views"],
                "newFollowers": item["new_followers"],
                "videoCount": item["video_count"],
                "conversionRate": item["conversion_rate"],
                "calculatedAt": item["calculated_at"],
            }
            for item in calculate_platform_summaries(data, "spark_static_mock_001", data["meta"]["generatedAt"])
        ],
        "videoFollowerContributions": [
            {
                "runId": item["run_id"],
                "rankPosition": item["rank_position"],
                "creatorId": item["creator_id"],
                "videoId": item["video_id"],
                "platform": item["platform"],
                "title": item["title"],
                "views": item["views"],
                "newFollowers": item["new_followers"],
                "conversionRate": item["conversion_rate"],
                "calculatedAt": item["calculated_at"],
            }
            for item in calculate_video_contributions(data, "spark_static_mock_001", data["meta"]["generatedAt"])
        ],
    }
    enriched = merge_spark_insights(enriched)
    enriched["viewModels"] = make_view_models(enriched)
    return enriched


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
            "sparkPlatformMetricSummaries": len(data["sparkOutputs"]["platformMetricSummaries"]),
            "sparkVideoFollowerContributions": len(data["sparkOutputs"]["videoFollowerContributions"]),
        },
    }
