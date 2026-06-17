"""Admin simulation monitoring queries."""

from __future__ import annotations

from typing import Any

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
