"""MySQL-backed repository for CreatorPulse MVP data."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from functools import cached_property
from typing import Any

from config import ConfigError, MySQLSettings
from spark_insights import merge_spark_insights
from view_model_builder import make_view_models


class MySQLRepositoryError(RuntimeError):
    """Raised when MySQL data cannot satisfy the API contract."""


def parse_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    return json.loads(value)


def iso_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def comparable_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def latest_rows_by_key(rows: list[dict[str, Any]], key: str, order_columns: tuple[str, ...]) -> list[dict[str, Any]]:
    latest: dict[Any, dict[str, Any]] = {}
    for row in rows:
        row_key = row[key]
        current = latest.get(row_key)
        if current is None:
            latest[row_key] = row
            continue
        row_order = tuple(comparable_value(row.get(column)) for column in order_columns)
        current_order = tuple(comparable_value(current.get(column)) for column in order_columns)
        if row_order > current_order:
            latest[row_key] = row
    return list(latest.values())


class MySQLRepository:
    """Repository implementation backed by the MVP MySQL schema."""

    @cached_property
    def engine(self) -> Any:
        try:
            from sqlalchemy import create_engine
        except ImportError as exc:
            raise ConfigError("SQLAlchemy is not installed. Run: pip install -r requirements.txt") from exc

        settings = MySQLSettings.from_env()
        return create_engine(settings.sqlalchemy_url, pool_pre_ping=True)

    def _list_creators(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = self.fetch_all(connection, "SELECT * FROM creators ORDER BY creator_id")
        return [
            {
                "creatorId": item["creator_id"],
                "displayName": item["display_name"],
                "avatarUrl": item["avatar_url"] or "",
                "nicheTags": parse_json(item["niche_tags"]),
                "timezone": item["timezone"],
            }
            for item in rows
        ]

    def get_health(self) -> dict[str, Any]:
        data = self.load_creator_payload("demo")
        return {
            "status": "ok",
            "dataSource": "mysql",
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

    def get_view_model(self, creator_id: str, key: str) -> dict[str, Any]:
        data = self.load_creator_payload(creator_id)
        view_models = make_view_models(data)
        if key not in view_models:
            raise KeyError(key)
        return {
            "meta": data["meta"],
            "creator": data["creator"],
            "data": view_models[key],
        }

    def list_reports(self, creator_id: str, report_type: str | None = None, page: int = 1, page_size: int = 10) -> dict[str, Any]:
        resolved_creator_id = self.resolve_creator_id(creator_id)
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        offset = (page - 1) * page_size
        params: dict[str, Any] = {"creator_id": resolved_creator_id, "limit": page_size, "offset": offset}
        where = "creator_id = :creator_id"
        if report_type:
            where += " AND report_type = :report_type"
            params["report_type"] = report_type.upper()

        with self.engine.connect() as connection:
            rows = self.fetch_all(
                connection,
                f"""
                SELECT *
                FROM creator_reports
                WHERE {where}
                ORDER BY generated_at DESC, period_end DESC, report_id
                LIMIT :limit OFFSET :offset
                """,
                params,
            )
            total_rows = self.fetch_all(
                connection,
                f"SELECT COUNT(*) AS total FROM creator_reports WHERE {where}",
                {key: value for key, value in params.items() if key not in {"limit", "offset"}},
            )

        return {
            "items": [self.map_report(row) for row in rows],
            "page": page,
            "pageSize": page_size,
            "total": int(total_rows[0]["total"]) if total_rows else 0,
        }

    def get_report(self, creator_id: str, report_id: str) -> dict[str, Any]:
        resolved_creator_id = self.resolve_creator_id(creator_id)
        with self.engine.connect() as connection:
            rows = self.fetch_all(
                connection,
                """
                SELECT *
                FROM creator_reports
                WHERE creator_id = :creator_id AND report_id = :report_id
                """,
                {"creator_id": resolved_creator_id, "report_id": report_id},
            )
        if not rows:
            raise KeyError(report_id)
        return self.map_report(rows[0])

    def load_creator_payload(self, creator_id: str) -> dict[str, Any]:
        resolved_creator_id = self.resolve_creator_id(creator_id)
        with self.engine.connect() as connection:
            rows = {
                "creators": self.fetch_all(
                    connection,
                    "SELECT * FROM creators WHERE creator_id = :creator_id ORDER BY creator_id",
                    {"creator_id": resolved_creator_id},
                ),
                "platform_accounts": self.fetch_all(
                    connection,
                    "SELECT * FROM platform_accounts WHERE creator_id = :creator_id ORDER BY account_id",
                    {"creator_id": resolved_creator_id},
                ),
                "videos": self.fetch_all(
                    connection,
                    "SELECT * FROM videos WHERE creator_id = :creator_id ORDER BY publish_time DESC, video_id",
                    {"creator_id": resolved_creator_id},
                ),
                "video_metric_snapshots": self.fetch_all(
                    connection,
                    """
                    SELECT snapshot.*
                    FROM video_metric_snapshots snapshot
                    INNER JOIN (
                        SELECT video_id, MAX(collected_at) AS collected_at
                        FROM video_metric_snapshots
                        WHERE creator_id = :creator_id
                        GROUP BY video_id
                    ) latest
                        ON latest.video_id = snapshot.video_id
                       AND latest.collected_at = snapshot.collected_at
                    WHERE snapshot.creator_id = :creator_id
                    ORDER BY snapshot.collected_at DESC, snapshot.snapshot_id
                    """,
                    {"creator_id": resolved_creator_id},
                ),
                "video_traffic_source_metrics": self.fetch_all(
                    connection,
                    """
                    SELECT traffic.*
                    FROM video_traffic_source_metrics traffic
                    INNER JOIN videos video ON video.video_id = traffic.video_id
                    WHERE video.creator_id = :creator_id
                    ORDER BY traffic.video_id, traffic.source
                    """,
                    {"creator_id": resolved_creator_id},
                ),
                "creator_metric_snapshots": self.fetch_all(
                    connection,
                    "SELECT * FROM creator_metric_snapshots WHERE creator_id = :creator_id ORDER BY metric_date",
                    {"creator_id": resolved_creator_id},
                ),
                "offline_creator_daily_metrics": self.fetch_optional_all(
                    connection,
                    """
                    SELECT *
                    FROM offline_creator_daily_metrics
                    WHERE creator_id = :creator_id
                    ORDER BY metric_date DESC
                    LIMIT 1
                    """,
                    {"creator_id": resolved_creator_id},
                ),
                "offline_content_type_daily_metrics": self.fetch_optional_all(
                    connection,
                    """
                    SELECT *
                    FROM offline_content_type_daily_metrics
                    WHERE creator_id = :creator_id
                      AND metric_date = (
                        SELECT MAX(metric_date)
                        FROM offline_content_type_daily_metrics
                        WHERE creator_id = :creator_id
                      )
                    ORDER BY new_followers_delta DESC, content_type
                    """,
                    {"creator_id": resolved_creator_id},
                ),
                "audience_profile_snapshots": self.fetch_all(
                    connection,
                    "SELECT * FROM audience_profile_snapshots WHERE creator_id = :creator_id ORDER BY snapshot_id",
                    {"creator_id": resolved_creator_id},
                ),
                "topic_trend_snapshots": self.fetch_all(connection, "SELECT * FROM topic_trend_snapshots ORDER BY heat_score DESC, topic_id"),
                "insights": self.fetch_all(
                    connection,
                    "SELECT * FROM insights WHERE creator_id = :creator_id ORDER BY generated_at DESC, insight_id",
                    {"creator_id": resolved_creator_id},
                ),
                "insight_evidence_metrics": self.fetch_all(
                    connection,
                    """
                    SELECT evidence.*
                    FROM insight_evidence_metrics evidence
                    INNER JOIN insights insight ON insight.insight_id = evidence.insight_id
                    WHERE insight.creator_id = :creator_id
                    ORDER BY evidence.insight_id, evidence.position
                    """,
                    {"creator_id": resolved_creator_id},
                ),
                "recommended_actions": self.fetch_all(
                    connection,
                    """
                    SELECT action.*
                    FROM recommended_actions action
                    INNER JOIN insights insight ON insight.insight_id = action.insight_id
                    WHERE insight.creator_id = :creator_id
                    ORDER BY action.insight_id, action.position
                    """,
                    {"creator_id": resolved_creator_id},
                ),
                "spark_platform_metric_summaries": self.fetch_all(
                    connection,
                    """
                    SELECT summary.*
                    FROM spark_platform_metric_summaries summary
                    INNER JOIN (
                        SELECT platform, MAX(calculated_at) AS calculated_at
                        FROM spark_platform_metric_summaries
                        WHERE creator_id = :creator_id
                        GROUP BY platform
                    ) latest
                        ON latest.platform = summary.platform
                       AND latest.calculated_at = summary.calculated_at
                    WHERE summary.creator_id = :creator_id
                    ORDER BY summary.calculated_at DESC, summary.platform
                    """,
                    {"creator_id": resolved_creator_id},
                ),
                "spark_video_follower_contributions": self.fetch_all(
                    connection,
                    """
                    SELECT contribution.*
                    FROM spark_video_follower_contributions contribution
                    INNER JOIN (
                        SELECT video_id, MAX(calculated_at) AS calculated_at
                        FROM spark_video_follower_contributions
                        WHERE creator_id = :creator_id
                        GROUP BY video_id
                    ) latest
                        ON latest.video_id = contribution.video_id
                       AND latest.calculated_at = contribution.calculated_at
                    WHERE contribution.creator_id = :creator_id
                    ORDER BY contribution.new_followers DESC, contribution.conversion_rate DESC, contribution.calculated_at DESC
                    LIMIT 10
                    """,
                    {"creator_id": resolved_creator_id},
                ),
            }

        if not rows["creators"]:
            raise KeyError(creator_id)

        return self.to_contract(rows, resolved_creator_id)

    def resolve_creator_id(self, creator_id: str) -> str:
        if creator_id != "demo":
            return creator_id
        creators = self._list_creators()
        if not creators:
            raise KeyError(creator_id)
        return creators[0]["creatorId"]

    @staticmethod
    def fetch_all(connection: Any, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            from sqlalchemy import text
        except ImportError as exc:
            raise ConfigError("SQLAlchemy is not installed. Run: pip install -r requirements.txt") from exc

        result = connection.execute(text(sql), params or {})
        return [dict(row._mapping) for row in result]

    @staticmethod
    def fetch_optional_all(connection: Any, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            return MySQLRepository.fetch_all(connection, sql, params)
        except Exception as exc:
            if "doesn't exist" in str(exc) or "no such table" in str(exc):
                return []
            raise

    def to_contract(self, rows: dict[str, list[dict[str, Any]]], creator_id: str | None = None) -> dict[str, Any]:
        rows = self.filter_rows_by_creator(rows, creator_id)
        rows = self.latest_metric_rows(rows)
        creator = rows["creators"][0]
        generated_at = self.latest_generated_at(rows["insights"], rows["video_metric_snapshots"])

        insights = self.map_insights(rows)
        data = {
            "meta": {
                "schemaVersion": "mvp-1",
                "generatedAt": generated_at,
                "dataSource": "mysql",
            },
            "creator": {
                "creatorId": creator["creator_id"],
                "displayName": creator["display_name"],
                "avatarUrl": creator["avatar_url"] or "",
                "nicheTags": parse_json(creator["niche_tags"]),
                "timezone": creator["timezone"],
            },
            "platformAccounts": [
                {
                    "accountId": item["account_id"],
                    "creatorId": item["creator_id"],
                    "platform": item["platform"],
                    "platformDisplayName": item["platform_display_name"],
                    "bindingStatus": item["binding_status"],
                    "followerCount": item.get("follower_count", 0),
                    "syncLatencySeconds": item["sync_latency_seconds"],
                    "collectionIntervalSeconds": item["collection_interval_seconds"],
                    "dataScopes": parse_json(item["data_scopes"]),
                }
                for item in rows["platform_accounts"]
            ],
            "videos": [
                {
                    "videoId": item["video_id"],
                    "creatorId": item["creator_id"],
                    "platform": item["platform"],
                    "platformLabel": item["platform_label"],
                    "title": item["title"],
                    "contentType": item["content_type"],
                    "contentTypeLabel": item["content_type_label"],
                    "topicTags": parse_json(item["topic_tags"]),
                    "publishTime": iso_datetime(item["publish_time"]),
                    "lifecycleStage": item["lifecycle_stage"],
                }
                for item in rows["videos"]
            ],
            "videoMetricSnapshots": [
                {
                    "snapshotId": item["snapshot_id"],
                    "videoId": item["video_id"],
                    "creatorId": item["creator_id"],
                    "platform": item["platform"],
                    "views": item["views"],
                    "likes": item["likes"],
                    "comments": item["comments"],
                    "shares": item["shares"],
                    "saves": item["saves"],
                    "profileVisits": item["profile_visits"],
                    "newFollowers": item["new_followers"],
                    "completionRate": float(item["completion_rate"]),
                    "averageWatchSeconds": item["average_watch_seconds"],
                    "engagementRate": float(item["engagement_rate"]),
                    "conversionRate": float(item["conversion_rate"]),
                    "commentRate": float(item["comment_rate"]),
                    "saveRate": float(item["save_rate"]),
                    "shareRate": float(item["share_rate"]),
                    "collectedAt": iso_datetime(item["collected_at"]),
                }
                for item in rows["video_metric_snapshots"]
            ],
            "videoTrafficSourceMetrics": [
                {
                    "videoId": item["video_id"],
                    "source": item["source"],
                    "views": item["views"],
                    "newFollowers": item["new_followers"],
                    "conversionRate": float(item["conversion_rate"]),
                    "saveRate": float(item["save_rate"]),
                    "commentRate": float(item["comment_rate"]),
                }
                for item in rows["video_traffic_source_metrics"]
            ],
            "creatorMetricSnapshots": [
                {
                    "snapshotId": item["snapshot_id"],
                    "creatorId": item["creator_id"],
                    "date": iso_datetime(item["metric_date"]),
                    "totalFollowers": item["total_followers"],
                    "newFollowers": item["new_followers"],
                    "lostFollowers": item["lost_followers"],
                    "netFollowers": item["net_followers"],
                    "totalViews": item["total_views"],
                    "totalInteractions": item["total_interactions"],
                    "profileVisits": item["profile_visits"],
                    "followerGrowthRate": float(item["follower_growth_rate"]),
                    "viewToFollowerRate": float(item["view_to_follower_rate"]),
                    "stickinessScore": float(item["stickiness_score"]),
                    "growthHealthScore": float(item["growth_health_score"]),
                }
                for item in rows["creator_metric_snapshots"]
            ],
            "dailyMetrics": self.map_daily_metrics(rows),
            "audienceProfileSnapshot": self.map_audience(rows["audience_profile_snapshots"]),
            "topicTrendSnapshots": [
                {
                    "topicId": item["topic_id"],
                    "topicName": item["topic_name"],
                    "platforms": parse_json(item["platforms"]),
                    "heatScore": item["heat_score"],
                    "growthRate": float(item["growth_rate"]),
                    "audienceFitScore": item["audience_fit_score"],
                    "creatorFitScore": item["creator_fit_score"],
                    "riskLevel": item["risk_level"],
                }
                for item in rows["topic_trend_snapshots"]
            ],
            "insights": insights,
            "sparkOutputs": self.map_spark_outputs(rows),
        }
        data = merge_spark_insights(data)
        data["viewModels"] = make_view_models(data)
        return data

    @staticmethod
    def latest_metric_rows(rows: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        next_rows = {table: list(table_rows) for table, table_rows in rows.items()}
        next_rows["video_metric_snapshots"] = latest_rows_by_key(
            rows.get("video_metric_snapshots", []),
            "video_id",
            ("collected_at", "updated_at", "created_at", "snapshot_id"),
        )
        next_rows["spark_platform_metric_summaries"] = latest_rows_by_key(
            rows.get("spark_platform_metric_summaries", []),
            "platform",
            ("calculated_at", "run_id"),
        )
        next_rows["spark_video_follower_contributions"] = sorted(
            latest_rows_by_key(
                rows.get("spark_video_follower_contributions", []),
                "video_id",
                ("calculated_at", "run_id"),
            ),
            key=lambda item: (item.get("new_followers") or 0, item.get("conversion_rate") or 0, comparable_value(item.get("calculated_at"))),
            reverse=True,
        )[:10]
        return next_rows

    @staticmethod
    def filter_rows_by_creator(rows: dict[str, list[dict[str, Any]]], creator_id: str | None) -> dict[str, list[dict[str, Any]]]:
        if creator_id is None:
            return rows

        filtered = {table: list(table_rows) for table, table_rows in rows.items()}
        filtered["creators"] = [item for item in rows["creators"] if item["creator_id"] == creator_id]
        if not filtered["creators"]:
            raise KeyError(creator_id)

        direct_creator_tables = [
            "platform_accounts",
            "videos",
            "video_metric_snapshots",
            "creator_metric_snapshots",
            "offline_creator_daily_metrics",
            "offline_content_type_daily_metrics",
            "audience_profile_snapshots",
            "insights",
            "spark_platform_metric_summaries",
            "spark_video_follower_contributions",
        ]
        for table in direct_creator_tables:
            filtered[table] = [item for item in rows.get(table, []) if item["creator_id"] == creator_id]

        video_ids = {item["video_id"] for item in filtered["videos"]}
        insight_ids = {item["insight_id"] for item in filtered["insights"]}
        filtered["video_traffic_source_metrics"] = [item for item in rows["video_traffic_source_metrics"] if item["video_id"] in video_ids]
        filtered["insight_evidence_metrics"] = [item for item in rows["insight_evidence_metrics"] if item["insight_id"] in insight_ids]
        filtered["recommended_actions"] = [item for item in rows["recommended_actions"] if item["insight_id"] in insight_ids]
        return filtered

    @staticmethod
    def latest_generated_at(insights: list[dict[str, Any]], snapshots: list[dict[str, Any]]) -> str:
        if insights:
            return iso_datetime(max(item["generated_at"] for item in insights))
        if snapshots:
            return iso_datetime(max(item["collected_at"] for item in snapshots))
        return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    @staticmethod
    def map_audience(rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            raise MySQLRepositoryError("MySQL data is missing audience_profile_snapshots")
        item = rows[0]
        return {
            "snapshotId": item["snapshot_id"],
            "creatorId": item["creator_id"],
            "gender": parse_json(item["gender"]),
            "ageGroups": parse_json(item["age_groups"]),
            "regions": parse_json(item["regions"]),
            "activeHours": parse_json(item["active_hours"]),
            "interestTags": parse_json(item["interest_tags"]),
            "highValueSegments": parse_json(item["high_value_segments"]),
        }

    @staticmethod
    def map_insights(rows: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        evidence_by_insight: dict[str, list[dict[str, Any]]] = {}
        for item in rows["insight_evidence_metrics"]:
            evidence_by_insight.setdefault(item["insight_id"], []).append(
                {
                    "label": item["label"],
                    "value": parse_json(item["value_json"]),
                    "unit": item["unit"],
                    "direction": item["direction"],
                }
            )

        actions_by_insight: dict[str, list[dict[str, Any]]] = {}
        for item in rows["recommended_actions"]:
            actions_by_insight.setdefault(item["insight_id"], []).append(
                {
                    "actionId": item["action_id"],
                    "title": item["title"],
                    "description": item["description"],
                    "expectedImpact": item["expected_impact"],
                    "relatedPage": item["related_page"],
                }
            )

        return [
            {
                "insightId": item["insight_id"],
                "creatorId": item["creator_id"],
                "type": item["type"],
                "scope": item["scope"],
                "targetId": item["target_id"],
                "title": item["title"],
                "summary": item["summary"],
                "priority": item["priority"],
                "evidenceMetrics": evidence_by_insight.get(item["insight_id"], []),
                "recommendedActions": actions_by_insight.get(item["insight_id"], []),
                "generatedBy": item["generated_by"],
                "generatedAt": iso_datetime(item["generated_at"]),
                "pageTargets": parse_json(item["page_targets"]),
            }
            for item in rows["insights"]
        ]

    @staticmethod
    def map_spark_outputs(rows: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        return {
            "platformMetricSummaries": [
                {
                    "runId": item["run_id"],
                    "creatorId": item["creator_id"],
                    "platform": item["platform"],
                    "totalViews": item["total_views"],
                    "newFollowers": item["new_followers"],
                    "videoCount": item["video_count"],
                    "conversionRate": float(item["conversion_rate"]),
                    "calculatedAt": iso_datetime(item["calculated_at"]),
                }
                for item in rows.get("spark_platform_metric_summaries", [])
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
                    "conversionRate": float(item["conversion_rate"]),
                    "calculatedAt": iso_datetime(item["calculated_at"]),
                }
                for item in rows.get("spark_video_follower_contributions", [])
            ],
        }

    @staticmethod
    def map_daily_metrics(rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        creator_rows = rows.get("offline_creator_daily_metrics", [])
        creator = creator_rows[0] if creator_rows else None
        return {
            "creator": (
                {
                    "creatorId": creator["creator_id"],
                    "date": iso_datetime(creator["metric_date"]),
                    "totalViews": creator["total_views_delta"],
                    "totalInteractions": creator["total_interactions_delta"],
                    "profileVisits": creator["profile_visits_delta"],
                    "newFollowers": creator["new_followers_delta"],
                    "lostFollowers": creator["lost_followers_delta"],
                    "netFollowers": creator["net_followers_delta"],
                    "viewToFollowerRate": float(creator["view_to_follower_rate"]),
                    "stickinessScore": float(creator["stickiness_score"]),
                    "growthHealthScore": float(creator["growth_health_score"]),
                }
                if creator
                else None
            ),
            "contentTypes": [
                {
                    "creatorId": item["creator_id"],
                    "contentType": item["content_type"],
                    "date": iso_datetime(item["metric_date"]),
                    "videoCount": item["video_count"],
                    "views": item["views_delta"],
                    "interactions": item["interactions_delta"],
                    "newFollowers": item["new_followers_delta"],
                    "viewToFollowerRate": float(item["view_to_follower_rate"]),
                    "efficiencyScore": float(item["efficiency_score"]),
                }
                for item in rows.get("offline_content_type_daily_metrics", [])
            ],
        }

    @staticmethod
    def map_report(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "reportId": row["report_id"],
            "creatorId": row["creator_id"],
            "reportType": row["report_type"],
            "periodStart": iso_datetime(row["period_start"]),
            "periodEnd": iso_datetime(row["period_end"]),
            "status": row["status"],
            "title": row["title"],
            "summary": row["summary"],
            "highlights": parse_json(row["highlights_json"]),
            "risks": parse_json(row["risks_json"]),
            "actions": parse_json(row["actions_json"]),
            "metrics": parse_json(row["metrics_json"]),
            "generatedAt": iso_datetime(row["generated_at"]),
            "batchRunId": row["batch_run_id"],
        }
