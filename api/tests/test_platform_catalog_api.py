"""Tests for the supported platform catalog API."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app  # noqa: E402
from repository import clear_repository_cache  # noqa: E402


class PlatformCatalogAPITest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["CREATORPULSE_DATA_SOURCE"] = "mock"
        clear_repository_cache()
        self.client = create_app().test_client()

    def tearDown(self) -> None:
        os.environ.pop("CREATORPULSE_DATA_SOURCE", None)
        clear_repository_cache()

    def test_platforms_returns_enabled_mvp_platforms(self) -> None:
        response = self.client.get("/api/platforms")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        platforms = response.get_json()["platforms"]
        self.assertEqual(
            [item["value"] for item in platforms],
            ["DOUYIN", "BILIBILI", "XIAOHONGSHU", "KUAISHOU", "WEIBO"],
        )
        self.assertTrue(all(item["enabled"] for item in platforms))
        self.assertTrue(all(item["mvpReady"] for item in platforms))

    def test_platforms_can_include_future_disabled_platforms(self) -> None:
        response = self.client.get("/api/platforms?includeDisabled=1")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        platforms = response.get_json()["platforms"]
        values = [item["value"] for item in platforms]
        self.assertIn("KUAISHOU", values)
        self.assertIn("WEIBO", values)
        self.assertIn("WECHAT_VIDEO", values)
        self.assertFalse(next(item for item in platforms if item["value"] == "WECHAT_VIDEO")["enabled"])


if __name__ == "__main__":
    unittest.main()
