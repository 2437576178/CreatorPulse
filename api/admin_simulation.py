"""Admin simulation monitoring queries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from mysql_repository import MySQLRepository, iso_datetime


def platform_label(platform: str) -> str:
    return {
        "DOUYIN": "抖音",
        "BILIBILI": "B站",
        "XIAOHONGSHU": "小红书",
    }.get(platform, platform)


class AdminSimulationRepository:
    def __init__(self, repository: MySQLRepository | None = None) -> None:
        self.repository = repository or MySQLRepository()

    def get_status(self) -> dict[str, Any]:
        with self.repository.engine.connect() as connection:
            counts = self.repository.fetch_all(
                connection,
                """
                SELECT
                  (SELECT COUNT(*) FROM creators) AS creator_count,
                  (SELECT COUNT(*) FROM platform_accounts WHERE binding_status = 'BOUND') AS bound_platform_count,
                  (SELECT COUNT(*) FROM videos) AS video_count,
                  (SELECT COUNT(*) FROM spark_platform_metric_summaries) AS spark_platform_rows
                """,
            )[0]
            latest = self.repository.fetch_all(
                connection,
                """
                SELECT run_id, calculated_at
                FROM spark_platform_metric_summaries
                ORDER BY calculated_at DESC, run_id DESC
                LIMIT 1
                """,
            )

        latest_row = latest[0] if latest else None
        return {
            "dataSource": "mysql",
            "creatorCount": counts["creator_count"],
            "boundPlatformCount": counts["bound_platform_count"],
            "videoCount": counts["video_count"],
            "sparkPlatformRows": counts["spark_platform_rows"],
            "latestSparkBatch": latest_row["run_id"] if latest_row else None,
            "latestWriteAt": iso_datetime(latest_row["calculated_at"]) if latest_row else None,
        }

    def list_creators(self) -> dict[str, list[dict[str, Any]]]:
        with self.repository.engine.connect() as connection:
            rows = self.repository.fetch_all(
                connection,
                """
                SELECT
                  c.creator_id,
                  c.display_name,
                  pa.platform,
                  pa.binding_status,
                  pa.sync_latency_seconds,
                  MAX(sp.calculated_at) AS latest_write_at,
                  MAX(sp.run_id) AS latest_run_id
                FROM creators c
                LEFT JOIN platform_accounts pa ON pa.creator_id = c.creator_id
                LEFT JOIN spark_platform_metric_summaries sp
                  ON sp.creator_id = c.creator_id AND sp.platform = pa.platform
                GROUP BY c.creator_id, c.display_name, pa.platform, pa.binding_status, pa.sync_latency_seconds
                ORDER BY c.creator_id, pa.platform
                """,
            )

        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            creator = grouped.setdefault(
                row["creator_id"],
                {
                    "creatorId": row["creator_id"],
                    "displayName": row["display_name"],
                    "platforms": [],
                    "latestWriteAt": None,
                    "latestRunId": None,
                },
            )
            if row["platform"]:
                creator["platforms"].append(
                    {
                        "platform": row["platform"],
                        "label": platform_label(row["platform"]),
                        "bindingStatus": row["binding_status"],
                        "syncLatencySeconds": row["sync_latency_seconds"],
                        "latestWriteAt": iso_datetime(row["latest_write_at"]) if row["latest_write_at"] else None,
                        "latestRunId": row["latest_run_id"],
                    }
                )
            if row["latest_write_at"]:
                latest = iso_datetime(row["latest_write_at"])
                if creator["latestWriteAt"] is None or latest > creator["latestWriteAt"]:
                    creator["latestWriteAt"] = latest
                    creator["latestRunId"] = row["latest_run_id"]

        return {"creators": list(grouped.values())}

    def list_events(self, limit: int = 30) -> dict[str, list[dict[str, Any]]]:
        with self.repository.engine.connect() as connection:
            rows = self.repository.fetch_all(
                connection,
                """
                SELECT
                  sp.run_id,
                  sp.creator_id,
                  c.display_name,
                  sp.platform,
                  sp.total_views,
                  sp.new_followers,
                  sp.video_count,
                  sp.conversion_rate,
                  sp.calculated_at
                FROM spark_platform_metric_summaries sp
                INNER JOIN creators c ON c.creator_id = sp.creator_id
                ORDER BY sp.calculated_at DESC, sp.run_id DESC, sp.creator_id, sp.platform
                LIMIT :limit
                """,
                {"limit": limit},
            )

        return {
            "events": [
                {
                    "runId": row["run_id"],
                    "creatorId": row["creator_id"],
                    "displayName": row["display_name"],
                    "platform": row["platform"],
                    "platformLabel": platform_label(row["platform"]),
                    "totalViews": row["total_views"],
                    "newFollowers": row["new_followers"],
                    "videoCount": row["video_count"],
                    "conversionRate": float(row["conversion_rate"]),
                    "calculatedAt": iso_datetime(row["calculated_at"]),
                }
                for row in rows
            ]
        }

    def get_offline_status(self) -> dict[str, Any]:
        with self.repository.engine.connect() as connection:
            counts = self.repository.fetch_all(
                connection,
                """
                SELECT
                  (SELECT COUNT(*) FROM raw_video_stat_events) AS raw_event_count,
                  (SELECT COUNT(*) FROM offline_creator_daily_metrics) AS creator_daily_count,
                  (SELECT COUNT(*) FROM creator_reports) AS report_count,
                  (SELECT COUNT(*) FROM offline_recompute_requests WHERE status = 'PENDING') AS pending_recompute_count
                """,
            )[0]
            recent_runs = self.repository.fetch_all(
                connection,
                """
                SELECT batch_run_id, job_name, job_type, period_start, period_end, status,
                       triggered_by, input_event_count, output_row_count, error_message,
                       started_at, finished_at
                FROM offline_batch_runs
                ORDER BY started_at DESC, batch_run_id DESC
                LIMIT 10
                """,
            )
            recent_reports = self.repository.fetch_all(
                connection,
                """
                SELECT report_id, creator_id, report_type, period_start, period_end, status,
                       title, generated_at, batch_run_id
                FROM creator_reports
                ORDER BY generated_at DESC, report_id DESC
                LIMIT 10
                """,
            )

        return {
            "dataSource": "mysql",
            "rawEventCount": counts["raw_event_count"],
            "creatorDailyCount": counts["creator_daily_count"],
            "reportCount": counts["report_count"],
            "pendingRecomputeCount": counts["pending_recompute_count"],
            "recentRuns": [
                {
                    "batchRunId": row["batch_run_id"],
                    "jobName": row["job_name"],
                    "jobType": row["job_type"],
                    "periodStart": iso_datetime(row["period_start"]) if row["period_start"] else None,
                    "periodEnd": iso_datetime(row["period_end"]) if row["period_end"] else None,
                    "status": row["status"],
                    "triggeredBy": row["triggered_by"],
                    "inputEventCount": row["input_event_count"],
                    "outputRowCount": row["output_row_count"],
                    "errorMessage": row["error_message"],
                    "startedAt": iso_datetime(row["started_at"]),
                    "finishedAt": iso_datetime(row["finished_at"]) if row["finished_at"] else None,
                }
                for row in recent_runs
            ],
            "recentReports": [
                {
                    "reportId": row["report_id"],
                    "creatorId": row["creator_id"],
                    "reportType": row["report_type"],
                    "periodStart": iso_datetime(row["period_start"]),
                    "periodEnd": iso_datetime(row["period_end"]),
                    "status": row["status"],
                    "title": row["title"],
                    "generatedAt": iso_datetime(row["generated_at"]),
                    "batchRunId": row["batch_run_id"],
                }
                for row in recent_reports
            ],
        }

    def create_recompute_request(
        self,
        creator_id: str,
        period_start: str,
        period_end: str,
        recompute_scope: str = "ALL",
        requested_by: str = "admin",
    ) -> dict[str, Any]:
        allowed_scopes = {"CREATOR_DAILY", "PLATFORM_DAILY", "VIDEO_DAILY", "CONTENT_TYPE_DAILY", "REPORTS", "ALL"}
        scope = recompute_scope.upper()
        if scope not in allowed_scopes:
            raise ValueError("Invalid recompute scope")

        request_id = f"recompute_{uuid4().hex[:24]}"
        requested_at = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None).isoformat()
        with self.repository.engine.begin() as connection:
            connection.execute(
                text(
                    """
                INSERT INTO offline_recompute_requests
                  (request_id, creator_id, period_start, period_end, recompute_scope, status, requested_by, requested_at)
                VALUES
                  (:request_id, :creator_id, :period_start, :period_end, :recompute_scope, 'PENDING', :requested_by, :requested_at)
                """,
                ),
                {
                    "request_id": request_id,
                    "creator_id": creator_id,
                    "period_start": period_start,
                    "period_end": period_end,
                    "recompute_scope": scope,
                    "requested_by": requested_by,
                    "requested_at": requested_at,
                },
            )

        return {
            "requestId": request_id,
            "creatorId": creator_id,
            "periodStart": period_start,
            "periodEnd": period_end,
            "recomputeScope": scope,
            "status": "PENDING",
            "requestedBy": requested_by,
            "requestedAt": requested_at,
        }
