"""Report how MVP data objects flow through MySQL rows and page ViewModels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "api"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from api.mysql_repository import MySQLRepository  # noqa: E402
from database.import_mock_to_mysql import build_table_rows, load_json, validate_rows  # noqa: E402


OBJECT_SPECS = [
    {
        "name": "creator",
        "mockPath": ["creator"],
        "mysqlTables": ["creators"],
        "viewModelFields": [],
        "expectedPageExposure": False,
        "notes": "returned in API payload creator, not repeated inside page ViewModel data",
    },
    {
        "name": "platformAccounts",
        "mockPath": ["platformAccounts"],
        "mysqlTables": ["platform_accounts"],
        "viewModelFields": [{"viewModel": "profile", "field": "platformAccounts"}],
        "expectedPageExposure": True,
        "notes": "used by profile authorization and binding checks",
    },
    {
        "name": "videos",
        "mockPath": ["videos"],
        "mysqlTables": ["videos"],
        "viewModelFields": [{"viewModel": "videoAnalysis", "field": "videos"}],
        "expectedPageExposure": True,
        "notes": "core content identity object",
    },
    {
        "name": "videoMetricSnapshots",
        "mockPath": ["videoMetricSnapshots"],
        "mysqlTables": ["video_metric_snapshots"],
        "viewModelFields": [
            {"viewModel": "videoAnalysis", "field": "snapshots"},
            {"viewModel": "growthDashboard", "field": "topVideos"},
            {"viewModel": "videoAnalysis", "field": "topVideos"},
        ],
        "expectedPageExposure": True,
        "notes": "powers video performance, growth top videos, and ranking views",
    },
    {
        "name": "videoTrafficSourceMetrics",
        "mockPath": ["videoTrafficSourceMetrics"],
        "mysqlTables": ["video_traffic_source_metrics"],
        "viewModelFields": [],
        "expectedPageExposure": False,
        "notes": "stored for later source-quality analysis; current MVP ViewModels use higher-level aggregates",
    },
    {
        "name": "creatorMetricSnapshots",
        "mockPath": ["creatorMetricSnapshots"],
        "mysqlTables": ["creator_metric_snapshots"],
        "viewModelFields": [
            {"viewModel": "fansAnalysis", "field": "trend"},
            {"viewModel": "growthDashboard", "field": "currentSnapshot"},
        ],
        "expectedPageExposure": True,
        "notes": "powers account trend and current growth snapshot",
    },
    {
        "name": "audienceProfileSnapshot",
        "mockPath": ["audienceProfileSnapshot"],
        "mysqlTables": ["audience_profile_snapshots"],
        "viewModelFields": [{"viewModel": "fansAnalysis", "field": "audienceProfile"}],
        "expectedPageExposure": True,
        "notes": "used by audience strategy and fan profile views",
    },
    {
        "name": "topicTrendSnapshots",
        "mockPath": ["topicTrendSnapshots"],
        "mysqlTables": ["topic_trend_snapshots"],
        "viewModelFields": [{"viewModel": "opportunities", "field": "topics"}],
        "expectedPageExposure": True,
        "notes": "used by opportunity discovery",
    },
    {
        "name": "insights",
        "mockPath": ["insights"],
        "mysqlTables": ["insights", "insight_evidence_metrics", "recommended_actions"],
        "viewModelFields": [
            {"viewModel": "growthDashboard", "field": "insights"},
            {"viewModel": "fansAnalysis", "field": "insights"},
            {"viewModel": "videoAnalysis", "field": "insights"},
            {"viewModel": "contentDistribution", "field": "insights"},
            {"viewModel": "opportunities", "field": "insights"},
            {"viewModel": "profile", "field": "insights"},
        ],
        "expectedPageExposure": True,
        "notes": "page conclusions, evidence metrics, and recommended actions",
    },
    {
        "name": "sparkPlatformMetricSummaries",
        "mockPath": ["sparkOutputs", "platformMetricSummaries"],
        "mysqlTables": ["spark_platform_metric_summaries"],
        "viewModelFields": [{"viewModel": "contentDistribution", "field": "sparkPlatformSummaries"}],
        "expectedPageExposure": True,
        "notes": "runtime aggregate also imported for MySQL dry-run parity",
    },
    {
        "name": "sparkVideoFollowerContributions",
        "mockPath": ["sparkOutputs", "videoFollowerContributions"],
        "mysqlTables": ["spark_video_follower_contributions"],
        "viewModelFields": [{"viewModel": "videoAnalysis", "field": "sparkContributions"}],
        "expectedPageExposure": True,
        "notes": "runtime aggregate used by video growth attribution",
    },
]


def count_value(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return 1
    if value is None:
        return 0
    return 1


def nested_get(data: dict[str, Any], path: list[str]) -> Any:
    current: Any = data
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def view_model_count(view_models: dict[str, Any], view_model_name: str, field: str) -> int:
    value = view_models.get(view_model_name, {}).get(field)
    return count_value(value)


def object_coverage_status(has_mysql: bool, has_exposure: bool, expected_exposure: bool) -> str:
    if not has_mysql:
        return "missing-mysql"
    if expected_exposure and not has_exposure:
        return "missing-page-exposure"
    if not expected_exposure and not has_exposure:
        return "stored-only"
    return "covered"


def build_object_coverage_report() -> dict[str, Any]:
    data = load_json()
    rows = build_table_rows(data)
    validate_rows(rows)
    contract = MySQLRepository().to_contract(rows)
    enriched = {**data, "sparkOutputs": contract["sparkOutputs"]}
    view_models = contract["viewModels"]

    objects = []
    for spec in OBJECT_SPECS:
        mysql_counts = {table: len(rows.get(table, [])) for table in spec["mysqlTables"]}
        exposures = [
            {
                "viewModel": item["viewModel"],
                "field": item["field"],
                "count": view_model_count(view_models, item["viewModel"], item["field"]),
            }
            for item in spec["viewModelFields"]
        ]
        has_mysql = all(count > 0 for count in mysql_counts.values())
        has_exposure = any(item["count"] > 0 for item in exposures)
        coverage_status = object_coverage_status(has_mysql, has_exposure, spec["expectedPageExposure"])
        objects.append(
            {
                "name": spec["name"],
                "mockCount": count_value(nested_get(enriched, spec["mockPath"])),
                "mysqlTables": spec["mysqlTables"],
                "mysqlRowCounts": mysql_counts,
                "viewModelExposures": exposures,
                "coverageStatus": coverage_status,
                "notes": spec["notes"],
            }
        )

    missing_mysql = [item["name"] for item in objects if item["coverageStatus"] == "missing-mysql"]
    missing_exposure = [item["name"] for item in objects if item["coverageStatus"] == "missing-page-exposure"]
    return {
        "status": "ok" if not missing_mysql and not missing_exposure else "warning",
        "summary": {
            "totalObjects": len(objects),
            "covered": [item["name"] for item in objects if item["coverageStatus"] == "covered"],
            "storedOnly": [item["name"] for item in objects if item["coverageStatus"] == "stored-only"],
            "missingMySQLCoverage": missing_mysql,
            "unexpectedMissingPageExposure": missing_exposure,
        },
        "objects": objects,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Report MVP data-object coverage across storage and API ViewModels")
    parser.parse_args()

    print(json.dumps(build_object_coverage_report(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
