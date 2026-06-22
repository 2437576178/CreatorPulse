"""Offline daily metrics aggregation for CreatorPulse.

This job is the batch counterpart to the realtime Spark Streaming path. The
MVP dry-run uses local mock events so formulas and output contracts can be
tested before VM scheduling writes to MySQL.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT_DIR / ".env"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.import_mock_to_mysql import ImportConfigError, MySQLConfig, load_env_file  # noqa: E402


OFFLINE_TABLE_ORDER = [
    "offline_batch_runs",
    "offline_creator_daily_metrics",
    "offline_platform_daily_metrics",
    "offline_video_daily_metrics",
    "offline_content_type_daily_metrics",
]

OFFLINE_PRIMARY_KEYS = {
    "offline_batch_runs": {"batch_run_id"},
    "offline_creator_daily_metrics": {"creator_id", "metric_date"},
    "offline_platform_daily_metrics": {"creator_id", "platform", "metric_date"},
    "offline_video_daily_metrics": {"creator_id", "video_id", "metric_date"},
    "offline_content_type_daily_metrics": {"creator_id", "content_type", "metric_date"},
    "creator_reports": {"report_id"},
}


def pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def bounded_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()


def safe_id(*parts: Any) -> str:
    raw = "_".join(str(part) for part in parts if part is not None)
    return "".join(char if char.isalnum() else "_" for char in raw)[:96]


def build_batch_run(
    batch_run_id: str,
    start_date: str,
    end_date: str,
    input_count: int,
    output_count: int,
    status: str = "SUCCESS",
    triggered_by: str = "MANUAL",
) -> dict[str, Any]:
    timestamp = now_iso()
    return {
        "batch_run_id": batch_run_id,
        "job_name": "offline_daily_metrics",
        "job_type": "DAILY_AGGREGATION",
        "period_start": start_date,
        "period_end": end_date,
        "status": status,
        "triggered_by": triggered_by,
        "input_event_count": input_count,
        "output_row_count": output_count,
        "error_message": None,
        "started_at": timestamp,
        "finished_at": timestamp,
    }


def filter_raw_events(
    raw_events: list[dict[str, Any]],
    start_date: str,
    end_date: str,
    creator_id: str | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for event in raw_events:
        event_date = str(event["event_date"])
        if event_date < start_date or event_date > end_date:
            continue
        if creator_id and event["creator_id"] != creator_id:
            continue
        rows.append(event)
    return rows


def video_content_type_map(videos: list[dict[str, Any]]) -> dict[str, str]:
    mapping = {}
    for video in videos:
        video_id = video.get("videoId") or video.get("video_id")
        content_type = video.get("contentType") or video.get("content_type") or "UNKNOWN"
        if video_id:
            mapping[video_id] = content_type
    return mapping


def aggregate_group(
    rows: list[dict[str, Any]],
    batch_run_id: str,
    metric_date: str,
    extra_keys: dict[str, Any],
) -> dict[str, Any]:
    views = sum(int(row["play_delta"]) for row in rows)
    likes = sum(int(row["like_delta"]) for row in rows)
    comments = sum(int(row["comment_delta"]) for row in rows)
    shares = sum(int(row["share_delta"]) for row in rows)
    saves = sum(int(row["save_delta"]) for row in rows)
    interactions = likes + comments + shares + saves
    profile_visits = sum(int(row["profile_visit_delta"]) for row in rows)
    new_followers = sum(int(row["new_follower_delta"]) for row in rows)
    lost_followers = sum(int(row["lost_follower_delta"]) for row in rows)
    view_to_follower_rate = pct(new_followers, views)
    engagement_rate = pct(interactions, views)
    profile_conversion_rate = pct(new_followers, profile_visits)
    stickiness_score = bounded_score(engagement_rate * 420)
    growth_health_score = bounded_score(view_to_follower_rate * 7200 + profile_conversion_rate * 120 + stickiness_score * 0.35)
    return {
        **extra_keys,
        "metric_date": metric_date,
        "views_delta": views,
        "likes_delta": likes,
        "comments_delta": comments,
        "shares_delta": shares,
        "saves_delta": saves,
        "interactions_delta": interactions,
        "profile_visits_delta": profile_visits,
        "new_followers_delta": new_followers,
        "lost_followers_delta": lost_followers,
        "net_followers_delta": new_followers - lost_followers,
        "view_to_follower_rate": view_to_follower_rate,
        "engagement_rate": engagement_rate,
        "stickiness_score": stickiness_score,
        "growth_health_score": growth_health_score,
        "batch_run_id": batch_run_id,
    }


def aggregate_daily_metrics(
    raw_events: list[dict[str, Any]],
    videos: list[dict[str, Any]],
    batch_run_id: str,
    start_date: str,
    end_date: str,
    creator_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    filtered = filter_raw_events(raw_events, start_date, end_date, creator_id)
    content_types = video_content_type_map(videos)

    creator_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    platform_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    video_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    content_type_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for event in filtered:
        metric_date = str(event["event_date"])
        creator_key = (event["creator_id"], metric_date)
        platform_key = (event["creator_id"], event["platform"], metric_date)
        video_key = (event["creator_id"], event["video_id"], metric_date)
        content_type_key = (event["creator_id"], content_types.get(event["video_id"], "UNKNOWN"), metric_date)
        creator_groups[creator_key].append(event)
        platform_groups[platform_key].append(event)
        video_groups[video_key].append(event)
        content_type_groups[content_type_key].append(event)

    creator_rows = []
    for (group_creator_id, metric_date), rows in sorted(creator_groups.items()):
        base = aggregate_group(rows, batch_run_id, metric_date, {"creator_id": group_creator_id})
        creator_rows.append(
            {
                "creator_id": base["creator_id"],
                "metric_date": base["metric_date"],
                "total_views_delta": base["views_delta"],
                "total_interactions_delta": base["interactions_delta"],
                "profile_visits_delta": base["profile_visits_delta"],
                "new_followers_delta": base["new_followers_delta"],
                "lost_followers_delta": base["lost_followers_delta"],
                "net_followers_delta": base["net_followers_delta"],
                "view_to_follower_rate": base["view_to_follower_rate"],
                "engagement_rate": base["engagement_rate"],
                "stickiness_score": base["stickiness_score"],
                "growth_health_score": base["growth_health_score"],
                "batch_run_id": batch_run_id,
            }
        )

    platform_rows = []
    for (group_creator_id, platform, metric_date), rows in sorted(platform_groups.items()):
        base = aggregate_group(rows, batch_run_id, metric_date, {"creator_id": group_creator_id, "platform": platform})
        platform_rows.append(
            {
                "creator_id": base["creator_id"],
                "platform": base["platform"],
                "metric_date": base["metric_date"],
                "views_delta": base["views_delta"],
                "interactions_delta": base["interactions_delta"],
                "profile_visits_delta": base["profile_visits_delta"],
                "new_followers_delta": base["new_followers_delta"],
                "lost_followers_delta": base["lost_followers_delta"],
                "view_to_follower_rate": base["view_to_follower_rate"],
                "engagement_rate": base["engagement_rate"],
                "contribution_score": bounded_score(base["new_followers_delta"] * 0.02 + base["view_to_follower_rate"] * 5000),
                "batch_run_id": batch_run_id,
            }
        )

    video_rows = []
    for (group_creator_id, video_id, metric_date), rows in sorted(video_groups.items()):
        platform = rows[0]["platform"]
        base = aggregate_group(rows, batch_run_id, metric_date, {"creator_id": group_creator_id, "video_id": video_id, "platform": platform})
        video_rows.append(
            {
                "creator_id": base["creator_id"],
                "video_id": base["video_id"],
                "platform": base["platform"],
                "metric_date": base["metric_date"],
                "views_delta": base["views_delta"],
                "likes_delta": base["likes_delta"],
                "comments_delta": base["comments_delta"],
                "shares_delta": base["shares_delta"],
                "saves_delta": base["saves_delta"],
                "profile_visits_delta": base["profile_visits_delta"],
                "new_followers_delta": base["new_followers_delta"],
                "lost_followers_delta": base["lost_followers_delta"],
                "view_to_follower_rate": base["view_to_follower_rate"],
                "engagement_rate": base["engagement_rate"],
                "follower_contribution_score": bounded_score(base["new_followers_delta"] * 0.03 + base["view_to_follower_rate"] * 5000),
                "batch_run_id": batch_run_id,
            }
        )

    content_type_rows = []
    for (group_creator_id, content_type, metric_date), rows in sorted(content_type_groups.items()):
        base = aggregate_group(rows, batch_run_id, metric_date, {"creator_id": group_creator_id, "content_type": content_type})
        content_type_rows.append(
            {
                "creator_id": base["creator_id"],
                "content_type": base["content_type"],
                "metric_date": base["metric_date"],
                "video_count": len({row["video_id"] for row in rows}),
                "views_delta": base["views_delta"],
                "interactions_delta": base["interactions_delta"],
                "new_followers_delta": base["new_followers_delta"],
                "view_to_follower_rate": base["view_to_follower_rate"],
                "engagement_rate": base["engagement_rate"],
                "efficiency_score": bounded_score(base["new_followers_delta"] * 0.03 + base["engagement_rate"] * 100),
                "batch_run_id": batch_run_id,
            }
        )

    output_count = len(creator_rows) + len(platform_rows) + len(video_rows) + len(content_type_rows)
    return {
        "offline_batch_runs": [build_batch_run(batch_run_id, start_date, end_date, len(filtered), output_count)],
        "offline_creator_daily_metrics": creator_rows,
        "offline_platform_daily_metrics": platform_rows,
        "offline_video_daily_metrics": video_rows,
        "offline_content_type_daily_metrics": content_type_rows,
    }


def build_mock_inputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        from kafka_tools.mock_event_builder import build_events
        from kafka_tools.mock_producer import load_mock
        from spark_jobs.kafka_events_to_mysql import archive_raw_video_stat_events
    except ImportError:
        from kafka_tools.mock_event_builder import build_events
        from kafka_tools.mock_producer import load_mock
        from kafka_events_to_mysql import archive_raw_video_stat_events

    data = load_mock()
    return archive_raw_video_stat_events(build_events(data)), data["videos"]


def normalize_raw_event(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    event_date = normalized.get("event_date")
    fetch_time = normalized.get("fetch_time")
    normalized["event_date"] = event_date.isoformat() if hasattr(event_date, "isoformat") else str(event_date)
    normalized["fetch_time"] = fetch_time.isoformat(sep=" ") if hasattr(fetch_time, "isoformat") else str(fetch_time)
    return normalized


def normalize_video(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "video_id": row.get("video_id"),
        "videoId": row.get("video_id"),
        "content_type": row.get("content_type") or "UNKNOWN",
        "contentType": row.get("content_type") or "UNKNOWN",
    }


def connect_mysql(config: MySQLConfig) -> Any:
    try:
        import pymysql
    except ImportError as exc:
        raise ImportConfigError("PyMySQL is not installed. Run: pip install -r requirements.txt") from exc

    return pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.database,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def read_mysql_inputs(config: MySQLConfig, start_date: str, end_date: str, creator_id: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    connection = connect_mysql(config)
    try:
        params: list[Any] = [start_date, end_date]
        where = "event_date BETWEEN %s AND %s"
        if creator_id:
            where += " AND creator_id = %s"
            params.append(creator_id)
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT event_id, creator_id, platform, video_id, event_type, event_date, fetch_time,
                       play_delta, like_delta, comment_delta, share_delta, save_delta,
                       profile_visit_delta, new_follower_delta, lost_follower_delta
                FROM raw_video_stat_events
                WHERE {where}
                ORDER BY event_date, fetch_time, event_id
                """,
                params,
            )
            raw_events = [normalize_raw_event(row) for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT video_id, content_type
                FROM videos
                WHERE creator_id IN (
                    SELECT DISTINCT creator_id
                    FROM raw_video_stat_events
                    WHERE event_date BETWEEN %s AND %s
                )
                ORDER BY video_id
                """,
                [start_date, end_date],
            )
            videos = [normalize_video(row) for row in cursor.fetchall()]
        return raw_events, videos
    finally:
        connection.close()


def upsert_sql(table: str, sample_row: dict[str, Any]) -> str:
    columns = list(sample_row)
    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(f"`{column}`" for column in columns)
    update_columns = [column for column in columns if column not in OFFLINE_PRIMARY_KEYS[table]]
    update_sql = ", ".join(f"`{column}` = VALUES(`{column}`)" for column in update_columns)
    return f"INSERT INTO `{table}` ({column_sql}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_sql}"


def write_mysql_rows(rows: dict[str, list[dict[str, Any]]], config: MySQLConfig) -> None:
    connection = connect_mysql(config)
    try:
        with connection.cursor() as cursor:
            for table in OFFLINE_TABLE_ORDER:
                table_rows = rows.get(table, [])
                if not table_rows:
                    continue
                sql = upsert_sql(table, table_rows[0])
                cursor.executemany(sql, [tuple(row.values()) for row in table_rows])
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate archived CreatorPulse events into offline daily metrics")
    parser.add_argument("--start-date", default="2026-06-14")
    parser.add_argument("--end-date", default="2026-06-14")
    parser.add_argument("--creator-id", default=None)
    parser.add_argument("--batch-run-id", default=None)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--triggered-by", default="MANUAL", choices=["MANUAL", "SCHEDULED"])
    parser.add_argument("--execute", action="store_true", help="Read raw events from MySQL and write offline daily metric tables")
    args = parser.parse_args()

    batch_run_id = args.batch_run_id or safe_id("offline_daily", args.start_date, args.end_date, args.creator_id or "all", now_iso())
    if args.execute:
        load_env_file(args.env_file)
        config = MySQLConfig.from_env()
        raw_events, videos = read_mysql_inputs(config, args.start_date, args.end_date, args.creator_id)
        mode = "mysql-write"
    else:
        raw_events, videos = build_mock_inputs()
        mode = "dry-run"
    result = aggregate_daily_metrics(raw_events, videos, batch_run_id, args.start_date, args.end_date, args.creator_id)
    result["offline_batch_runs"] = [
        build_batch_run(
            batch_run_id,
            args.start_date,
            args.end_date,
            input_count=len(filter_raw_events(raw_events, args.start_date, args.end_date, args.creator_id)),
            output_count=sum(len(rows) for table, rows in result.items() if table != "offline_batch_runs"),
            triggered_by=args.triggered_by,
        )
    ]
    if args.execute:
        write_mysql_rows(result, config)
    counts = {table: len(rows) for table, rows in result.items()}
    print(
        json.dumps(
            {
                "status": "ok",
                "mode": mode,
                "dateRange": {"startDate": args.start_date, "endDate": args.end_date},
                "counts": counts,
                "sample": {
                    "creatorDaily": result["offline_creator_daily_metrics"][0] if result["offline_creator_daily_metrics"] else None,
                    "platformDaily": result["offline_platform_daily_metrics"][0] if result["offline_platform_daily_metrics"] else None,
                    "videoDaily": result["offline_video_daily_metrics"][0] if result["offline_video_daily_metrics"] else None,
                    "contentTypeDaily": result["offline_content_type_daily_metrics"][0] if result["offline_content_type_daily_metrics"] else None,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
