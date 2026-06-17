"""CreatorPulse Kafka message contract.

The MVP uses these event shapes before real platform APIs are connected. The
contract stays close to 03_数据模拟与业务流程详解.md while mapping back to the
current MVP mock data objects.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any


TOPICS_BY_EVENT_TYPE = {
    "video_stats": "video_stats_topic",
    "creator_stats": "creator_stats_topic",
    "comment": "comment_topic",
    "danmaku": "danmaku_topic",
    "topic_trend": "topic_trend_topic",
}

REQUIRED_FIELDS_BY_EVENT_TYPE = {
    "video_stats": {
        "event_id",
        "event_type",
        "platform",
        "fetch_time",
        "creator_id",
        "content_id",
        "content_type",
        "publish_time",
        "stats",
        "growth",
        "traffic_source",
    },
    "creator_stats": {
        "event_id",
        "event_type",
        "platform",
        "fetch_time",
        "creator_id",
        "follower",
    },
    "comment": {
        "event_id",
        "event_type",
        "platform",
        "fetch_time",
        "creator_id",
        "content_id",
        "comment_id",
        "comment_text",
        "sentiment",
        "sentiment_score",
    },
    "danmaku": {
        "event_id",
        "event_type",
        "platform",
        "fetch_time",
        "creator_id",
        "content_id",
        "danmaku_id",
        "danmaku_text",
        "video_timestamp",
    },
    "topic_trend": {
        "event_id",
        "event_type",
        "platform",
        "fetch_time",
        "topic_id",
        "hashtag",
        "heat_score",
        "growth_rate",
        "platform_breakdown",
    },
}


class MessageContractError(ValueError):
    """Raised when an event does not match the MVP Kafka contract."""


def topic_for_event_type(event_type: str) -> str:
    try:
        return TOPICS_BY_EVENT_TYPE[event_type]
    except KeyError as exc:
        raise MessageContractError(f"Unsupported event_type: {event_type}") from exc


def deterministic_event_id(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"evt_{digest}"


def validate_event(event: dict[str, Any]) -> None:
    event_type = event.get("event_type")
    if event_type not in REQUIRED_FIELDS_BY_EVENT_TYPE:
        raise MessageContractError(f"Unsupported event_type: {event_type}")

    missing = sorted(REQUIRED_FIELDS_BY_EVENT_TYPE[event_type] - set(event))
    if missing:
        raise MessageContractError(f"{event_type} missing fields: {', '.join(missing)}")

    if event.get("event_id") == "":
        raise MessageContractError("event_id cannot be empty")
    if event.get("topic") and event["topic"] != topic_for_event_type(event_type):
        raise MessageContractError(f"Event topic does not match event_type: {event_type}")
    if "fetch_time" in event:
        try:
            datetime.fromisoformat(event["fetch_time"])
        except ValueError as exc:
            raise MessageContractError(f"fetch_time must be ISO datetime: {event['fetch_time']}") from exc


def validate_events(events: list[dict[str, Any]]) -> None:
    for event in events:
        validate_event(event)
