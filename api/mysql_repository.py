"""MySQL-backed repository for CreatorPulse MVP data."""

from __future__ import annotations

import json
from datetime import date, datetime
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
                    "SELECT * FROM video_metric_snapshots WHERE creator_id = :creator_id ORDER BY collected_at DESC, snapshot_id",
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
                    SELECT * FROM spark_platform_metric_summaries
                    WHERE creator_id = :creator_id
                    ORDER BY calculated_at DESC, platform
                    """,
                    {"creator_id": resolved_creator_id},
                ),
                "spark_video_follower_contributions": self.fetch_all(
                    connection,
                    """
                    SELECT * FROM spark_video_follower_contributions
                    WHERE creator_id = :creator_id
                    ORDER BY calculated_at DESC, rank_position
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

    def to_contract(self, rows: dict[str, list[dict[str, Any]]], creator_id: str | None = None) -> dict[str, Any]:
        rows = self.filter_rows_by_creator(rows, creator_id)
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
            "audience_profile_snapshots",
            "insights",
            "spark_platform_metric_summaries",
            "spark_video_follower_contributions",
        ]
        for table in direct_creator_tables:
            filtered[table] = [item for item in rows[table] if item["creator_id"] == creator_id]

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
        return datetime.utcnow().isoformat()

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
