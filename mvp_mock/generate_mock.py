"""Generate CreatorPulse MVP mock data.

The output follows 04A_MVP数据Mock与Insight实现SPEC.md:
- 1 creator
- 3 platforms
- 8-10 videos per platform
- 1 latest snapshot per video
- 7 days creator trend
- 1 audience profile
- 10 topic trends
- 20-30 rule-based insights
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


RANDOM_SEED = 20260614
CREATOR_ID = "creator_001"
OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "creatorpulse_mvp_mock.json"

PLATFORMS = [
    {"value": "DOUYIN", "label": "抖音", "handle": "通勤妆研究所"},
    {"value": "BILIBILI", "label": "B站", "handle": "通勤美妆研究所"},
    {"value": "XIAOHONGSHU", "label": "小红书", "handle": "通勤妆实验室"},
]

CONTENT_TYPES = [
    ("TUTORIAL", "教程"),
    ("REVIEW", "测评"),
    ("SEEDING", "种草"),
    ("VLOG", "Vlog"),
    ("LIVE_CLIP", "直播切片"),
]

TRAFFIC_SOURCES = ["RECOMMENDATION", "SEARCH", "FOLLOWING", "SHARE", "PROFILE"]

VIDEO_TITLES = {
    "TUTORIAL": [
        "5分钟通勤妆教程",
        "新手底妆三步走",
        "早八不迟到的快速眼妆",
        "通勤妆补妆完整流程",
        "新手必看持妆教程",
    ],
    "REVIEW": [
        "夏季防晒测评",
        "平价粉底横评",
        "通勤持妆喷雾对比",
        "油皮底妆实测",
        "新手眼影盘测评",
    ],
    "SEEDING": [
        "近期爱用通勤好物",
        "平价彩妆种草清单",
        "适合上班的口红合集",
        "夏季底妆新品试色",
        "出门包里常备好物",
    ],
    "VLOG": [
        "一周通勤化妆记录",
        "普通打工人的早晨",
        "下班后补妆和复盘",
        "周末整理化妆台",
    ],
    "LIVE_CLIP": [
        "直播切片：粉底色号答疑",
        "直播切片：新手刷具怎么选",
        "直播切片：通勤妆答疑",
    ],
}


def pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def now_iso() -> str:
    return datetime(2026, 6, 14, 20, 0, tzinfo=timezone(timedelta(hours=8))).isoformat()


def iso_days_ago(days: int, hour: int) -> str:
    base = datetime(2026, 6, 14, hour, 0, tzinfo=timezone(timedelta(hours=8)))
    return (base - timedelta(days=days)).isoformat()


def weighted_choice(items: list[tuple[str, float]]) -> str:
    total = sum(weight for _, weight in items)
    pick = random.uniform(0, total)
    current = 0.0
    for item, weight in items:
        current += weight
        if pick <= current:
            return item
    return items[-1][0]


def make_creator() -> dict[str, Any]:
    return {
        "creatorId": CREATOR_ID,
        "displayName": "通勤美妆研究所",
        "avatarUrl": "",
        "nicheTags": ["通勤妆", "平价测评", "新手教程"],
        "timezone": "Asia/Shanghai",
    }


def make_platform_accounts() -> list[dict[str, Any]]:
    accounts = []
    for index, platform in enumerate(PLATFORMS, start=1):
        accounts.append(
            {
                "accountId": f"account_{index:03d}",
                "creatorId": CREATOR_ID,
                "platform": platform["value"],
                "platformDisplayName": platform["handle"],
                "bindingStatus": "BOUND",
                "syncLatencySeconds": 5 if platform["value"] != "XIAOHONGSHU" else 10,
                "collectionIntervalSeconds": 5 if platform["value"] == "BILIBILI" else 30,
                "dataScopes": ["VIDEO", "FOLLOWER", "COMMENT", "TOPIC"],
            }
        )
    return accounts


def make_videos() -> list[dict[str, Any]]:
    videos: list[dict[str, Any]] = []
    content_weights = [
        ("TUTORIAL", 0.32),
        ("REVIEW", 0.27),
        ("SEEDING", 0.24),
        ("VLOG", 0.1),
        ("LIVE_CLIP", 0.07),
    ]
    lifecycle_weights = [
        ("BURST", 0.18),
        ("STABLE", 0.38),
        ("LONG_TAIL", 0.28),
        ("SECONDARY_BOOST", 0.08),
        ("DECLINING", 0.08),
    ]

    for platform in PLATFORMS:
        for item_index in range(1, 10):
            content_type = weighted_choice(content_weights)
            title_pool = VIDEO_TITLES[content_type]
            title = title_pool[(item_index - 1) % len(title_pool)]
            video_id = f"video_{platform['value'].lower()}_{item_index:02d}"
            videos.append(
                {
                    "videoId": video_id,
                    "creatorId": CREATOR_ID,
                    "platform": platform["value"],
                    "platformLabel": platform["label"],
                    "title": title,
                    "contentType": content_type,
                    "contentTypeLabel": dict(CONTENT_TYPES)[content_type],
                    "topicTags": build_topic_tags(content_type, title),
                    "publishTime": iso_days_ago(random.randint(0, 21), random.choice([12, 18, 20, 21])),
                    "lifecycleStage": weighted_choice(lifecycle_weights),
                }
            )
    return videos


def build_topic_tags(content_type: str, title: str) -> list[str]:
    tags_by_type = {
        "TUTORIAL": ["教程", "新手", "通勤妆"],
        "REVIEW": ["测评", "平价", "持妆"],
        "SEEDING": ["种草", "清单", "好物"],
        "VLOG": ["日常", "通勤", "复盘"],
        "LIVE_CLIP": ["直播", "答疑", "切片"],
    }
    tags = tags_by_type[content_type][:]
    if "防晒" in title:
        tags.append("防晒")
    if "粉底" in title:
        tags.append("粉底")
    return tags


def make_video_snapshots(videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for index, video in enumerate(videos, start=1):
        platform = video["platform"]
        content_type = video["contentType"]

        view_base = {
            "DOUYIN": 860_000,
            "BILIBILI": 520_000,
            "XIAOHONGSHU": 430_000,
        }[platform]
        content_view_factor = {
            "TUTORIAL": 0.95,
            "REVIEW": 1.0,
            "SEEDING": 1.18,
            "VLOG": 0.55,
            "LIVE_CLIP": 0.42,
        }[content_type]
        views = int(random.uniform(0.55, 1.45) * view_base * content_view_factor)

        conversion_base = {
            "TUTORIAL": 0.0108,
            "REVIEW": 0.0069,
            "SEEDING": 0.0022,
            "VLOG": 0.0031,
            "LIVE_CLIP": 0.0042,
        }[content_type]
        platform_conversion_factor = {
            "DOUYIN": 0.58,
            "BILIBILI": 1.45,
            "XIAOHONGSHU": 1.12,
        }[platform]
        conversion = conversion_base * platform_conversion_factor * random.uniform(0.78, 1.22)

        new_followers = max(80, int(views * conversion))
        profile_visits = max(new_followers, int(new_followers * random.uniform(4.8, 7.6)))
        profile_visits = min(profile_visits, int(views * 0.18))

        like_rate = random.uniform(0.055, 0.13)
        comment_rate = {
            "TUTORIAL": random.uniform(0.012, 0.026),
            "REVIEW": random.uniform(0.016, 0.032),
            "SEEDING": random.uniform(0.006, 0.014),
            "VLOG": random.uniform(0.007, 0.015),
            "LIVE_CLIP": random.uniform(0.01, 0.02),
        }[content_type]
        save_rate = {
            "TUTORIAL": random.uniform(0.095, 0.16),
            "REVIEW": random.uniform(0.065, 0.12),
            "SEEDING": random.uniform(0.025, 0.065),
            "VLOG": random.uniform(0.015, 0.035),
            "LIVE_CLIP": random.uniform(0.02, 0.05),
        }[content_type]
        share_rate = random.uniform(0.018, 0.065)

        likes = int(views * like_rate)
        comments = int(views * comment_rate)
        shares = int(views * share_rate)
        saves = int(views * save_rate)
        completion_rate = round(random.uniform(0.42, 0.76), 4)
        average_watch_seconds = int(random.uniform(38, 235))

        snapshots.append(
            {
                "snapshotId": f"snapshot_{index:04d}",
                "videoId": video["videoId"],
                "creatorId": CREATOR_ID,
                "platform": platform,
                "views": views,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "saves": saves,
                "profileVisits": profile_visits,
                "newFollowers": new_followers,
                "completionRate": completion_rate,
                "averageWatchSeconds": average_watch_seconds,
                "engagementRate": pct(likes + comments + shares + saves, views),
                "conversionRate": pct(new_followers, views),
                "commentRate": pct(comments, views),
                "saveRate": pct(saves, views),
                "shareRate": pct(shares, views),
                "collectedAt": now_iso(),
            }
        )
    return snapshots


def make_traffic_sources(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_weights = {
        "RECOMMENDATION": 0.52,
        "SEARCH": 0.18,
        "FOLLOWING": 0.14,
        "SHARE": 0.09,
        "PROFILE": 0.07,
    }
    follower_quality = {
        "RECOMMENDATION": 0.54,
        "SEARCH": 1.58,
        "FOLLOWING": 1.08,
        "SHARE": 1.18,
        "PROFILE": 1.26,
    }

    for snapshot in snapshots:
        views_remaining = snapshot["views"]
        raw_views: dict[str, int] = {}
        for source in TRAFFIC_SOURCES[:-1]:
            value = int(snapshot["views"] * source_weights[source] * random.uniform(0.82, 1.18))
            raw_views[source] = min(value, views_remaining)
            views_remaining -= raw_views[source]
        raw_views[TRAFFIC_SOURCES[-1]] = max(0, views_remaining)

        quality_total = sum(raw_views[source] * follower_quality[source] for source in TRAFFIC_SOURCES)
        follower_allocations = {
            source: int(snapshot["newFollowers"] * (raw_views[source] * follower_quality[source]) / quality_total)
            for source in TRAFFIC_SOURCES
        }
        follower_gap = snapshot["newFollowers"] - sum(follower_allocations.values())
        largest_source = max(TRAFFIC_SOURCES, key=lambda source: raw_views[source])
        follower_allocations[largest_source] += follower_gap

        for source in TRAFFIC_SOURCES:
            source_views = raw_views[source]
            followers = follower_allocations[source]
            rows.append(
                {
                    "videoId": snapshot["videoId"],
                    "source": source,
                    "views": source_views,
                    "newFollowers": followers,
                    "conversionRate": pct(followers, source_views),
                    "saveRate": round(snapshot["saveRate"] * random.uniform(0.75, 1.3), 6),
                    "commentRate": round(snapshot["commentRate"] * random.uniform(0.75, 1.3), 6),
                }
            )
    return rows


def make_creator_trend(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total_views_today = sum(row["views"] for row in snapshots)
    total_new_followers_today = sum(row["newFollowers"] for row in snapshots)
    total_interactions_today = sum(row["likes"] + row["comments"] + row["shares"] + row["saves"] for row in snapshots)
    total_profile_visits_today = sum(row["profileVisits"] for row in snapshots)

    rows: list[dict[str, Any]] = []
    base_total_followers = 2_780_000
    running_followers = base_total_followers - int(total_new_followers_today * 3.2)
    for days_ago in range(6, -1, -1):
        factor = 0.72 + (6 - days_ago) * 0.055 + random.uniform(-0.05, 0.06)
        new_followers = int(total_new_followers_today / 7 * factor)
        lost_followers = int(new_followers * random.uniform(0.035, 0.075))
        net_followers = new_followers - lost_followers
        running_followers += net_followers
        total_views = int(total_views_today / 7 * random.uniform(0.78, 1.24))
        total_interactions = int(total_interactions_today / 7 * random.uniform(0.82, 1.18))
        profile_visits = int(total_profile_visits_today / 7 * random.uniform(0.78, 1.18))
        engagement_rate = pct(total_interactions, total_views)
        profile_conversion_rate = pct(new_followers, profile_visits)
        stickiness_score = round(min(100, engagement_rate * 180), 1)
        growth_health_score = round(
            min(100, pct(new_followers, total_views) * 900 + profile_conversion_rate * 100 + stickiness_score * 0.25),
            1,
        )
        rows.append(
            {
                "snapshotId": f"creator_snapshot_{days_ago}",
                "creatorId": CREATOR_ID,
                "date": (datetime(2026, 6, 14) - timedelta(days=days_ago)).date().isoformat(),
                "totalFollowers": running_followers,
                "newFollowers": new_followers,
                "lostFollowers": lost_followers,
                "netFollowers": net_followers,
                "totalViews": total_views,
                "totalInteractions": total_interactions,
                "profileVisits": profile_visits,
                "followerGrowthRate": pct(net_followers, running_followers - net_followers),
                "viewToFollowerRate": pct(new_followers, total_views),
                "stickinessScore": stickiness_score,
                "growthHealthScore": growth_health_score,
            }
        )
    return rows


def make_audience_profile() -> dict[str, Any]:
    return {
        "snapshotId": "audience_profile_001",
        "creatorId": CREATOR_ID,
        "gender": {"female": 0.82, "male": 0.15, "unknown": 0.03},
        "ageGroups": {"18-24": 0.46, "25-30": 0.31, "31-35": 0.15, "36+": 0.08},
        "regions": {"广东": 0.18, "浙江": 0.15, "上海": 0.13, "北京": 0.1, "四川": 0.08, "其他": 0.36},
        "activeHours": {"12": 0.09, "18": 0.16, "20": 0.28, "21": 0.24, "22": 0.14, "other": 0.09},
        "interestTags": {"通勤妆": 0.35, "防晒测评": 0.22, "平价粉底": 0.18, "新手教程": 0.16, "职场穿搭": 0.09},
        "highValueSegments": [
            {
                "segmentId": "seg_18_24_female",
                "label": "18-24 女性新手用户",
                "share": 0.46,
                "growthRate": 0.18,
                "preferredContentTypes": ["TUTORIAL"],
                "preferredActiveHours": ["20", "21"],
                "primaryActions": ["SAVE", "COMMENT"],
            },
            {
                "segmentId": "seg_25_30_workplace",
                "label": "25-30 职场女性",
                "share": 0.31,
                "growthRate": 0.24,
                "preferredContentTypes": ["REVIEW", "TUTORIAL"],
                "preferredActiveHours": ["20"],
                "primaryActions": ["COMMENT", "SHARE"],
            },
        ],
    }


def make_topics() -> list[dict[str, Any]]:
    names = [
        "5分钟通勤妆",
        "夏季防晒测评",
        "早八快速出门",
        "平价粉底横评",
        "油皮持妆挑战",
        "新手眼妆公式",
        "职场淡妆模板",
        "618彩妆复盘",
        "底妆不脱妆",
        "通勤包好物",
    ]
    topics = []
    for index, name in enumerate(names, start=1):
        topics.append(
            {
                "topicId": f"topic_{index:03d}",
                "topicName": name,
                "platforms": ["BILIBILI", "XIAOHONGSHU"] if index % 2 else ["DOUYIN", "XIAOHONGSHU"],
                "heatScore": random.randint(68, 96),
                "growthRate": round(random.uniform(0.08, 0.42), 4),
                "audienceFitScore": random.randint(72, 96),
                "creatorFitScore": random.randint(70, 94),
                "riskLevel": "LOW" if index not in (8, 10) else "MEDIUM",
            }
        )
    return topics


def calculate_baselines(videos: list[dict[str, Any]], snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    video_by_id = {video["videoId"]: video for video in videos}
    total_views = sum(row["views"] for row in snapshots)
    total_followers = sum(row["newFollowers"] for row in snapshots)
    total_saves = sum(row["saves"] for row in snapshots)
    total_comments = sum(row["comments"] for row in snapshots)
    by_platform: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in snapshots:
        video = video_by_id[row["videoId"]]
        by_platform[row["platform"]].append(row)
        by_type[video["contentType"]].append(row)

    return {
        "averageConversionRate": pct(total_followers, total_views),
        "averageSaveRate": pct(total_saves, total_views),
        "averageCommentRate": pct(total_comments, total_views),
        "averageViews": int(total_views / len(snapshots)),
        "platformAverageViews": {platform: int(sum(row["views"] for row in rows) / len(rows)) for platform, rows in by_platform.items()},
        "contentTypes": {
            content_type: {
                "views": sum(row["views"] for row in rows),
                "newFollowers": sum(row["newFollowers"] for row in rows),
                "comments": sum(row["comments"] for row in rows),
                "saves": sum(row["saves"] for row in rows),
                "conversionRate": pct(sum(row["newFollowers"] for row in rows), sum(row["views"] for row in rows)),
                "saveRate": pct(sum(row["saves"] for row in rows), sum(row["views"] for row in rows)),
                "commentRate": pct(sum(row["comments"] for row in rows), sum(row["views"] for row in rows)),
                "newFollowersShare": pct(sum(row["newFollowers"] for row in rows), total_followers),
            }
            for content_type, rows in by_type.items()
        },
        "platforms": {
            platform: {
                "views": sum(row["views"] for row in rows),
                "newFollowers": sum(row["newFollowers"] for row in rows),
                "publishShare": pct(len(rows), len(snapshots)),
                "newFollowersShare": pct(sum(row["newFollowers"] for row in rows), total_followers),
                "conversionRate": pct(sum(row["newFollowers"] for row in rows), sum(row["views"] for row in rows)),
            }
            for platform, rows in by_platform.items()
        },
    }


def make_insight(
    index: int,
    insight_type: str,
    scope: str,
    target_id: str,
    title: str,
    summary: str,
    priority: str,
    evidence: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    page_targets: list[str],
) -> dict[str, Any]:
    return {
        "insightId": f"insight_{index:03d}",
        "creatorId": CREATOR_ID,
        "type": insight_type,
        "scope": scope,
        "targetId": target_id,
        "title": title,
        "summary": summary,
        "priority": priority,
        "evidenceMetrics": evidence,
        "recommendedActions": [
            {
                "actionId": f"action_{index:03d}_{item_index:02d}",
                **action,
            }
            for item_index, action in enumerate(actions, start=1)
        ],
        "generatedBy": "RULE_ENGINE",
        "generatedAt": now_iso(),
        "pageTargets": page_targets,
    }


def make_insights(
    videos: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    topics: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    video_by_id = {video["videoId"]: video for video in videos}
    baselines = calculate_baselines(videos, snapshots)
    insights: list[dict[str, Any]] = []
    index = 1

    high_conversion = sorted(snapshots, key=lambda row: (row["conversionRate"], row["newFollowers"]), reverse=True)[:5]
    for row in high_conversion:
        video = video_by_id[row["videoId"]]
        if row["conversionRate"] < baselines["averageConversionRate"] * 1.3 or row["newFollowers"] < 1000:
            continue
        title = f"{video['title']} 值得复刻"
        summary = (
            f"{video['platformLabel']}的{video['contentTypeLabel']}内容转粉率达到"
            f"{row['conversionRate'] * 100:.2f}%，新增粉丝 {row['newFollowers']} 人。"
        )
        insights.append(
            make_insight(
                index,
                "OPPORTUNITY",
                "VIDEO",
                video["videoId"],
                title,
                summary,
                "HIGH",
                [
                    {"label": "播放量", "value": row["views"], "unit": "次"},
                    {"label": "新增粉丝", "value": row["newFollowers"], "unit": "人"},
                    {"label": "转粉率", "value": round(row["conversionRate"] * 100, 2), "unit": "%", "direction": "UP"},
                ],
                [
                    {
                        "title": "复刻高转粉结构",
                        "description": f"复刻《{video['title']}》的选题、人群表达、开头结构和关注 CTA。",
                        "expectedImpact": "提升同类型内容转粉效率",
                        "relatedPage": "video.contribution",
                    }
                ],
                ["growth.conversion", "fans.source", "video.contribution"],
            )
        )
        index += 1

    for row in sorted(snapshots, key=lambda item: item["views"], reverse=True)[:6]:
        video = video_by_id[row["videoId"]]
        platform_avg = baselines["platformAverageViews"][row["platform"]]
        if row["views"] < platform_avg * 1.15 or row["conversionRate"] > baselines["averageConversionRate"] * 0.75:
            continue
        insights.append(
            make_insight(
                index,
                "RISK",
                "VIDEO",
                video["videoId"],
                f"{video['title']} 播放高但转粉偏低",
                f"这条视频播放达到 {row['views']} 次，但转粉率只有 {row['conversionRate'] * 100:.2f}%。",
                "HIGH",
                [
                    {"label": "播放量", "value": row["views"], "unit": "次", "direction": "UP"},
                    {"label": "转粉率", "value": round(row["conversionRate"] * 100, 2), "unit": "%", "direction": "DOWN"},
                ],
                [
                    {
                        "title": "提前给出关注理由",
                        "description": "前 8 秒明确适合谁关注，减少泛流量空转。",
                        "expectedImpact": "改善播放到关注的转化",
                        "relatedPage": "growth.conversion",
                    }
                ],
                ["growth.conversion", "video.contribution", "content.source"],
            )
        )
        index += 1

    type_metrics = baselines["contentTypes"]
    if "TUTORIAL" in type_metrics:
        tutorial = type_metrics["TUTORIAL"]
        if tutorial["newFollowersShare"] >= 0.35 and tutorial["saveRate"] >= baselines["averageSaveRate"]:
            insights.append(
                make_insight(
                    index,
                    "OPPORTUNITY",
                    "CONTENT_TYPE",
                    "TUTORIAL",
                    "教程类内容值得加码",
                    f"教程类贡献 {tutorial['newFollowersShare'] * 100:.1f}% 新粉，收藏率达到 {tutorial['saveRate'] * 100:.1f}%。",
                    "HIGH",
                    [
                        {"label": "涨粉贡献", "value": round(tutorial["newFollowersShare"] * 100, 1), "unit": "%"},
                        {"label": "收藏率", "value": round(tutorial["saveRate"] * 100, 1), "unit": "%"},
                    ],
                    [
                        {
                            "title": "提高教程发布占比",
                            "description": "下周把教程作为主线内容，优先做通勤妆系列。",
                            "expectedImpact": "提升新粉和收藏回看",
                            "relatedPage": "content.type",
                        }
                    ],
                    ["growth.distribution", "content.type", "opportunities.advice"],
                )
            )
            index += 1

    if "REVIEW" in type_metrics:
        review = type_metrics["REVIEW"]
        if review["commentRate"] >= baselines["averageCommentRate"] * 1.2:
            insights.append(
                make_insight(
                    index,
                    "OPPORTUNITY",
                    "CONTENT_TYPE",
                    "REVIEW",
                    "测评内容适合承接评论选题",
                    f"测评类评论率达到 {review['commentRate'] * 100:.2f}%，高于账号平均水平。",
                    "MEDIUM",
                    [
                        {"label": "评论率", "value": round(review["commentRate"] * 100, 2), "unit": "%"},
                        {"label": "新增粉丝", "value": review["newFollowers"], "unit": "人"},
                    ],
                    [
                        {
                            "title": "把评论问题做成续集",
                            "description": "整理测评视频评论区高频问题，做成下一条 Q&A 视频。",
                            "expectedImpact": "提升连续互动",
                            "relatedPage": "fans.stickiness",
                        }
                    ],
                    ["growth.stickiness", "fans.stickiness", "video.quality"],
                )
            )
            index += 1

    for platform, metrics in baselines["platforms"].items():
        label = next(item["label"] for item in PLATFORMS if item["value"] == platform)
        if metrics["publishShare"] > metrics["newFollowersShare"] * 1.25:
            insights.append(
                make_insight(
                    index,
                    "DIAGNOSIS",
                    "PLATFORM",
                    platform,
                    f"{label}投入和涨粉贡献不匹配",
                    f"{label}内容投入占比 {metrics['publishShare'] * 100:.1f}%，但涨粉贡献只有 {metrics['newFollowersShare'] * 100:.1f}%。",
                    "MEDIUM",
                    [
                        {"label": "投入占比", "value": round(metrics["publishShare"] * 100, 1), "unit": "%"},
                        {"label": "涨粉贡献", "value": round(metrics["newFollowersShare"] * 100, 1), "unit": "%"},
                    ],
                    [
                        {
                            "title": "减少低转粉泛内容",
                            "description": f"把{label}低转粉内容改为高转粉教程或测评的切片导流。",
                            "expectedImpact": "降低播放空转",
                            "relatedPage": "content.platform",
                        }
                    ],
                    ["growth.distribution", "content.platform", "content.source"],
                )
            )
            index += 1

    for topic in sorted(topics, key=lambda item: item["creatorFitScore"], reverse=True)[:5]:
        if topic["creatorFitScore"] < 85 or topic["riskLevel"] == "HIGH":
            continue
        insights.append(
            make_insight(
                index,
                "OPPORTUNITY",
                "TOPIC",
                topic["topicId"],
                f"{topic['topicName']}适合作为下一条内容选题",
                f"话题热度 {topic['heatScore']}，达人适配度 {topic['creatorFitScore']}，受众适配度 {topic['audienceFitScore']}。",
                "HIGH" if topic["creatorFitScore"] >= 90 else "MEDIUM",
                [
                    {"label": "话题热度", "value": topic["heatScore"]},
                    {"label": "达人适配度", "value": topic["creatorFitScore"]},
                    {"label": "受众适配度", "value": topic["audienceFitScore"]},
                ],
                [
                    {
                        "title": "生成下一条内容方案",
                        "description": f"围绕“{topic['topicName']}”做教程或测评结构，明确适合人群和收藏理由。",
                        "expectedImpact": "提升热点承接效率",
                        "relatedPage": "opportunities.advice",
                    }
                ],
                ["opportunities.hot", "opportunities.advice"],
            )
        )
        index += 1

    for account in accounts:
        if account["bindingStatus"] != "BOUND" or account["syncLatencySeconds"] > 60:
            label = next(item["label"] for item in PLATFORMS if item["value"] == account["platform"])
            insights.append(
                make_insight(
                    index,
                    "RISK",
                    "ACCOUNT",
                    account["accountId"],
                    f"{label}授权或同步状态需要处理",
                    f"{label}当前状态为 {account['bindingStatus']}，同步延迟 {account['syncLatencySeconds']} 秒。",
                    "HIGH",
                    [
                        {"label": "绑定状态", "value": account["bindingStatus"]},
                        {"label": "同步延迟", "value": account["syncLatencySeconds"], "unit": "秒"},
                    ],
                    [
                        {
                            "title": "刷新授权或检查采集任务",
                            "description": "避免增长分析因为数据断流失真。",
                            "expectedImpact": "提升数据完整性",
                            "relatedPage": "profile.bindings",
                        }
                    ],
                    ["profile.bindings", "profile.settings"],
                )
            )
            index += 1

    insights.extend(make_general_insights(index, baselines))
    return sorted(insights, key=lambda item: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[item["priority"]])[:30]


def make_general_insights(start_index: int, baselines: dict[str, Any]) -> list[dict[str, Any]]:
    extras = [
        (
            "DIAGNOSIS",
            "CREATOR",
            CREATOR_ID,
            "账号增长健康度稳定",
            f"账号平均转粉率 {baselines['averageConversionRate'] * 100:.2f}%，内容粘性处于可持续区间。",
            "MEDIUM",
            [
                {"label": "平均转粉率", "value": round(baselines["averageConversionRate"] * 100, 2), "unit": "%"},
                {"label": "平均收藏率", "value": round(baselines["averageSaveRate"] * 100, 2), "unit": "%"},
            ],
            [
                {
                    "title": "保持教程和测评主线",
                    "description": "继续用教程拉收藏，用测评拉评论，把泛种草控制在辅助内容。",
                    "expectedImpact": "稳定增长质量",
                    "relatedPage": "growth.overview",
                }
            ],
            ["growth.overview", "fans.growth"],
        ),
        (
            "OPPORTUNITY",
            "AUDIENCE",
            "seg_18_24_female",
            "18-24 女性仍是核心服务人群",
            "该人群更偏好可保存的教程内容，晚间 20:00-21:00 活跃度最高。",
            "MEDIUM",
            [
                {"label": "人群占比", "value": 46, "unit": "%"},
                {"label": "高活跃窗口", "value": "20:00-21:00"},
            ],
            [
                {
                    "title": "固定晚间发布教程主内容",
                    "description": "主内容安排在 20:00-21:00，午间只发轻量切片。",
                    "expectedImpact": "提升收藏和转粉",
                    "relatedPage": "fans.profile",
                }
            ],
            ["fans.profile", "content.time"],
        ),
        (
            "ACTION",
            "CREATOR",
            CREATOR_ID,
            "下一条内容优先做通勤妆教程",
            "教程类内容同时具备高收藏、高评论和高转粉，是当前最稳的增长路径。",
            "HIGH",
            [
                {"label": "教程涨粉贡献", "value": round(baselines["contentTypes"].get("TUTORIAL", {}).get("newFollowersShare", 0) * 100, 1), "unit": "%"},
                {"label": "教程收藏率", "value": round(baselines["contentTypes"].get("TUTORIAL", {}).get("saveRate", 0) * 100, 1), "unit": "%"},
            ],
            [
                {
                    "title": "制作 5 分钟通勤妆脚本",
                    "description": "结构采用结果预览、三步拆解、常见错误、收藏引导。",
                    "expectedImpact": "提升下一条内容转粉率",
                    "relatedPage": "opportunities.advice",
                }
            ],
            ["opportunities.advice", "opportunities.reference"],
        ),
        (
            "DIAGNOSIS",
            "ACCOUNT",
            "platform_health",
            "核心平台授权状态健康",
            "抖音、B站和小红书均处于已绑定状态，同步延迟满足 MVP 实时分析需要。",
            "MEDIUM",
            [
                {"label": "已绑定平台", "value": 3, "unit": "个"},
                {"label": "最大同步延迟", "value": 10, "unit": "秒"},
            ],
            [
                {
                    "title": "保持每周授权检查",
                    "description": "每周检查一次平台授权和同步延迟，避免数据断点影响复盘。",
                    "expectedImpact": "提升数据稳定性",
                    "relatedPage": "profile.bindings",
                }
            ],
            ["profile.bindings"],
        ),
        (
            "ACTION",
            "ACCOUNT",
            "collection_strategy",
            "采集频率可以支撑当前 MVP",
            "视频数据保持 5-30 秒采集，粉丝和评论数据足够支撑当前诊断页面。",
            "LOW",
            [
                {"label": "视频采集频率", "value": "5-30秒"},
                {"label": "覆盖平台", "value": 3, "unit": "个"},
            ],
            [
                {
                    "title": "优先保持视频和粉丝高频采集",
                    "description": "暂不提高话题和报告类数据频率，先保证增长总览和视频分析稳定。",
                    "expectedImpact": "控制采集成本",
                    "relatedPage": "profile.settings",
                }
            ],
            ["profile.settings"],
        ),
        (
            "ACTION",
            "ACCOUNT",
            "notification_rules",
            "提醒规则应聚焦可执行事件",
            "增长机会、异常流量、掉粉异常和授权状态是当前最值得保留的四类提醒。",
            "LOW",
            [
                {"label": "高价值提醒", "value": 4, "unit": "类"},
                {"label": "低价值提醒", "value": "暂不启用"},
            ],
            [
                {
                    "title": "只开启可行动提醒",
                    "description": "通知偏好中先保留增长机会、异常风险、内容复盘和授权状态。",
                    "expectedImpact": "减少无效打扰",
                    "relatedPage": "profile.notify",
                }
            ],
            ["profile.notify"],
        ),
    ]
    return [
        make_insight(start_index + offset, *payload)
        for offset, payload in enumerate(extras)
    ]


def make_view_models(data: dict[str, Any]) -> dict[str, Any]:
    insights = data["insights"]

    def target(prefix: str) -> list[dict[str, Any]]:
        return [item for item in insights if any(page.startswith(prefix) for page in item["pageTargets"])]

    latest_creator = data["creatorMetricSnapshots"][-1]
    snapshots = data["videoMetricSnapshots"]
    videos_by_id = {item["videoId"]: item for item in data["videos"]}
    top_videos = sorted(
        [{**row, **{"title": videos_by_id[row["videoId"]]["title"], "contentType": videos_by_id[row["videoId"]]["contentType"]}} for row in snapshots],
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
            "insights": target("video."),
        },
        "contentDistribution": {
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


def generate() -> dict[str, Any]:
    random.seed(RANDOM_SEED)
    creator = make_creator()
    accounts = make_platform_accounts()
    videos = make_videos()
    snapshots = make_video_snapshots(videos)
    traffic = make_traffic_sources(snapshots)
    trend = make_creator_trend(snapshots)
    audience = make_audience_profile()
    topics = make_topics()
    insights = make_insights(videos, snapshots, topics, accounts)
    data = {
        "meta": {
            "schemaVersion": "mvp-1",
            "generatedAt": now_iso(),
            "randomSeed": RANDOM_SEED,
        },
        "creator": creator,
        "platformAccounts": accounts,
        "videos": videos,
        "videoMetricSnapshots": snapshots,
        "videoTrafficSourceMetrics": traffic,
        "creatorMetricSnapshots": trend,
        "audienceProfileSnapshot": audience,
        "topicTrendSnapshots": topics,
        "insights": insights,
    }
    data["viewModels"] = make_view_models(data)
    return data


def main() -> None:
    data = generate()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    print(f"videos={len(data['videos'])} insights={len(data['insights'])}")


if __name__ == "__main__":
    main()
