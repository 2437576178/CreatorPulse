"""Tests for the machine-readable MVP OpenAPI contract."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app import create_app  # noqa: E402
from openapi_contract import LEGACY_CREATOR_PAGE_ENDPOINTS, PAGE_ENDPOINTS, openapi_schema  # noqa: E402
from repository import clear_repository_cache  # noqa: E402


class OpenAPIContractTest(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("CREATORPULSE_DATA_SOURCE", None)
        clear_repository_cache()

    def test_schema_contains_all_mvp_paths_and_components(self) -> None:
        schema = openapi_schema()

        self.assertEqual(schema["openapi"], "3.0.3")
        self.assertIn("/api/health", schema["paths"])
        self.assertIn("/api/auth/login", schema["paths"])
        self.assertIn("/api/auth/logout", schema["paths"])
        self.assertIn("/api/me", schema["paths"])
        for path, component_name in PAGE_ENDPOINTS.items():
            self.assertIn(path, schema["paths"])
            self.assertIn(component_name, schema["components"]["schemas"])

        for path in LEGACY_CREATOR_PAGE_ENDPOINTS:
            self.assertIn(path, schema["paths"])
            self.assertTrue(schema["paths"][path]["get"]["deprecated"])

        self.assertIn("AuthUser", schema["components"]["schemas"])
        self.assertIn("AuthUserResponse", schema["components"]["schemas"])
        self.assertIn("PageResponseBase", schema["components"]["schemas"])
        self.assertIn("ErrorResponse", schema["components"]["schemas"])
        self.assertEqual(
            schema["components"]["schemas"]["videoAnalysis"]["required"],
            ["videos", "snapshots", "topVideos", "sparkContributions", "insights"],
        )

    def test_flask_serves_openapi_json_without_data_source_query(self) -> None:
        os.environ["CREATORPULSE_DATA_SOURCE"] = "mock"
        clear_repository_cache()
        response = create_app().test_client().get("/api/openapi.json")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["info"]["version"], "mvp-1")
        self.assertIn("/api/me/videos", payload["paths"])
        self.assertIn("/api/creators/{creatorId}/videos", payload["paths"])


if __name__ == "__main__":
    unittest.main()
