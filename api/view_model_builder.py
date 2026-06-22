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


def make_view_models(data: dict[str, Any]) -> dict[str, Any]:
    insights = data["insights"]

    def target(prefix: str) -> list[dict[str, Any]]:
        return [item for item in insights if any(page.startswith(prefix) for page in item["pageTargets"])]

    creator_id = data["creator"]["creatorId"]
    platform_count = len(data.get("platformAccounts", []))
    total_platform_followers = sum(int(item.get("followerCount") or 0) for item in data.get("platformAccounts", []))
    creator_snapshots = data["creatorMetricSnapshots"] or [empty_creator_snapshot(creator_id)]
    creator_snapshots = [
        {**snapshot, "totalFollowers": total_platform_followers}
        for snapshot in creator_snapshots
    ]
    latest_creator = creator_snapshots[-1]
    snapshots = data["videoMetricSnapshots"]
    total_video_views = sum(int(item.get("views") or 0) for item in snapshots)
    video_new_followers = sum(int(item.get("newFollowers") or 0) for item in snapshots)
    total_interactions = int(latest_creator.get("totalInteractions") or 0)
    profile_visits = int(latest_creator.get("profileVisits") or 0)
    calibrated_stickiness_score = bounded_score(pct(total_interactions, total_video_views) * 180)
    calibrated_growth_health_score = bounded_score(
        pct(video_new_followers, total_video_views) * 900
        + pct(video_new_followers, profile_visits) * 100
        + calibrated_stickiness_score * 0.25
    )
    latest_creator = {
        **latest_creator,
        "newFollowers": video_new_followers,
        "netFollowers": max(0, video_new_followers - int(latest_creator.get("lostFollowers") or 0)),
        "viewToFollowerRate": pct(video_new_followers, total_video_views),
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
    estimated_new_views = sum(max(1, int(int(item.get("views") or 0) * 0.0012)) for item in snapshots) if snapshots else 0
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
    for row in snapshots:
        content_type = videos_by_id[row["videoId"]]["contentType"]
        content_type_rows_by_type.setdefault(
            content_type,
            {"contentType": content_type, "views": 0, "newFollowers": 0, "saves": 0},
        )
        content_type_rows_by_type[content_type]["views"] += int(row.get("views") or 0)
        content_type_rows_by_type[content_type]["newFollowers"] += int(row.get("newFollowers") or 0)
        content_type_rows_by_type[content_type]["saves"] += int(row.get("saves") or 0)
    content_type_rows = sorted(
        content_type_rows_by_type.values(),
        key=lambda item: item["newFollowers"],
        reverse=True,
    )
    fans_trend = [
        (
            {**snapshot, "newFollowers": video_new_followers, "netFollowers": max(0, video_new_followers - int(snapshot.get("lostFollowers") or 0))}
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
            "totalFollowers": total_platform_followers,
            "newFollowers": video_new_followers,
            "topVideos": top_videos,
            "contentTypeRows": content_type_rows,
            "insights": target("growth."),
        },
        "fansAnalysis": {
            "trend": fans_trend,
            "newFollowers": video_new_followers,
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
            "insights": target("content."),
        },
        "opportunities": {
            "topics": data["topicTrendSnapshots"],
            "insights": target("opportunities."),
        },
        "profile": {
            "platformAccounts": data["platformAccounts"],
            "insights": target("profile."),
        },
    }
