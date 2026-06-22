"""Tests for account login and creator ownership mapping."""

from __future__ import annotations

import os
import sys
import unittest
from io import BytesIO
from pathlib import Path
from uuid import uuid4


ROOT_DIR = Path(__file__).resolve().parents[2]
API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app  # noqa: E402
from repository import clear_repository_cache  # noqa: E402
from view_model_contract import validate_api_payload  # noqa: E402


class AuthAPITest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["CREATORPULSE_DATA_SOURCE"] = "mysql"
        clear_repository_cache()
        self.client = create_app().test_client()

    def tearDown(self) -> None:
        os.environ.pop("CREATORPULSE_DATA_SOURCE", None)
        clear_repository_cache()

    def test_me_requires_login(self) -> None:
        response = self.client.get("/api/me")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"]["code"], "UNAUTHENTICATED")

    def test_login_maps_account_to_creator_and_me_endpoints_use_session_creator(self) -> None:
        login = self.client.post(
            "/api/auth/login",
            json={"email": "demo@creatorpulse.local", "password": "demo123456"},
        )
        self.assertEqual(login.status_code, 200, login.get_data(as_text=True))
        self.assertEqual(login.get_json()["user"]["creatorId"], "creator_001")

        me = self.client.get("/api/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["user"]["creatorId"], "creator_001")
        self.assertIn("avatarUrl", me.get_json()["user"])

        growth = self.client.get("/api/me/dashboard/growth")
        self.assertEqual(growth.status_code, 200, growth.get_data(as_text=True))
        payload = growth.get_json()
        self.assertEqual(payload["creator"]["creatorId"], "creator_001")
        validate_api_payload(payload, "growthDashboard")

    def test_me_reports_returns_creator_scoped_report_list(self) -> None:
        login = self.client.post(
            "/api/auth/login",
            json={"email": "demo@creatorpulse.local", "password": "demo123456"},
        )
        self.assertEqual(login.status_code, 200, login.get_data(as_text=True))

        response = self.client.get("/api/me/reports?type=DAILY")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertIn("items", payload)
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["pageSize"], 10)
        self.assertTrue(all(item["creatorId"] == "creator_001" for item in payload["items"]))

    def test_second_account_cannot_see_first_creator_through_me_endpoint(self) -> None:
        login = self.client.post(
            "/api/auth/login",
            json={"email": "style@creatorpulse.local", "password": "demo123456"},
        )
        self.assertEqual(login.status_code, 200, login.get_data(as_text=True))
        self.assertEqual(login.get_json()["user"]["creatorId"], "creator_002")

        growth = self.client.get("/api/me/dashboard/growth")
        self.assertEqual(growth.status_code, 200, growth.get_data(as_text=True))
        self.assertEqual(growth.get_json()["creator"]["creatorId"], "creator_002")

    def test_third_account_maps_to_creator_three(self) -> None:
        login = self.client.post(
            "/api/auth/login",
            json={"email": "tech@creatorpulse.local", "password": "demo123456"},
        )
        self.assertEqual(login.status_code, 200, login.get_data(as_text=True))
        self.assertEqual(login.get_json()["user"]["creatorId"], "creator_003")

        videos = self.client.get("/api/me/videos")
        self.assertEqual(videos.status_code, 200, videos.get_data(as_text=True))
        payload = videos.get_json()
        self.assertEqual(payload["creator"]["creatorId"], "creator_003")
        self.assertTrue(all(item["creatorId"] == "creator_003" for item in payload["data"]["videos"]))

    def test_logout_clears_session(self) -> None:
        self.client.post("/api/auth/login", json={"email": "demo@creatorpulse.local", "password": "demo123456"})

        logout = self.client.post("/api/auth/logout")
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(self.client.get("/api/me").status_code, 401)

    def test_upload_avatar_updates_current_creator(self) -> None:
        self.client.post("/api/auth/login", json={"email": "demo@creatorpulse.local", "password": "demo123456"})

        response = self.client.post(
            "/api/me/avatar",
            data={"avatar": (BytesIO(b"\x89PNG\r\n\x1a\navatar"), "avatar.png")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        avatar_url = response.get_json()["user"]["avatarUrl"]
        self.assertTrue(avatar_url.startswith("/uploads/avatars/creator_001_avatar_"))

        me = self.client.get("/api/me")
        self.assertEqual(me.get_json()["user"]["avatarUrl"], avatar_url)

    def test_upload_avatar_rejects_non_image(self) -> None:
        self.client.post("/api/auth/login", json={"email": "demo@creatorpulse.local", "password": "demo123456"})

        response = self.client.post(
            "/api/me/avatar",
            data={"avatar": (BytesIO(b"not an image"), "avatar.txt")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "VALIDATION_ERROR")

    def test_register_creates_creator_with_selected_platforms_and_logs_in(self) -> None:
        email = f"signup-{uuid4().hex[:8]}@creatorpulse.local"
        response = self.client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": "demo123456",
                "displayName": "注册测试达人",
                "platforms": ["DOUYIN", "XIAOHONGSHU"],
            },
        )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        user = response.get_json()["user"]
        self.assertEqual(user["email"], email)
        self.assertTrue(user["creatorId"].startswith("creator_"))

        profile = self.client.get("/api/me/profile")
        self.assertEqual(profile.status_code, 200, profile.get_data(as_text=True))
        accounts = profile.get_json()["data"]["platformAccounts"]
        self.assertEqual({item["platform"] for item in accounts}, {"DOUYIN", "XIAOHONGSHU"})

        growth = self.client.get("/api/me/dashboard/growth")
        self.assertEqual(growth.status_code, 200, growth.get_data(as_text=True))
        growth_payload = growth.get_json()
        self.assertEqual(growth_payload["data"]["currentSnapshot"]["dataStatus"], "WAITING_FOR_EVENTS")
        self.assertEqual(growth_payload["data"]["topVideos"], [])

        videos = self.client.get("/api/me/videos")
        self.assertEqual(videos.status_code, 200, videos.get_data(as_text=True))
        videos_payload = videos.get_json()
        self.assertTrue(videos_payload["data"]["videos"])
        self.assertEqual(videos_payload["data"]["snapshots"], [])
        self.assertEqual(videos_payload["data"]["sparkContributions"], [])


if __name__ == "__main__":
    unittest.main()
