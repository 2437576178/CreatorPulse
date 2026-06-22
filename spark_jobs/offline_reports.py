"""Generate CreatorPulse periodic reports from offline metric tables."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT_DIR / ".env"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.import_mock_to_mysql import MySQLConfig, load_env_file  # noqa: E402
from spark_jobs.offline_daily_metrics import connect_mysql, safe_id, upsert_sql  # noqa: E402


REPORT_LABELS = {
    "DAILY": "日报",
    "WEEKLY": "周报",
    "MONTHLY": "月报",
}

REPORT_TABLE_ORDER = ["offline_batch_runs", "creator_reports"]


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()


def report_id(creator_id: str, report_type: str, period_start: str, period_end: str) -> str:
    raw = f"report_{creator_id}_{report_type.lower()}_{period_start}_{period_end}"
    return "".join(char if char.isalnum() else "_" for char in raw)[:96]


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def sum_field(rows: list[dict[str, Any]], field: str) -> int:
    return sum(int(row.get(field, 0)) for row in rows)


def best_row(rows: list[dict[str, Any]], field: str) -> dict[str, Any] | None:
    if not rows:
        return None
    return max(rows, key=lambda row: row.get(field, 0))


def creator_display_name(data: dict[str, Any], creator_id: str) -> str:
    creator = data.get("creator") or {}
    if creator.get("creatorId") == creator_id:
        return creator.get("displayName") or "你的账号"
    return "你的账号"


def empty_report(
    creator_id: str,
    report_type: str,
    period_start: str,
    period_end: str,
    batch_run_id: str,
) -> dict[str, Any]:
    label = REPORT_LABELS.get(report_type, report_type)
    generated_at = now_iso()
    return {
        "report_id": report_id(creator_id, report_type, period_start, period_end),
        "creator_id": creator_id,
        "report_type": report_type,
        "period_start": period_start,
        "period_end": period_end,
        "status": "EMPTY",
        "title": f"{period_start} 至 {period_end} {label}",
        "summary": "等待离线任务生成足够数据后，这里会展示你的账号复盘结论。",
        "highlights_json": dumps([]),
        "risks_json": dumps(["当前周期缺少离线汇总数据，暂时不能生成有效判断。"]),
        "actions_json": dumps(["确认实时链路正在写入 raw_video_stat_events，然后重新运行离线汇总任务。"]),
        "metrics_json": dumps({}),
        "generated_at": generated_at,
        "batch_run_id": batch_run_id,
    }


def generate_report_for_creator(
    creator_id: str,
    daily_metrics: dict[str, list[dict[str, Any]]],
    data: dict[str, Any],
    report_type: str,
    period_start: str,
    period_end: str,
    batch_run_id: str,
) -> dict[str, Any]:
    creator_rows = [
        row
        for row in daily_metrics.get("offline_creator_daily_metrics", [])
        if row["creator_id"] == creator_id and period_start <= str(row["metric_date"]) <= period_end
    ]
    if not creator_rows:
        return empty_report(creator_id, report_type, period_start, period_end, batch_run_id)

    platform_rows = [
        row
        for row in daily_metrics.get("offline_platform_daily_metrics", [])
        if row["creator_id"] == creator_id and period_start <= str(row["metric_date"]) <= period_end
    ]
    video_rows = [
        row
        for row in daily_metrics.get("offline_video_daily_metrics", [])
        if row["creator_id"] == creator_id and period_start <= str(row["metric_date"]) <= period_end
    ]
    content_type_rows = [
        row
        for row in daily_metrics.get("offline_content_type_daily_metrics", [])
        if row["creator_id"] == creator_id and period_start <= str(row["metric_date"]) <= period_end
    ]

    views = sum_field(creator_rows, "total_views_delta")
    interactions = sum_field(creator_rows, "total_interactions_delta")
    new_followers = sum_field(creator_rows, "new_followers_delta")
    lost_followers = sum_field(creator_rows, "lost_followers_delta")
    net_followers = sum_field(creator_rows, "net_followers_delta")
    profile_visits = sum_field(creator_rows, "profile_visits_delta")
    view_to_follower_rate = round(new_followers / views, 6) if views else 0.0
    engagement_rate = round(interactions / views, 6) if views else 0.0
    avg_health = round(sum(float(row["growth_health_score"]) for row in creator_rows) / len(creator_rows), 2)
    avg_stickiness = round(sum(float(row["stickiness_score"]) for row in creator_rows) / len(creator_rows), 2)

    best_platform = best_row(platform_rows, "new_followers_delta")
    best_video = best_row(video_rows, "new_followers_delta")
    best_type = best_row(content_type_rows, "new_followers_delta")
    label = REPORT_LABELS.get(report_type, report_type)
    display_name = creator_display_name(data, creator_id)
    generated_at = now_iso()

    platform_text = best_platform["platform"] if best_platform else "暂无平台"
    type_text = best_type["content_type"] if best_type else "暂无类型"
    summary = f"你的账号（{display_name}）本周期净增 {net_followers} 粉丝，{platform_text} 贡献最高，{type_text} 内容最值得继续投入。"

    highlights = [
        f"你的账号本周期新增粉丝 {new_followers}，净增 {net_followers}。",
        f"{platform_text} 是本周期最强平台，带来 {best_platform['new_followers_delta'] if best_platform else 0} 新粉。",
        f"{type_text} 内容贡献最高，适合继续复刻。",
    ]
    risks = []
    if lost_followers > 0:
        risks.append(f"本周期流失粉丝 {lost_followers}，需要检查低粘性内容。")
    if view_to_follower_rate < 0.003:
        risks.append("播放转粉率偏低，部分流量可能没有有效进入主页或关注。")
    if not risks:
        risks.append("本周期没有明显离线风险，但仍需观察后续连续趋势。")

    actions = [
        f"下个周期优先复刻 {platform_text} 的高转粉内容结构。",
        f"围绕 {type_text} 内容继续做系列化发布。",
        "把评论问题和收藏需求整理成下一条内容选题。",
    ]
    metrics = {
        "views": views,
        "interactions": interactions,
        "profileVisits": profile_visits,
        "newFollowers": new_followers,
        "lostFollowers": lost_followers,
        "netFollowers": net_followers,
        "viewToFollowerRate": view_to_follower_rate,
        "engagementRate": engagement_rate,
        "stickinessScore": avg_stickiness,
        "growthHealthScore": avg_health,
        "bestPlatform": platform_text,
        "bestContentType": type_text,
        "bestVideoId": best_video["video_id"] if best_video else None,
    }

    return {
        "report_id": report_id(creator_id, report_type, period_start, period_end),
        "creator_id": creator_id,
        "report_type": report_type,
        "period_start": period_start,
        "period_end": period_end,
        "status": "GENERATED",
        "title": f"{period_start} 至 {period_end} {label}",
        "summary": summary,
        "highlights_json": dumps(highlights),
        "risks_json": dumps(risks),
        "actions_json": dumps(actions),
        "metrics_json": dumps(metrics),
        "generated_at": generated_at,
        "batch_run_id": batch_run_id,
    }


def generate_reports(
    daily_metrics: dict[str, list[dict[str, Any]]],
    data: dict[str, Any],
    report_type: str,
    period_start: str,
    period_end: str,
    batch_run_id: str,
    creator_id: str | None = None,
) -> list[dict[str, Any]]:
    report_type = report_type.upper()
    if report_type not in REPORT_LABELS:
        raise ValueError("report_type must be DAILY, WEEKLY, or MONTHLY")

    creator_ids = {row["creator_id"] for row in daily_metrics.get("offline_creator_daily_metrics", [])}
    if creator_id:
        creator_ids = {creator_id}
    if not creator_ids:
        creator_ids = {creator_id or (data.get("creator") or {}).get("creatorId") or "creator_unknown"}

    return [
        generate_report_for_creator(current_creator_id, daily_metrics, data, report_type, period_start, period_end, batch_run_id)
        for current_creator_id in sorted(creator_ids)
    ]


def camel_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "reportId": report["report_id"],
        "creatorId": report["creator_id"],
        "reportType": report["report_type"],
        "periodStart": str(report["period_start"]),
        "periodEnd": str(report["period_end"]),
        "status": report["status"],
        "title": report["title"],
        "summary": report["summary"],
        "highlights": json.loads(report["highlights_json"]),
        "risks": json.loads(report["risks_json"]),
        "actions": json.loads(report["actions_json"]),
        "metrics": json.loads(report["metrics_json"]),
        "generatedAt": str(report["generated_at"]),
        "batchRunId": report["batch_run_id"],
    }


def build_mock_daily_metrics(start_date: str, end_date: str, creator_id: str | None = None) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    from kafka_tools.mock_event_builder import build_events
    from kafka_tools.mock_producer import load_mock
    from spark_jobs.kafka_events_to_mysql import archive_raw_video_stat_events
    from spark_jobs.offline_daily_metrics import aggregate_daily_metrics

    data = load_mock()
    raw_rows = archive_raw_video_stat_events(build_events(data))
    return (
        aggregate_daily_metrics(raw_rows, data["videos"], "offline_daily_for_report_dry_run", start_date, end_date, creator_id),
        data,
    )


def normalize_date(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def normalize_creator(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "creatorId": row["creator_id"],
        "displayName": row["display_name"],
        "avatarUrl": row.get("avatar_url") or "",
        "nicheTags": [],
        "timezone": row.get("timezone") or "Asia/Shanghai",
    }


def read_mysql_report_inputs(
    config: MySQLConfig,
    period_start: str,
    period_end: str,
    creator_id: str | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    connection = connect_mysql(config)
    try:
        creator_params: list[Any] = []
        creator_where = ""
        if creator_id:
            creator_where = "WHERE creator_id = %s"
            creator_params.append(creator_id)

        metric_params: list[Any] = [period_start, period_end]
        metric_where = "metric_date BETWEEN %s AND %s"
        if creator_id:
            metric_where += " AND creator_id = %s"
            metric_params.append(creator_id)

        with connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM creators {creator_where} ORDER BY creator_id", creator_params)
            creators = {row["creator_id"]: normalize_creator(row) for row in cursor.fetchall()}

            cursor.execute(f"SELECT * FROM offline_creator_daily_metrics WHERE {metric_where} ORDER BY creator_id, metric_date", metric_params)
            creator_rows = [dict(row, metric_date=normalize_date(row["metric_date"])) for row in cursor.fetchall()]
            cursor.execute(f"SELECT * FROM offline_platform_daily_metrics WHERE {metric_where} ORDER BY creator_id, platform, metric_date", metric_params)
            platform_rows = [dict(row, metric_date=normalize_date(row["metric_date"])) for row in cursor.fetchall()]
            cursor.execute(f"SELECT * FROM offline_video_daily_metrics WHERE {metric_where} ORDER BY creator_id, video_id, metric_date", metric_params)
            video_rows = [dict(row, metric_date=normalize_date(row["metric_date"])) for row in cursor.fetchall()]
            cursor.execute(f"SELECT * FROM offline_content_type_daily_metrics WHERE {metric_where} ORDER BY creator_id, content_type, metric_date", metric_params)
            content_type_rows = [dict(row, metric_date=normalize_date(row["metric_date"])) for row in cursor.fetchall()]

        return (
            {
                "offline_creator_daily_metrics": creator_rows,
                "offline_platform_daily_metrics": platform_rows,
                "offline_video_daily_metrics": video_rows,
                "offline_content_type_daily_metrics": content_type_rows,
            },
            creators,
        )
    finally:
        connection.close()


def build_report_batch_run(
    batch_run_id: str,
    report_type: str,
    period_start: str,
    period_end: str,
    input_count: int,
    output_count: int,
    status: str = "SUCCESS",
    triggered_by: str = "MANUAL",
    error_message: str | None = None,
) -> dict[str, Any]:
    timestamp = now_iso()
    return {
        "batch_run_id": batch_run_id,
        "job_name": f"offline_reports_{report_type.lower()}",
        "job_type": "REPORT_GENERATION",
        "period_start": period_start,
        "period_end": period_end,
        "status": status,
        "triggered_by": triggered_by,
        "input_event_count": input_count,
        "output_row_count": output_count,
        "error_message": error_message,
        "started_at": timestamp,
        "finished_at": timestamp,
    }


def write_report_rows(batch_run: dict[str, Any], reports: list[dict[str, Any]], config: MySQLConfig) -> None:
    connection = connect_mysql(config)
    try:
        with connection.cursor() as cursor:
            rows_by_table = {"offline_batch_runs": [batch_run], "creator_reports": reports}
            for table in REPORT_TABLE_ORDER:
                table_rows = rows_by_table[table]
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


def generate_reports_from_mysql(
    daily_metrics: dict[str, list[dict[str, Any]]],
    creators: dict[str, dict[str, Any]],
    report_type: str,
    period_start: str,
    period_end: str,
    batch_run_id: str,
    creator_id: str | None = None,
) -> list[dict[str, Any]]:
    metric_creator_ids = {row["creator_id"] for row in daily_metrics.get("offline_creator_daily_metrics", [])}
    target_creator_ids = {creator_id} if creator_id else metric_creator_ids

    reports = []
    for current_creator_id in sorted(target_creator_ids):
        creator_data = {"creator": creators.get(current_creator_id) or {"creatorId": current_creator_id, "displayName": "你的账号"}}
        reports.extend(
            generate_reports(
                daily_metrics,
                creator_data,
                report_type=report_type,
                period_start=period_start,
                period_end=period_end,
                batch_run_id=batch_run_id,
                creator_id=current_creator_id,
            )
        )
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CreatorPulse offline reports")
    parser.add_argument("--report-type", default="DAILY", choices=sorted(REPORT_LABELS))
    parser.add_argument("--period-start", default="2026-06-14")
    parser.add_argument("--period-end", default="2026-06-14")
    parser.add_argument("--creator-id", default=None)
    parser.add_argument("--batch-run-id", default=None)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--triggered-by", default="MANUAL", choices=["MANUAL", "SCHEDULED"])
    parser.add_argument("--execute", action="store_true", help="Read offline daily metrics from MySQL and write creator_reports")
    args = parser.parse_args()

    batch_run_id = args.batch_run_id or safe_id("offline_report", args.report_type, args.period_start, args.period_end, args.creator_id or "all", now_iso())
    if args.execute:
        load_env_file(args.env_file)
        config = MySQLConfig.from_env()
        daily_metrics, creators = read_mysql_report_inputs(config, args.period_start, args.period_end, args.creator_id)
        reports = generate_reports_from_mysql(
            daily_metrics,
            creators,
            report_type=args.report_type,
            period_start=args.period_start,
            period_end=args.period_end,
            batch_run_id=batch_run_id,
            creator_id=args.creator_id,
        )
        batch_run = build_report_batch_run(
            batch_run_id,
            args.report_type,
            args.period_start,
            args.period_end,
            input_count=len(daily_metrics["offline_creator_daily_metrics"]),
            output_count=len(reports),
            triggered_by=args.triggered_by,
        )
        write_report_rows(batch_run, reports, config)
        mode = "mysql-write"
    else:
        daily_metrics, data = build_mock_daily_metrics(args.period_start, args.period_end, args.creator_id)
        reports = generate_reports(
            daily_metrics,
            data,
            report_type=args.report_type,
            period_start=args.period_start,
            period_end=args.period_end,
            batch_run_id=batch_run_id,
            creator_id=args.creator_id,
        )
        mode = "dry-run"

    print(
        json.dumps(
            {
                "status": "ok",
                "mode": mode,
                "counts": {"creator_reports": len(reports)},
                "sample": {"report": camel_report(reports[0]) if reports else None},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
