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


PLATFORM_ORDER = ["DOUYIN", "BILIBILI", "XIAOHONGSHU"]
PLATFORM_LABELS = {
    "DOUYIN": "抖音",
    "BILIBILI": "B站",
    "XIAOHONGSHU": "小红书",
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


def seed_registered_creator_rows(creator_id: str, display_name: str, platforms: list[str]) -> dict[str, list[dict[str, Any]]]:
    selected_platforms = set(normalize_platforms(platforms))
    data = copy.deepcopy(load_json())

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

    rows = build_table_rows(data)
    validate_rows(rows)
    return rows
