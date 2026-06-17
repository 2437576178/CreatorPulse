"""Tests for database-driven mock event generation."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mock_generator.generate_events import build_videos_from_bindings, load_video_templates, make_event  # noqa: E402


class GenerateEventsTest(unittest.TestCase):
    def test_builds_video_templates_from_bound_platform_rows(self) -> None:
        rows = [
            {
                "creator_id": "creator_signup_001",
                "display_name": "新注册达人",
                "platform": "DOUYIN",
                "video_id": "video_douyin_01_creator_signup_001",
                "title": "注册后的第一条抖音内容",
                "content_type": "TUTORIAL",
                "publish_time": "2026-06-17 09:00:00",
                "topic_tags": '["效率工具"]',
                "views": 1200,
                "likes": 90,
                "comments": 12,
                "shares": 8,
                "saves": 16,
                "new_followers": 20,
            }
        ]

        videos = build_videos_from_bindings(rows)

        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]["creator_id"], "creator_signup_001")
        self.assertEqual(videos[0]["platform"], "DOUYIN")
        self.assertEqual(videos[0]["content_id"], "video_douyin_01_creator_signup_001")
        self.assertEqual(videos[0]["tags"], ["效率工具"])

    def test_generated_event_preserves_creator_and_video_identity(self) -> None:
        video = build_videos_from_bindings(
            [
                {
                    "creator_id": "creator_signup_001",
                    "display_name": "新注册达人",
                    "platform": "BILIBILI",
                    "video_id": "video_bilibili_01_creator_signup_001",
                    "title": "注册后的第一条B站内容",
                    "content_type": "REVIEW",
                    "publish_time": "2026-06-17 20:00:00",
                    "topic_tags": '["测评"]',
                    "views": 2200,
                    "likes": 180,
                    "comments": 22,
                    "shares": 18,
                    "saves": 36,
                    "new_followers": 28,
                }
            ]
        )[0]

        event = make_event(video, {}, 1)

        self.assertEqual(event["creator_id"], "creator_signup_001")
        self.assertEqual(event["platform"], "BILIBILI")
        self.assertEqual(event["content_id"], "video_bilibili_01_creator_signup_001")
        self.assertEqual(event["event_type"], "video_stats")

    def test_require_db_rejects_missing_mysql_config(self) -> None:
        with patch.dict("os.environ", {key: "" for key in ["MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD"]}):
            with self.assertRaises(RuntimeError):
                load_video_templates(env_file=None, require_db=True)


if __name__ == "__main__":
    unittest.main()
