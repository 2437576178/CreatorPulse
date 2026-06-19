"""Supported platform catalog for registration and display contracts."""

from __future__ import annotations

from typing import Any


PLATFORM_CATALOG: list[dict[str, Any]] = [
    {
        "value": "DOUYIN",
        "label": "抖音",
        "icon": "fa-music",
        "enabled": True,
        "mvpReady": True,
    },
    {
        "value": "BILIBILI",
        "label": "B站",
        "icon": "fa-play",
        "enabled": True,
        "mvpReady": True,
    },
    {
        "value": "XIAOHONGSHU",
        "label": "小红书",
        "icon": "fa-book-open",
        "enabled": True,
        "mvpReady": True,
    },
    {
        "value": "KUAISHOU",
        "label": "快手",
        "icon": "fa-bolt",
        "enabled": True,
        "mvpReady": True,
    },
    {
        "value": "WEIBO",
        "label": "微博",
        "icon": "fa-comments",
        "enabled": True,
        "mvpReady": True,
    },
    {
        "value": "WECHAT_VIDEO",
        "label": "视频号",
        "icon": "fa-video",
        "enabled": False,
        "mvpReady": False,
    },
]


def list_platforms(include_disabled: bool = False) -> list[dict[str, Any]]:
    platforms = PLATFORM_CATALOG if include_disabled else [item for item in PLATFORM_CATALOG if item["enabled"]]
    return [dict(item) for item in platforms]


def enabled_platform_values() -> list[str]:
    return [item["value"] for item in PLATFORM_CATALOG if item["enabled"]]


def platform_labels() -> dict[str, str]:
    return {item["value"]: item["label"] for item in PLATFORM_CATALOG}
