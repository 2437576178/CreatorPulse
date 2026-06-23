"""Build page ViewModels from CreatorPulse data-contract objects."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def empty_creator_snapshot(creator_id: str) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date().isoformat()
    return {
        "snapshotId": f"empty_creator_snapshot_{creator_id}",
        "creatorId": creator_id,
        "date": today,
        "totalFollowers": 0,
        "newFollowers": 0,
        "lostFollowers": 0,
        "netFollowers": 0,
        "totalViews": 0,
        "totalInteractions": 0,
        "profileVisits": 0,
        "followerGrowthRate": 0.0,
        "viewToFollowerRate": 0.0,
        "stickinessScore": 0.0,
        "growthHealthScore": 0.0,
        "dataStatus": "WAITING_FOR_EVENTS",
    }


def pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def bounded_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def ratio_score(value: float, target: float, points: float) -> float:
    if target <= 0:
        return 0.0
    return min(points, (value / target) * points)


def growth_health_score(
    *,
    view_to_follower_rate: float,
    profile_conversion_rate: float,
    interaction_rate: float,
    retained_follower_rate: float,
) -> float:
    return bounded_score(
        ratio_score(view_to_follower_rate, 0.0008, 40)
        + ratio_score(profile_conversion_rate, 0.08, 30)
        + ratio_score(interaction_rate, 0.03, 20)
        + ratio_score(retained_follower_rate, 0.9, 10)
    )


def conversion_rate_status(view_to_follower_rate: float) -> str:
    if view_to_follower_rate >= 0.0008:
        return "高于目标"
    if view_to_follower_rate >= 0.0004:
        return "接近目标"
    return "低于目标"


def make_view_models(data: dict[str, Any]) -> dict[str, Any]:
    insights = data["insights"]

    def target(prefix: str) -> list[dict[str, Any]]:
        return [item for item in insights if any(page.startswith(prefix) for page in item["pageTargets"])]

    creator_id = data["creator"]["creatorId"]
    platform_count = len(data.get("platformAccounts", []))
    sync_latencies = [int(item.get("syncLatencySeconds") or 0) for item in data.get("platformAccounts", [])]
    sync_latency_seconds = max(sync_latencies) if sync_latencies else 0
    total_platform_followers = sum(int(item.get("followerCount") or 0) for item in data.get("platformAccounts", []))
    creator_snapshots = data["creatorMetricSnapshots"] or [empty_creator_snapshot(creator_id)]
    creator_snapshots = [
        {**snapshot, "totalFollowers": total_platform_followers}
        for snapshot in creator_snapshots
    ]
    latest_creator = creator_snapshots[-1]
    snapshots = data["videoMetricSnapshots"]
    total_video_views = sum(int(item.get("views") or 0) for item in snapshots)
    video_follower_contribution_total = sum(int(item.get("newFollowers") or 0) for item in snapshots)
    daily_metrics = data.get("dailyMetrics", {})
    latest_daily_creator = daily_metrics.get("creator")
    today_new_followers = int(
        (latest_daily_creator or {}).get("newFollowers")
        if latest_daily_creator
        else latest_creator.get("newFollowers") or 0
    )
    today_lost_followers = int(
        (latest_daily_creator or {}).get("lostFollowers")
        if latest_daily_creator
        else latest_creator.get("lostFollowers") or 0
    )
    today_net_followers = int(
        (latest_daily_creator or {}).get("netFollowers")
        if latest_daily_creator
        else max(0, today_new_followers - today_lost_followers)
    )
    today_new_views = int((latest_daily_creator or {}).get("totalViews") or 0)
    total_interactions = int(latest_creator.get("totalInteractions") or 0)
    profile_visits = int(latest_creator.get("profileVisits") or 0)
    view_to_follower_rate = pct(today_new_followers, total_video_views)
    profile_conversion_rate = pct(today_new_followers, profile_visits)
    interaction_rate = pct(total_interactions, total_video_views)
    retained_follower_rate = pct(today_net_followers, today_new_followers)
    calibrated_stickiness_score = bounded_score(pct(total_interactions, total_video_views) * 180)
    calibrated_growth_health_score = growth_health_score(
        view_to_follower_rate=view_to_follower_rate,
        profile_conversion_rate=profile_conversion_rate,
        interaction_rate=interaction_rate,
        retained_follower_rate=retained_follower_rate,
    )
    latest_creator = {
        **latest_creator,
        "newFollowers": today_new_followers,
        "lostFollowers": today_lost_followers,
        "netFollowers": today_net_followers,
        "viewToFollowerRate": view_to_follower_rate,
        "stickinessScore": calibrated_stickiness_score,
        "growthHealthScore": calibrated_growth_health_score,
    }
    creator_snapshots = [*creator_snapshots[:-1], latest_creator]
    latest_metric_date = str(latest_creator.get("date") or "")[:10]
    new_video_count = sum(
        1
        for item in data["videos"]
        if latest_metric_date and str(item.get("publishTime") or "")[:10] == latest_metric_date
    )
    estimated_new_views = today_new_views or (sum(max(1, int(int(item.get("views") or 0) * 0.0012)) for item in snapshots) if snapshots else 0)
    spark_outputs = data.get(
        "sparkOutputs",
        {
            "platformMetricSummaries": [],
            "videoFollowerContributions": [],
        },
    )
    videos_by_id = {item["videoId"]: item for item in data["videos"]}
    top_videos = sorted(
        [
            {
                **row,
                "title": videos_by_id[row["videoId"]]["title"],
                "contentType": videos_by_id[row["videoId"]]["contentType"],
            }
            for row in snapshots
        ],
        key=lambda item: item["newFollowers"],
        reverse=True,
    )[:5]
    content_type_rows_by_type: dict[str, dict[str, Any]] = {}
    content_type_daily_rows = {
        item["contentType"]: item
        for item in daily_metrics.get("contentTypes", [])
    }
    for row in snapshots:
        content_type = videos_by_id[row["videoId"]]["contentType"]
        content_type_rows_by_type.setdefault(
            content_type,
            {"contentType": content_type, "views": 0, "newFollowers": 0, "saves": 0},
        )
        content_type_rows_by_type[content_type]["views"] += int(row.get("views") or 0)
        content_type_rows_by_type[content_type]["newFollowers"] += int(row.get("newFollowers") or 0)
        content_type_rows_by_type[content_type]["saves"] += int(row.get("saves") or 0)
    if content_type_daily_rows:
        for content_type, row in content_type_rows_by_type.items():
            row["newFollowers"] = int((content_type_daily_rows.get(content_type) or {}).get("newFollowers") or 0)
    elif video_follower_contribution_total and today_new_followers != video_follower_contribution_total:
        assigned_followers = 0
        rows = list(content_type_rows_by_type.values())
        for index, row in enumerate(rows):
            if index == len(rows) - 1:
                row["newFollowers"] = max(0, today_new_followers - assigned_followers)
                continue
            scaled_followers = int(round(int(row["newFollowers"]) * today_new_followers / video_follower_contribution_total))
            row["newFollowers"] = scaled_followers
            assigned_followers += scaled_followers
    content_type_rows = sorted(
        content_type_rows_by_type.values(),
        key=lambda item: item["newFollowers"],
        reverse=True,
    )
    fans_trend = [
        (
            {**snapshot, "newFollowers": today_new_followers, "lostFollowers": today_lost_followers, "netFollowers": today_net_followers}
            if index == len(creator_snapshots) - 1
            else snapshot
        )
        for index, snapshot in enumerate(creator_snapshots)
    ]

    return {
        "growthDashboard": {
            "currentSnapshot": latest_creator,
            "platformCount": platform_count,
            "newPlatformCount": 0,
            "videoCount": len(data["videos"]),
            "newVideoCount": new_video_count,
            "totalViews": total_video_views,
            "newViews": estimated_new_views,
            "totalInteractions": total_interactions,
            "profileVisits": profile_visits,
            "totalFollowers": total_platform_followers,
            "newFollowers": today_new_followers,
            "syncLatencySeconds": sync_latency_seconds,
            "conversionRateStatus": conversion_rate_status(view_to_follower_rate),
            "topVideos": top_videos,
            "contentTypeRows": content_type_rows,
            "insights": target("growth."),
        },
        "fansAnalysis": {
            "trend": fans_trend,
            "newFollowers": today_new_followers,
            "syncLatencySeconds": sync_latency_seconds,
            "topVideos": top_videos,
            "audienceProfile": data["audienceProfileSnapshot"],
            "insights": target("fans."),
        },
        "videoAnalysis": {
            "videos": data["videos"],
            "snapshots": snapshots,
            "topVideos": top_videos,
            "sparkContributions": spark_outputs["videoFollowerContributions"],
            "insights": target("video."),
        },
        "contentDistribution": {
            "sparkPlatformSummaries": spark_outputs["platformMetricSummaries"],
            "syncLatencySeconds": sync_latency_seconds,
            "insights": target("content."),
        },
        "opportunities": {
            "topics": data["topicTrendSnapshots"],
            "syncLatencySeconds": sync_latency_seconds,
            "insights": target("opportunities."),
        },
        "profile": {
            "platformAccounts": data["platformAccounts"],
            "insights": target("profile."),
        },
    }
