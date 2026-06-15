"""Validate CreatorPulse MVP mock data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parent / "data" / "creatorpulse_mvp_mock.json"


def close_enough(actual: float, expected: float, tolerance: float = 0.000001) -> bool:
    return abs(actual - expected) <= tolerance


def pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_counts(data: dict[str, Any]) -> None:
    require(data["creator"]["creatorId"] == "creator_001", "Expected one demo creator")
    require(len(data["platformAccounts"]) == 3, "Expected 3 platform accounts")
    require({item["platform"] for item in data["platformAccounts"]} == {"DOUYIN", "BILIBILI", "XIAOHONGSHU"}, "Unexpected platform set")
    require(len(data["videos"]) == 27, "Expected 9 videos per platform, 27 total")
    require(len(data["videoMetricSnapshots"]) == len(data["videos"]), "Expected one metric snapshot per video")
    require(len(data["creatorMetricSnapshots"]) == 7, "Expected 7 creator trend snapshots")
    require(len(data["topicTrendSnapshots"]) == 10, "Expected 10 topic trends")
    require(20 <= len(data["insights"]) <= 30, "Expected 20-30 insights")


def validate_snapshot_formulas(data: dict[str, Any]) -> None:
    video_ids = {item["videoId"] for item in data["videos"]}
    seen_snapshot_video_ids = set()

    for row in data["videoMetricSnapshots"]:
        seen_snapshot_video_ids.add(row["videoId"])
        require(row["videoId"] in video_ids, f"Snapshot references unknown video {row['videoId']}")
        require(row["newFollowers"] <= row["profileVisits"] <= row["views"], f"Invalid conversion chain for {row['videoId']}")
        interactions = row["likes"] + row["comments"] + row["shares"] + row["saves"]
        require(interactions <= row["views"] * 2, f"Interactions too high for {row['videoId']}")
        require(close_enough(row["conversionRate"], pct(row["newFollowers"], row["views"])), f"Bad conversionRate for {row['videoId']}")
        require(close_enough(row["commentRate"], pct(row["comments"], row["views"])), f"Bad commentRate for {row['videoId']}")
        require(close_enough(row["saveRate"], pct(row["saves"], row["views"])), f"Bad saveRate for {row['videoId']}")
        require(close_enough(row["shareRate"], pct(row["shares"], row["views"])), f"Bad shareRate for {row['videoId']}")
        require(close_enough(row["engagementRate"], pct(interactions, row["views"])), f"Bad engagementRate for {row['videoId']}")

    require(seen_snapshot_video_ids == video_ids, "Every video must have one latest snapshot")


def validate_traffic_sources(data: dict[str, Any]) -> None:
    by_video: dict[str, list[dict[str, Any]]] = {}
    for row in data["videoTrafficSourceMetrics"]:
        by_video.setdefault(row["videoId"], []).append(row)

    snapshot_by_video = {row["videoId"]: row for row in data["videoMetricSnapshots"]}
    for video_id, snapshot in snapshot_by_video.items():
        rows = by_video.get(video_id, [])
        require(len(rows) == 5, f"Expected 5 traffic source rows for {video_id}")
        require(sum(row["views"] for row in rows) == snapshot["views"], f"Traffic views do not sum to snapshot views for {video_id}")
        require(sum(row["newFollowers"] for row in rows) == snapshot["newFollowers"], f"Traffic followers do not sum to snapshot followers for {video_id}")
        for row in rows:
            require(close_enough(row["conversionRate"], pct(row["newFollowers"], row["views"])), f"Bad traffic conversionRate for {video_id}:{row['source']}")


def validate_creator_trend(data: dict[str, Any]) -> None:
    rows = data["creatorMetricSnapshots"]
    require(rows == sorted(rows, key=lambda item: item["date"]), "Creator trend should be sorted by date")
    for row in rows:
        require(row["netFollowers"] == row["newFollowers"] - row["lostFollowers"], f"Bad netFollowers for {row['date']}")
        previous_total = row["totalFollowers"] - row["netFollowers"]
        require(close_enough(row["followerGrowthRate"], pct(row["netFollowers"], previous_total)), f"Bad followerGrowthRate for {row['date']}")
        require(close_enough(row["viewToFollowerRate"], pct(row["newFollowers"], row["totalViews"])), f"Bad viewToFollowerRate for {row['date']}")


def validate_insights(data: dict[str, Any]) -> None:
    valid_types = {"DIAGNOSIS", "OPPORTUNITY", "RISK", "ACTION", "REPORT"}
    valid_priorities = {"LOW", "MEDIUM", "HIGH"}
    all_page_targets = set()
    for insight in data["insights"]:
        require(insight["type"] in valid_types, f"Invalid insight type {insight['insightId']}")
        require(insight["priority"] in valid_priorities, f"Invalid insight priority {insight['insightId']}")
        require(insight["generatedBy"] == "RULE_ENGINE", f"MVP insights must be rule generated: {insight['insightId']}")
        require(insight["title"], f"Missing insight title {insight['insightId']}")
        require(insight["summary"], f"Missing insight summary {insight['insightId']}")
        require(len(insight["evidenceMetrics"]) >= 2, f"Insight needs at least 2 evidence metrics: {insight['insightId']}")
        require(len(insight["recommendedActions"]) >= 1, f"Insight needs at least 1 action: {insight['insightId']}")
        require(len(insight["pageTargets"]) >= 1, f"Insight needs page targets: {insight['insightId']}")
        all_page_targets.update(insight["pageTargets"])

    required_prefixes = ["growth.", "fans.", "video.", "content.", "opportunities.", "profile."]
    for prefix in required_prefixes:
        require(any(target.startswith(prefix) for target in all_page_targets), f"Missing insights for {prefix}")


def validate_view_models(data: dict[str, Any]) -> None:
    expected = {"growthDashboard", "fansAnalysis", "videoAnalysis", "contentDistribution", "opportunities", "profile"}
    require(set(data["viewModels"]) == expected, "Unexpected view model keys")
    for key in expected:
        require("insights" in data["viewModels"][key] or key == "profile", f"Missing insights in {key}")
    require(data["viewModels"]["growthDashboard"]["topVideos"], "growthDashboard should expose top videos")
    require(data["viewModels"]["fansAnalysis"]["audienceProfile"], "fansAnalysis should expose audience profile")
    require(data["viewModels"]["opportunities"]["topics"], "opportunities should expose topic trends")


def main() -> None:
    require(DATA_PATH.exists(), f"Missing data file: {DATA_PATH}")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    validate_counts(data)
    validate_snapshot_formulas(data)
    validate_traffic_sources(data)
    validate_creator_trend(data)
    validate_insights(data)
    validate_view_models(data)
    print("MVP mock validation passed")


if __name__ == "__main__":
    main()
