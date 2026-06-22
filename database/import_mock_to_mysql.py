"""Import CreatorPulse MVP mock JSON into MySQL.

Default mode is a dry-run that validates row mapping and prints table counts.
Use --execute after filling .env or environment variables to write MySQL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from spark_jobs.static_mock_to_mysql import calculate_platform_summaries, calculate_video_contributions  # noqa: E402

DEFAULT_DATA_PATH = ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json"
DEFAULT_ENV_PATH = ROOT_DIR / ".env"

TABLE_ORDER = [
    "creators",
    "platform_accounts",
    "videos",
    "video_metric_snapshots",
    "video_traffic_source_metrics",
    "creator_metric_snapshots",
    "audience_profile_snapshots",
    "topic_trend_snapshots",
    "insights",
    "insight_evidence_metrics",
    "recommended_actions",
    "spark_platform_metric_summaries",
    "spark_video_follower_contributions",
]

PRIMARY_KEYS = {
    "creators": {"creator_id"},
    "platform_accounts": {"account_id"},
    "videos": {"video_id"},
    "video_metric_snapshots": {"snapshot_id"},
    "video_traffic_source_metrics": {"video_id", "source"},
    "creator_metric_snapshots": {"snapshot_id"},
    "audience_profile_snapshots": {"snapshot_id"},
    "topic_trend_snapshots": {"topic_id"},
    "insights": {"insight_id"},
    "insight_evidence_metrics": {"insight_id", "position"},
    "recommended_actions": {"action_id"},
    "spark_platform_metric_summaries": {"run_id", "creator_id", "platform"},
    "spark_video_follower_contributions": {"run_id", "creator_id", "rank_position"},
}


class ImportConfigError(RuntimeError):
    """Raised when MySQL import configuration is missing or invalid."""


def json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def mysql_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=None)


def platform_follower_counts(data: dict[str, Any]) -> dict[str, int]:
    explicit = {
        item["platform"]: int(item["followerCount"])
        for item in data.get("platformAccounts", [])
        if item.get("followerCount") is not None
    }
    platforms = [item["platform"] for item in data.get("platformAccounts", [])]
    missing = [platform for platform in platforms if platform not in explicit]
    if not missing:
        return explicit

    snapshots = data.get("creatorMetricSnapshots") or []
    latest_total = int(snapshots[-1].get("totalFollowers", 0)) if snapshots else 0
    if latest_total <= 0:
        return {platform: explicit.get(platform, 0) for platform in platforms}

    platform_new_followers: dict[str, int] = {platform: 0 for platform in platforms}
    for snapshot in data.get("videoMetricSnapshots", []):
        platform = snapshot.get("platform")
        if platform in platform_new_followers:
            platform_new_followers[platform] += int(snapshot.get("newFollowers", 0))

    weight_total = sum(platform_new_followers[platform] for platform in missing)
    if weight_total <= 0:
        equal_share = latest_total // max(len(platforms), 1)
        counts = {platform: explicit.get(platform, equal_share) for platform in platforms}
        if platforms:
            counts[platforms[-1]] += latest_total - sum(counts.values())
        return counts

    counts = dict(explicit)
    remaining_total = max(0, latest_total - sum(explicit.values()))
    for platform in missing[:-1]:
        counts[platform] = int(round(remaining_total * platform_new_followers[platform] / weight_total))
    counts[missing[-1]] = max(0, remaining_total - sum(counts[platform] for platform in missing[:-1]))
    return counts


def load_json(path: Path = DEFAULT_DATA_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_env_file(path: Path = DEFAULT_ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class MySQLConfig:
    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "MySQLConfig":
        required = ["MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD"]
        missing = [key for key in required if not os.environ.get(key)]
        if missing:
            raise ImportConfigError(f"Missing MySQL environment variables: {', '.join(missing)}")

        try:
            port = int(os.environ["MYSQL_PORT"])
        except ValueError as exc:
            raise ImportConfigError("MYSQL_PORT must be an integer") from exc

        return cls(
            host=os.environ["MYSQL_HOST"],
            port=port,
            database=os.environ["MYSQL_DATABASE"],
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
        )


def build_table_rows(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    creator = data["creator"]
    audience = data["audienceProfileSnapshot"]
    follower_counts = platform_follower_counts(data)

    rows: dict[str, list[dict[str, Any]]] = {
        "creators": [
            {
                "creator_id": creator["creatorId"],
                "display_name": creator["displayName"],
                "avatar_url": creator.get("avatarUrl") or None,
                "niche_tags": json_value(creator["nicheTags"]),
                "timezone": creator["timezone"],
            }
        ],
        "platform_accounts": [
            {
                "account_id": item["accountId"],
                "creator_id": item["creatorId"],
                "platform": item["platform"],
                "platform_display_name": item["platformDisplayName"],
                "binding_status": item["bindingStatus"],
                "follower_count": follower_counts.get(item["platform"], 0),
                "sync_latency_seconds": item["syncLatencySeconds"],
                "collection_interval_seconds": item["collectionIntervalSeconds"],
                "data_scopes": json_value(item["dataScopes"]),
            }
            for item in data["platformAccounts"]
        ],
        "videos": [
            {
                "video_id": item["videoId"],
                "creator_id": item["creatorId"],
                "platform": item["platform"],
                "platform_label": item.get("platformLabel"),
                "title": item["title"],
                "content_type": item["contentType"],
                "content_type_label": item.get("contentTypeLabel"),
                "topic_tags": json_value(item["topicTags"]),
                "publish_time": mysql_datetime(item["publishTime"]),
                "lifecycle_stage": item["lifecycleStage"],
            }
            for item in data["videos"]
        ],
        "video_metric_snapshots": [
            {
                "snapshot_id": item["snapshotId"],
                "video_id": item["videoId"],
                "creator_id": item["creatorId"],
                "platform": item["platform"],
                "views": item["views"],
                "likes": item["likes"],
                "comments": item["comments"],
                "shares": item["shares"],
                "saves": item["saves"],
                "profile_visits": item["profileVisits"],
                "new_followers": item["newFollowers"],
                "completion_rate": item["completionRate"],
                "average_watch_seconds": item["averageWatchSeconds"],
                "engagement_rate": item["engagementRate"],
                "conversion_rate": item["conversionRate"],
                "comment_rate": item["commentRate"],
                "save_rate": item["saveRate"],
                "share_rate": item["shareRate"],
                "collected_at": mysql_datetime(item["collectedAt"]),
            }
            for item in data["videoMetricSnapshots"]
        ],
        "video_traffic_source_metrics": [
            {
                "video_id": item["videoId"],
                "source": item["source"],
                "views": item["views"],
                "new_followers": item["newFollowers"],
                "conversion_rate": item["conversionRate"],
                "save_rate": item["saveRate"],
                "comment_rate": item["commentRate"],
            }
            for item in data["videoTrafficSourceMetrics"]
        ],
        "creator_metric_snapshots": [
            {
                "snapshot_id": item["snapshotId"],
                "creator_id": item["creatorId"],
                "metric_date": item["date"],
                "total_followers": item["totalFollowers"],
                "new_followers": item["newFollowers"],
                "lost_followers": item["lostFollowers"],
                "net_followers": item["netFollowers"],
                "total_views": item["totalViews"],
                "total_interactions": item["totalInteractions"],
                "profile_visits": item["profileVisits"],
                "follower_growth_rate": item["followerGrowthRate"],
                "view_to_follower_rate": item["viewToFollowerRate"],
                "stickiness_score": item["stickinessScore"],
                "growth_health_score": item["growthHealthScore"],
            }
            for item in data["creatorMetricSnapshots"]
        ],
        "audience_profile_snapshots": [
            {
                "snapshot_id": audience["snapshotId"],
                "creator_id": audience["creatorId"],
                "gender": json_value(audience["gender"]),
                "age_groups": json_value(audience["ageGroups"]),
                "regions": json_value(audience["regions"]),
                "active_hours": json_value(audience["activeHours"]),
                "interest_tags": json_value(audience["interestTags"]),
                "high_value_segments": json_value(audience["highValueSegments"]),
            }
        ],
        "topic_trend_snapshots": [
            {
                "topic_id": item["topicId"],
                "topic_name": item["topicName"],
                "platforms": json_value(item["platforms"]),
                "heat_score": item["heatScore"],
                "growth_rate": item["growthRate"],
                "audience_fit_score": item["audienceFitScore"],
                "creator_fit_score": item["creatorFitScore"],
                "risk_level": item["riskLevel"],
            }
            for item in data["topicTrendSnapshots"]
        ],
        "insights": [
            {
                "insight_id": item["insightId"],
                "creator_id": item["creatorId"],
                "type": item["type"],
                "scope": item["scope"],
                "target_id": item["targetId"],
                "title": item["title"],
                "summary": item["summary"],
                "priority": item["priority"],
                "generated_by": item["generatedBy"],
                "generated_at": mysql_datetime(item["generatedAt"]),
                "page_targets": json_value(item["pageTargets"]),
            }
            for item in data["insights"]
        ],
        "insight_evidence_metrics": [],
        "recommended_actions": [],
        "spark_platform_metric_summaries": calculate_platform_summaries(
            data,
            "spark_static_mock_001",
            "2026-06-15T00:00:00",
        ),
        "spark_video_follower_contributions": calculate_video_contributions(
            data,
            "spark_static_mock_001",
            "2026-06-15T00:00:00",
        ),
    }

    for insight in data["insights"]:
        for position, metric in enumerate(insight["evidenceMetrics"], start=1):
            rows["insight_evidence_metrics"].append(
                {
                    "insight_id": insight["insightId"],
                    "position": position,
                    "label": metric["label"],
                    "value_json": json_value(metric.get("value")),
                    "unit": metric.get("unit"),
                    "direction": metric.get("direction"),
                }
            )

        for position, action in enumerate(insight["recommendedActions"], start=1):
            rows["recommended_actions"].append(
                {
                    "action_id": action["actionId"],
                    "insight_id": insight["insightId"],
                    "position": position,
                    "title": action["title"],
                    "description": action["description"],
                    "expected_impact": action.get("expectedImpact"),
                    "related_page": action.get("relatedPage"),
                }
            )

    return rows


def validate_rows(rows: dict[str, list[dict[str, Any]]]) -> None:
    missing_tables = [table for table in TABLE_ORDER if table not in rows]
    if missing_tables:
        raise AssertionError(f"Missing mapped tables: {', '.join(missing_tables)}")

    creator_ids = {row["creator_id"] for row in rows["creators"]}
    video_ids = {row["video_id"] for row in rows["videos"]}
    insight_ids = {row["insight_id"] for row in rows["insights"]}

    for table in ["platform_accounts", "videos", "creator_metric_snapshots", "audience_profile_snapshots", "insights"]:
        for row in rows[table]:
            if row["creator_id"] not in creator_ids:
                raise AssertionError(f"{table} references unknown creator_id={row['creator_id']}")

    for table in ["video_metric_snapshots", "video_traffic_source_metrics"]:
        for row in rows[table]:
            if row["video_id"] not in video_ids:
                raise AssertionError(f"{table} references unknown video_id={row['video_id']}")

    for table in ["insight_evidence_metrics", "recommended_actions"]:
        for row in rows[table]:
            if row["insight_id"] not in insight_ids:
                raise AssertionError(f"{table} references unknown insight_id={row['insight_id']}")

    for table in ["spark_platform_metric_summaries", "spark_video_follower_contributions"]:
        for row in rows[table]:
            if row["creator_id"] not in creator_ids:
                raise AssertionError(f"{table} references unknown creator_id={row['creator_id']}")

    for row in rows["spark_video_follower_contributions"]:
        if row["video_id"] not in video_ids:
            raise AssertionError(f"spark_video_follower_contributions references unknown video_id={row['video_id']}")


def insert_sql(table: str, sample_row: dict[str, Any]) -> str:
    columns = list(sample_row)
    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(f"`{column}`" for column in columns)
    update_columns = [column for column in columns if column not in PRIMARY_KEYS[table]]
    update_sql = ", ".join(f"`{column}` = VALUES(`{column}`)" for column in update_columns)
    return f"INSERT INTO `{table}` ({column_sql}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_sql}"


def write_mysql(rows: dict[str, list[dict[str, Any]]], config: MySQLConfig) -> None:
    try:
        import pymysql
    except ImportError as exc:
        raise ImportConfigError("PyMySQL is not installed. Run: pip install -r requirements.txt") from exc

    connection = pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.database,
        charset="utf8mb4",
        autocommit=False,
    )
    try:
        with connection.cursor() as cursor:
            for table in TABLE_ORDER:
                table_rows = rows[table]
                if not table_rows:
                    continue
                sql = insert_sql(table, table_rows[0])
                values = [tuple(row.values()) for row in table_rows]
                cursor.executemany(sql, values)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def row_counts(rows: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {table: len(rows[table]) for table in TABLE_ORDER}


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CreatorPulse MVP mock data into MySQL")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH, help="Path to creatorpulse_mvp_mock.json")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH, help="Optional .env file path")
    parser.add_argument("--execute", action="store_true", help="Actually write rows to MySQL. Default is dry-run.")
    args = parser.parse_args()

    load_env_file(args.env_file)
    data = load_json(args.data)
    rows = build_table_rows(data)
    validate_rows(rows)

    if args.execute:
        config = MySQLConfig.from_env()
        write_mysql(rows, config)
        mode = "mysql-import"
    else:
        mode = "dry-run"

    print(json.dumps({"status": "ok", "mode": mode, "counts": row_counts(rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
