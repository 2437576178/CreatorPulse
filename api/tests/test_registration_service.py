"""Tests for creator registration and initial simulation data setup."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from registration_service import normalize_platforms, seed_registered_creator_rows  # noqa: E402


class RegistrationServiceTest(unittest.TestCase):
    def test_normalize_platforms_accepts_known_platforms_in_stable_order(self) -> None:
        platforms = normalize_platforms(["XIAOHONGSHU", "DOUYIN", "DOUYIN", "BILIBILI"])

        self.assertEqual(platforms, ["DOUYIN", "BILIBILI", "XIAOHONGSHU"])

    def test_normalize_platforms_rejects_empty_or_unknown_platforms(self) -> None:
        with self.assertRaises(ValueError):
            normalize_platforms([])
        with self.assertRaises(ValueError):
            normalize_platforms(["WEIBO"])

    def test_seed_registered_creator_rows_filters_to_selected_platforms(self) -> None:
        rows = seed_registered_creator_rows(
            creator_id="creator_signup_001",
            display_name="新注册达人",
            platforms=["DOUYIN", "XIAOHONGSHU"],
        )

        self.assertEqual(rows["creators"][0]["creator_id"], "creator_signup_001")
        self.assertEqual({row["platform"] for row in rows["platform_accounts"]}, {"DOUYIN", "XIAOHONGSHU"})
        self.assertEqual({row["platform"] for row in rows["videos"]}, {"DOUYIN", "XIAOHONGSHU"})
        self.assertEqual({row["platform"] for row in rows["video_metric_snapshots"]}, {"DOUYIN", "XIAOHONGSHU"})
        self.assertEqual({row["creator_id"] for row in rows["videos"]}, {"creator_signup_001"})
        self.assertTrue(all(row["video_id"].endswith("_creator_signup_001") for row in rows["videos"]))


if __name__ == "__main__":
    unittest.main()
