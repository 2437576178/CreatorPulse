"""Optional live MySQL API integration test.

This test is skipped unless a local .env exists with real MYSQL_* values. It
does not create or import data; run scripts/setup_local_mysql.py --execute
first when you want to verify the live MySQL data source.
"""

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
from config import DEFAULT_ENV_PATH, load_env_file  # noqa: E402
from repository import clear_repository_cache  # noqa: E402
from view_model_contract import validate_api_payload  # noqa: E402


PLACEHOLDER_VALUES = {"your_user", "your_password"}
MYSQL_KEYS = ["MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD"]
ENDPOINTS = {
    "/api/creators/demo/dashboard/growth": "growthDashboard",
    "/api/creators/demo/fans": "fansAnalysis",
    "/api/creators/demo/videos": "videoAnalysis",
    "/api/creators/demo/distribution": "contentDistribution",
    "/api/creators/demo/opportunities": "opportunities",
    "/api/creators/demo/profile": "profile",
}


def mysql_env_ready() -> tuple[bool, str]:
    load_env_file(DEFAULT_ENV_PATH)
    if not DEFAULT_ENV_PATH.exists():
        return False, ".env not found"

    missing = [key for key in MYSQL_KEYS if not os.environ.get(key)]
    if missing:
        return False, f"missing MYSQL config: {', '.join(missing)}"

    placeholders = [key for key in MYSQL_KEYS if os.environ.get(key) in PLACEHOLDER_VALUES]
    if placeholders:
        return False, f"placeholder MYSQL config: {', '.join(placeholders)}"

    return True, "ready"


class MySQLAPIIntegrationTest(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("CREATORPULSE_DATA_SOURCE", None)
        clear_repository_cache()

    def test_live_mysql_api_satisfies_view_model_contract(self) -> None:
        ready, reason = mysql_env_ready()
        if not ready:
            self.skipTest(f"Live MySQL integration skipped: {reason}")

        os.environ["CREATORPULSE_DATA_SOURCE"] = "mysql"
        clear_repository_cache()
        client = create_app().test_client()

        health = client.get("/api/health")
        self.assertEqual(health.status_code, 200, health.get_data(as_text=True))
        self.assertEqual(health.get_json()["dataSource"], "mysql")

        for endpoint, view_model_name in ENDPOINTS.items():
            response = client.get(endpoint)
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            validate_api_payload(response.get_json(), view_model_name)

        second_creator = client.get("/api/creators/creator_002/dashboard/growth")
        if second_creator.status_code == 200:
            payload = second_creator.get_json()
            self.assertEqual(payload["creator"]["creatorId"], "creator_002")
            self.assertTrue(all(item["creatorId"] == "creator_002" for item in payload["data"]["insights"]))


if __name__ == "__main__":
    unittest.main()
