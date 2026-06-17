"""Build page ViewModels from CreatorPulse data-contract objects."""

from __future__ import annotations

from typing import Any


def make_view_models(data: dict[str, Any]) -> dict[str, Any]:
    insights = data["insights"]

    def target(prefix: str) -> list[dict[str, Any]]:
        return [item for item in insights if any(page.startswith(prefix) for page in item["pageTargets"])]

    latest_creator = data["creatorMetricSnapshots"][-1]
    snapshots = data["videoMetricSnapshots"]
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

    return {
        "growthDashboard": {
            "currentSnapshot": latest_creator,
            "topVideos": top_videos,
            "insights": target("growth."),
        },
        "fansAnalysis": {
            "trend": data["creatorMetricSnapshots"],
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
