"""Tests for the CreatorPulse page ViewModel API contract."""

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
from database.import_mock_to_mysql import build_table_rows, load_json  # noqa: E402
from mysql_repository import MySQLRepository  # noqa: E402
from repository import clear_repository_cache  # noqa: E402
from view_model_contract import validate_api_payload, validate_view_models  # noqa: E402


ENDPOINTS = {
    "/api/creators/demo/dashboard/growth": "growthDashboard",
    "/api/creators/demo/fans": "fansAnalysis",
    "/api/creators/demo/videos": "videoAnalysis",
    "/api/creators/demo/distribution": "contentDistribution",
    "/api/creators/demo/opportunities": "opportunities",
    "/api/creators/demo/profile": "profile",
}


class ViewModelContractTest(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("CREATORPULSE_DATA_SOURCE", None)
        clear_repository_cache()

    def test_mock_api_endpoints_satisfy_contract(self) -> None:
        os.environ["CREATORPULSE_DATA_SOURCE"] = "mock"
        clear_repository_cache()
        client = create_app().test_client()

        for endpoint, view_model_name in ENDPOINTS.items():
            response = client.get(endpoint)
            self.assertEqual(response.status_code, 200)
            validate_api_payload(response.get_json(), view_model_name)

    def test_mysql_mapped_view_models_satisfy_contract(self) -> None:
        table_rows = build_table_rows(load_json())
        contract = MySQLRepository().to_contract(table_rows)

        validate_view_models(contract["viewModels"])


if __name__ == "__main__":
    unittest.main()
