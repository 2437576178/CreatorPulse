"""Seed an additional demo creator account and full page data set."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

from werkzeug.security import generate_password_hash

from import_mock_to_mysql import DEFAULT_ENV_PATH, MySQLConfig, build_table_rows, load_env_file, load_json, validate_rows, write_mysql


ROOT_DIR = Path(__file__).resolve().parents[1]

TECH_CREATOR = {
    "creator_id": "creator_003",
    "display_name": "数码效率研究所",
    "avatar_url": "",
    "niche_tags": ["数码测评", "效率工具", "AI办公"],
    "timezone": "Asia/Shanghai",
}

TECH_USER = {
    "user_id": "user_demo_tech",
    "creator_id": "creator_003",
    "email": "tech@creatorpulse.local",
    "password": "demo123456",
    "display_name": "数码效率研究所",
    "role": "CREATOR",
}

TEXT_REPLACEMENTS = {
    "通勤美妆研究所": "数码效率研究所",
    "通勤妆研究所": "效率工具研究所",
    "通勤妆实验室": "AI办公实验室",
    "通勤妆": "效率工具",
    "通勤": "办公",
    "美妆": "数码",
    "妆": "工具",
    "粉底": "平板",
    "口红": "键盘",
    "防晒": "降噪耳机",
    "底妆": "桌搭",
    "新手教程": "AI办公教程",
    "平价测评": "高性价比测评",
    "直播切片": "直播答疑",
    "职场穿搭": "职场效率",
}


def remap_text(value: str) -> str:
    next_value = value
    for source, target in TEXT_REPLACEMENTS.items():
        next_value = next_value.replace(source, target)
    return next_value


def remap_value(value: Any, id_map: dict[str, str]) -> Any:
    if isinstance(value, str):
        if value in id_map:
            return id_map[value]
        return remap_text(value)
    if isinstance(value, list):
        return [remap_value(item, id_map) for item in value]
    if isinstance(value, dict):
        return {key: remap_value(item, id_map) for key, item in value.items()}
    return value


def scale_number(value: Any, factor: float) -> Any:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    next_value = value * factor
    if isinstance(value, int):
        return max(1, int(round(next_value)))
    return round(next_value, 6)


def clone_creator_dataset(source: dict[str, Any], creator: dict[str, Any] = TECH_CREATOR) -> dict[str, Any]:
    data = copy.deepcopy(source)
    id_map: dict[str, str] = {}

    def mapped_id(value: str) -> str:
        if value not in id_map:
            id_map[value] = f"{value}_c3"
        return id_map[value]

    data["creator"] = {
        "creatorId": creator["creator_id"],
        "displayName": creator["display_name"],
        "avatarUrl": creator["avatar_url"],
        "nicheTags": creator["niche_tags"],
        "timezone": creator["timezone"],
    }

    for item in data["platformAccounts"]:
        item["accountId"] = mapped_id(item["accountId"])
        item["creatorId"] = creator["creator_id"]
        item["platformDisplayName"] = remap_text(item["platformDisplayName"])

    for item in data["videos"]:
        item["videoId"] = mapped_id(item["videoId"])
        item["creatorId"] = creator["creator_id"]
        item["title"] = remap_text(item["title"])
        item["topicTags"] = remap_value(item["topicTags"], id_map)

    for index, item in enumerate(data["videoMetricSnapshots"], start=1):
        item["snapshotId"] = mapped_id(item["snapshotId"])
        item["videoId"] = mapped_id(item["videoId"])
        item["creatorId"] = creator["creator_id"]
        factor = 0.88 + (index % 6) * 0.07
        for key in ["views", "likes", "comments", "shares", "saves", "profileVisits", "newFollowers"]:
            item[key] = scale_number(item[key], factor)
        item["conversionRate"] = round(item["newFollowers"] / item["views"], 6)

    for item in data["videoTrafficSourceMetrics"]:
        item["videoId"] = mapped_id(item["videoId"])
        factor = 0.94 if item["source"] in {"SEARCH", "FOLLOW"} else 1.08
        item["views"] = scale_number(item["views"], factor)
        item["newFollowers"] = scale_number(item["newFollowers"], factor)
        item["conversionRate"] = round(item["newFollowers"] / item["views"], 6)

    for index, item in enumerate(data["creatorMetricSnapshots"], start=1):
        item["snapshotId"] = mapped_id(item["snapshotId"])
        item["creatorId"] = creator["creator_id"]
        factor = 0.92 + index * 0.025
        for key in ["totalFollowers", "newFollowers", "lostFollowers", "netFollowers", "totalViews", "totalInteractions", "profileVisits"]:
            item[key] = scale_number(item[key], factor)

    audience = data["audienceProfileSnapshot"]
    audience["snapshotId"] = mapped_id(audience["snapshotId"])
    audience["creatorId"] = creator["creator_id"]
    audience["interestTags"] = {"AI办公": 0.32, "数码测评": 0.25, "桌搭效率": 0.2, "平板笔记": 0.14, "职场效率": 0.09}
    audience["highValueSegments"] = [
        {"name": "效率工具新粉", "share": 0.34, "signal": "收藏回看高"},
        {"name": "AI办公深度粉", "share": 0.28, "signal": "评论提问密集"},
        {"name": "数码测评决策粉", "share": 0.22, "signal": "分享和主页访问高"},
    ]

    for item in data["insights"]:
        item["insightId"] = mapped_id(item["insightId"])
        item["creatorId"] = creator["creator_id"]
        item["targetId"] = mapped_id(item["targetId"]) if item["targetId"] in id_map or item["targetId"].startswith(("video_", "account_")) else remap_text(item["targetId"])
        item["title"] = remap_text(item["title"])
        item["summary"] = remap_text(item["summary"])
        item["evidenceMetrics"] = remap_value(item["evidenceMetrics"], id_map)
        for action in item["recommendedActions"]:
            action["actionId"] = mapped_id(action["actionId"])
            action["title"] = remap_text(action["title"])
            action["description"] = remap_text(action["description"])
            if action.get("expectedImpact"):
                action["expectedImpact"] = remap_text(action["expectedImpact"])

    data.pop("viewModels", None)
    return data


def insert_user(config: MySQLConfig, user: dict[str, str] = TECH_USER) -> None:
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("PyMySQL is not installed. Run: pip install -r requirements.txt") from exc

    connection = pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.database,
        charset="utf8mb4",
        autocommit=False,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users
                  (user_id, creator_id, email, password_hash, display_name, role, is_active)
                VALUES
                  (%s, %s, %s, %s, %s, %s, 1)
                ON DUPLICATE KEY UPDATE
                  creator_id = VALUES(creator_id),
                  password_hash = VALUES(password_hash),
                  display_name = VALUES(display_name),
                  role = VALUES(role),
                  is_active = VALUES(is_active)
                """,
                (
                    user["user_id"],
                    user["creator_id"],
                    user["email"],
                    generate_password_hash(user["password"]),
                    user["display_name"],
                    user["role"],
                ),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def build_rows() -> dict[str, list[dict[str, Any]]]:
    data = clone_creator_dataset(load_json())
    rows = build_table_rows(data)
    validate_rows(rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a third CreatorPulse demo creator and login account")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--execute", action="store_true", help="Actually write creator data and user to MySQL")
    args = parser.parse_args()

    rows = build_rows()
    counts = {table: len(table_rows) for table, table_rows in rows.items()}
    if not args.execute:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "mode": "dry-run",
                    "creator": TECH_CREATOR["creator_id"],
                    "login": {"email": TECH_USER["email"], "password": TECH_USER["password"]},
                    "counts": counts,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    load_env_file(args.env_file)
    config = MySQLConfig.from_env()
    write_mysql(rows, config)
    insert_user(config)

    print(
        json.dumps(
            {
                "status": "ok",
                "mode": "mysql-seed-additional-creator",
                "creator": TECH_CREATOR["creator_id"],
                "login": {"email": TECH_USER["email"], "password": TECH_USER["password"]},
                "counts": counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    main()
