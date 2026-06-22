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
from spark_jobs.kafka_events_to_mysql import archive_raw_video_stat_events  # noqa: E402
from spark_jobs.offline_daily_metrics import aggregate_daily_metrics  # noqa: E402
from spark_jobs.offline_reports import camel_report, generate_reports  # noqa: E402
from kafka_tools.mock_event_builder import build_events  # noqa: E402
from database.import_mock_to_mysql import platform_follower_counts  # noqa: E402
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

    def list_reports(self, creator_id: str, report_type: str | None = None, page: int = 1, page_size: int = 10) -> dict[str, Any]:
        data = get_creator_payload(creator_id)
        reports = make_mock_reports(data, report_type)
        start = (page - 1) * page_size
        end = start + page_size
        return {"items": reports[start:end], "page": page, "pageSize": page_size, "total": len(reports)}

    def get_report(self, creator_id: str, report_id: str) -> dict[str, Any]:
        data = get_creator_payload(creator_id)
        for report in make_mock_reports(data):
            if report["reportId"] == report_id:
                return report
        raise KeyError(report_id)


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
    follower_counts = platform_follower_counts(enriched)
    enriched["platformAccounts"] = [
        {
            **item,
            "followerCount": follower_counts.get(item["platform"], 0),
        }
        for item in data["platformAccounts"]
    ]
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


def make_mock_reports(data: dict[str, Any], report_type: str | None = None) -> list[dict[str, Any]]:
    raw_rows = archive_raw_video_stat_events(build_events(data))
    daily_metrics = aggregate_daily_metrics(
        raw_rows,
        data["videos"],
        batch_run_id="mock_offline_daily_report_source",
        start_date="2026-06-14",
        end_date="2026-06-14",
        creator_id=data["creator"]["creatorId"],
    )
    wanted_types = [report_type.upper()] if report_type else ["DAILY", "WEEKLY", "MONTHLY"]
    reports = []
    for current_type in wanted_types:
        reports.extend(
            camel_report(report)
            for report in generate_reports(
                daily_metrics,
                data,
                report_type=current_type,
                period_start="2026-06-14",
                period_end="2026-06-14",
                batch_run_id=f"mock_offline_report_{current_type.lower()}",
                creator_id=data["creator"]["creatorId"],
            )
        )
    return reports
