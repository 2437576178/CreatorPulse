"""Build MVP Kafka events from the unified mock dataset."""

from __future__ import annotations

from typing import Any

try:
    from .message_contract import deterministic_event_id, topic_for_event_type, validate_event
except ImportError:
    from message_contract import deterministic_event_id, topic_for_event_type, validate_event


def pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def video_stats_events(data: dict[str, Any]) -> list[dict[str, Any]]:
    videos_by_id = {item["videoId"]: item for item in data["videos"]}
    traffic_by_video: dict[str, list[dict[str, Any]]] = {}
    for row in data["videoTrafficSourceMetrics"]:
        traffic_by_video.setdefault(row["videoId"], []).append(row)

    events = []
    for snapshot in data["videoMetricSnapshots"]:
        video = videos_by_id[snapshot["videoId"]]
        fetch_time = snapshot["collectedAt"]
        sources = traffic_by_video.get(snapshot["videoId"], [])
        total_source_views = sum(item["views"] for item in sources) or 1
        event = {
            "topic": topic_for_event_type("video_stats"),
            "event_id": deterministic_event_id("video_stats", snapshot["videoId"], fetch_time),
            "event_type": "video_stats",
            "platform": snapshot["platform"],
            "fetch_time": fetch_time,
            "creator_id": snapshot["creatorId"],
            "content_id": snapshot["videoId"],
            "title": video["title"],
            "content_type": video["contentType"],
            "publish_time": video["publishTime"],
            "publish_hour": int(video["publishTime"][11:13]),
            "tags": video["topicTags"],
            "stats": {
                "play_count": snapshot["views"],
                "like_count": snapshot["likes"],
                "comment_count": snapshot["comments"],
                "share_count": snapshot["shares"],
                "save_count": snapshot["saves"],
                "interaction_rate": snapshot["engagementRate"],
                "completion_rate": snapshot["completionRate"],
                "average_watch_seconds": snapshot["averageWatchSeconds"],
            },
            "growth": {
                "play_growth_5s": max(1, int(snapshot["views"] * 0.0012)),
                "play_growth_1h": max(1, int(snapshot["views"] * 0.045)),
                "is_accelerating": snapshot["conversionRate"] >= 0.006,
                "velocity_score": round(min(100, snapshot["engagementRate"] * 420), 2),
                "new_followers": snapshot["newFollowers"],
                "profile_visits": snapshot["profileVisits"],
            },
            "traffic_source": {
                item["source"].lower(): {
                    "views": item["views"],
                    "view_ratio": pct(item["views"], total_source_views),
                    "new_followers": item["newFollowers"],
                    "conversion_rate": item["conversionRate"],
                }
                for item in sources
            },
        }
        validate_event(event)
        events.append(event)
    return events


def creator_stats_events(data: dict[str, Any]) -> list[dict[str, Any]]:
    events = []
    platform = "ALL"
    for snapshot in data["creatorMetricSnapshots"]:
        event = {
            "topic": topic_for_event_type("creator_stats"),
            "event_id": deterministic_event_id("creator_stats", snapshot["creatorId"], snapshot["date"]),
            "event_type": "creator_stats",
            "platform": platform,
            "fetch_time": f"{snapshot['date']}T23:59:00+08:00",
            "creator_id": snapshot["creatorId"],
            "follower": {
                "total_followers": snapshot["totalFollowers"],
                "new_followers_today": snapshot["newFollowers"],
                "lost_followers_today": snapshot["lostFollowers"],
                "net_growth": snapshot["netFollowers"],
                "view_to_follower_rate": snapshot["viewToFollowerRate"],
            },
        }
        validate_event(event)
        events.append(event)
    return events


def topic_trend_events(data: dict[str, Any]) -> list[dict[str, Any]]:
    fetch_time = data["meta"]["generatedAt"]
    events = []
    for topic in data["topicTrendSnapshots"]:
        event = {
            "topic": topic_for_event_type("topic_trend"),
            "event_id": deterministic_event_id("topic_trend", topic["topicId"], fetch_time),
            "event_type": "topic_trend",
            "platform": "MULTI",
            "fetch_time": fetch_time,
            "topic_id": topic["topicId"],
            "hashtag": topic["topicName"],
            "heat_score": topic["heatScore"],
            "growth_rate": topic["growthRate"],
            "platform_breakdown": {platform: topic["heatScore"] for platform in topic["platforms"]},
            "audience_fit_score": topic["audienceFitScore"],
            "creator_fit_score": topic["creatorFitScore"],
            "risk_level": topic["riskLevel"],
        }
        validate_event(event)
        events.append(event)
    return events


def comment_events(data: dict[str, Any], limit: int = 12) -> list[dict[str, Any]]:
    events = []
    for index, video in enumerate(data["videos"][:limit], start=1):
        event = {
            "topic": topic_for_event_type("comment"),
            "event_id": deterministic_event_id("comment", video["videoId"], index),
            "event_type": "comment",
            "platform": video["platform"],
            "fetch_time": data["meta"]["generatedAt"],
            "creator_id": video["creatorId"],
            "content_id": video["videoId"],
            "comment_id": f"comment_{index:04d}",
            "comment_text": f"想看{video['title']}的后续细节",
            "sentiment": "POSITIVE" if index % 5 else "NEUTRAL",
            "sentiment_score": 0.82 if index % 5 else 0.55,
        }
        validate_event(event)
        events.append(event)
    return events


def danmaku_events(data: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    bilibili_videos = [item for item in data["videos"] if item["platform"] == "BILIBILI"][:limit]
    events = []
    for index, video in enumerate(bilibili_videos, start=1):
        event = {
            "topic": topic_for_event_type("danmaku"),
            "event_id": deterministic_event_id("danmaku", video["videoId"], index),
            "event_type": "danmaku",
            "platform": "BILIBILI",
            "fetch_time": data["meta"]["generatedAt"],
            "creator_id": video["creatorId"],
            "content_id": video["videoId"],
            "danmaku_id": f"danmaku_{index:04d}",
            "danmaku_text": "这里的步骤很适合新手",
            "video_timestamp": index * 18,
        }
        validate_event(event)
        events.append(event)
    return events


def build_events(data: dict[str, Any]) -> list[dict[str, Any]]:
    events = []
    events.extend(video_stats_events(data))
    events.extend(creator_stats_events(data))
    events.extend(comment_events(data))
    events.extend(danmaku_events(data))
    events.extend(topic_trend_events(data))
    return events
