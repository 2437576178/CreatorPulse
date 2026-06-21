"""Registration and initial creator data seeding helpers."""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.import_mock_to_mysql import build_table_rows, load_json, validate_rows
from platform_catalog import enabled_platform_values, platform_labels


PLATFORM_ORDER = enabled_platform_values()
PLATFORM_LABELS = platform_labels()

DERIVED_PLATFORM_SOURCES = {
    "KUAISHOU": "DOUYIN",
    "WEIBO": "XIAOHONGSHU",
}

DERIVED_PLATFORM_FACTORS = {
    "KUAISHOU": {
        "views": 0.82,
        "likes": 0.9,
        "comments": 0.86,
        "shares": 1.06,
        "saves": 0.72,
        "profileVisits": 0.8,
        "newFollowers": 0.76,
    },
    "WEIBO": {
        "views": 0.68,
        "likes": 0.72,
        "comments": 1.18,
        "shares": 1.28,
        "saves": 0.58,
        "profileVisits": 0.62,
        "newFollowers": 0.52,
    },
}


def normalize_platforms(platforms: list[str]) -> list[str]:
    requested = {str(platform).strip().upper() for platform in platforms if str(platform).strip()}
    if not requested:
        raise ValueError("At least one platform is required")

    unknown = requested.difference(PLATFORM_ORDER)
    if unknown:
        raise ValueError(f"Unsupported platform: {', '.join(sorted(unknown))}")

    return [platform for platform in PLATFORM_ORDER if platform in requested]


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "creator"


def remap_id(value: str, creator_id: str) -> str:
    return f"{value}_{slug(creator_id)}"


def platform_id(value: str, source_platform: str, target_platform: str) -> str:
    updated = value.replace(source_platform.lower(), target_platform.lower()).replace(source_platform, target_platform)
    if updated == value:
        return f"{value}_{target_platform.lower()}"
    return updated


def scaled_int(value: Any, factor: float, minimum: int = 0) -> int:
    return max(minimum, int(round(float(value) * factor)))


def recalculate_rates(snapshot: dict[str, Any]) -> None:
    views = max(int(snapshot["views"]), 1)
    interactions = snapshot["likes"] + snapshot["comments"] + snapshot["shares"] + snapshot["saves"]
    snapshot["engagementRate"] = round(interactions / views, 6)
    snapshot["conversionRate"] = round(snapshot["newFollowers"] / views, 6)
    snapshot["commentRate"] = round(snapshot["comments"] / views, 6)
    snapshot["saveRate"] = round(snapshot["saves"] / views, 6)
    snapshot["shareRate"] = round(snapshot["shares"] / views, 6)


def add_derived_platform_data(data: dict[str, Any], target_platform: str) -> None:
    if target_platform not in DERIVED_PLATFORM_SOURCES:
        return
    if any(item["platform"] == target_platform for item in data["platformAccounts"]):
        return

    source_platform = DERIVED_PLATFORM_SOURCES[target_platform]
    label = PLATFORM_LABELS[target_platform]
    source_account = next(item for item in data["platformAccounts"] if item["platform"] == source_platform)
    account = copy.deepcopy(source_account)
    account["accountId"] = platform_id(account["accountId"], source_platform, target_platform)
    account["platform"] = target_platform
    account["platformDisplayName"] = f"{label}模拟账号"
    account["syncLatencySeconds"] = 8 if target_platform == "KUAISHOU" else 12
    account["collectionIntervalSeconds"] = 20 if target_platform == "KUAISHOU" else 45
    data["platformAccounts"].append(account)

    source_videos = [item for item in data["videos"] if item["platform"] == source_platform]
    source_video_ids = {item["videoId"] for item in source_videos}
    video_id_map = {
        video["videoId"]: platform_id(video["videoId"], source_platform, target_platform)
        for video in source_videos
    }

    title_prefix = "快手短视频" if target_platform == "KUAISHOU" else "微博话题"
    for video in source_videos:
        derived = copy.deepcopy(video)
        derived["videoId"] = video_id_map[video["videoId"]]
        derived["platform"] = target_platform
        derived["platformLabel"] = label
        derived["title"] = f"{title_prefix}：{video['title']}"
        derived["topicTags"] = list(dict.fromkeys([label, *derived["topicTags"]]))
        data["videos"].append(derived)

    factors = DERIVED_PLATFORM_FACTORS[target_platform]
    source_snapshots = [item for item in data["videoMetricSnapshots"] if item["videoId"] in source_video_ids]
    for snapshot in source_snapshots:
        derived_snapshot = copy.deepcopy(snapshot)
        derived_snapshot["snapshotId"] = platform_id(derived_snapshot["snapshotId"], source_platform, target_platform)
        derived_snapshot["videoId"] = video_id_map[snapshot["videoId"]]
        derived_snapshot["platform"] = target_platform
        for key, factor in factors.items():
            derived_snapshot[key] = scaled_int(snapshot[key], factor, minimum=1)
        recalculate_rates(derived_snapshot)
        data["videoMetricSnapshots"].append(derived_snapshot)

    source_traffic_rows = [item for item in data["videoTrafficSourceMetrics"] if item["videoId"] in source_video_ids]
    for row in source_traffic_rows:
        derived_traffic = copy.deepcopy(row)
        derived_traffic["videoId"] = video_id_map[row["videoId"]]
        derived_traffic["views"] = scaled_int(row["views"], factors["views"], minimum=1)
        derived_traffic["newFollowers"] = scaled_int(row["newFollowers"], factors["newFollowers"], minimum=0)
        derived_traffic["conversionRate"] = round(derived_traffic["newFollowers"] / max(derived_traffic["views"], 1), 6)
        data["videoTrafficSourceMetrics"].append(derived_traffic)


def seed_registered_creator_rows(creator_id: str, display_name: str, platforms: list[str]) -> dict[str, list[dict[str, Any]]]:
    selected_platforms = set(normalize_platforms(platforms))
    data = copy.deepcopy(load_json())

    for platform in selected_platforms:
        add_derived_platform_data(data, platform)

    data["creator"] = {
        "creatorId": creator_id,
        "displayName": display_name,
        "avatarUrl": "",
        "nicheTags": ["效率工具", "内容创作", "新账号"],
        "timezone": "Asia/Shanghai",
    }

    for item in data["platformAccounts"]:
        item["accountId"] = remap_id(item["accountId"], creator_id)
        item["creatorId"] = creator_id
        item["platformDisplayName"] = f"{display_name} · {PLATFORM_LABELS.get(item['platform'], item['platform'])}"

    for item in data["videos"]:
        item["videoId"] = remap_id(item["videoId"], creator_id)
        item["creatorId"] = creator_id

    for item in data["videoMetricSnapshots"]:
        item["snapshotId"] = remap_id(item["snapshotId"], creator_id)
        item["videoId"] = remap_id(item["videoId"], creator_id)
        item["creatorId"] = creator_id

    for item in data["videoTrafficSourceMetrics"]:
        item["videoId"] = remap_id(item["videoId"], creator_id)

    for item in data["creatorMetricSnapshots"]:
        item["snapshotId"] = remap_id(item["snapshotId"], creator_id)
        item["creatorId"] = creator_id

    audience = data["audienceProfileSnapshot"]
    audience["snapshotId"] = remap_id(audience["snapshotId"], creator_id)
    audience["creatorId"] = creator_id

    for item in data["insights"]:
        item["insightId"] = remap_id(item["insightId"], creator_id)
        item["creatorId"] = creator_id
        if str(item["targetId"]).startswith(("video_", "account_", "snapshot_")):
            item["targetId"] = remap_id(item["targetId"], creator_id)
        for action in item["recommendedActions"]:
            action["actionId"] = remap_id(action["actionId"], creator_id)

    data["platformAccounts"] = [item for item in data["platformAccounts"] if item["platform"] in selected_platforms]
    data["videos"] = [item for item in data["videos"] if item["platform"] in selected_platforms]
    allowed_video_ids = {item["videoId"] for item in data["videos"]}
    data["videoMetricSnapshots"] = [item for item in data["videoMetricSnapshots"] if item["videoId"] in allowed_video_ids]
    data["videoTrafficSourceMetrics"] = [item for item in data["videoTrafficSourceMetrics"] if item["videoId"] in allowed_video_ids]

    data["videoMetricSnapshots"] = []
    data["videoTrafficSourceMetrics"] = []
    data["creatorMetricSnapshots"] = []
    data["insights"] = []

    rows = build_table_rows(data)
    validate_rows(rows)
    return rows
