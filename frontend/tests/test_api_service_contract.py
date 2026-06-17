"""Validate frontend API service paths against the backend OpenAPI contract."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from openapi_contract import PAGE_ENDPOINTS  # noqa: E402


SERVICE_PATH = ROOT_DIR / "frontend" / "src" / "services" / "api.js"


def extract_request_paths(source: str) -> set[str]:
    return set(re.findall(r"request\(\"([^\"]+)\"\)", source))


class FrontendAPIServiceContractTest(unittest.TestCase):
    def test_frontend_page_fetches_use_session_scoped_openapi_endpoints(self) -> None:
        source = SERVICE_PATH.read_text(encoding="utf-8")
        frontend_paths = extract_request_paths(source) - {"/api/me"}

        self.assertEqual(frontend_paths, set(PAGE_ENDPOINTS))

    def test_frontend_service_does_not_expose_creator_id_selection(self) -> None:
        source = SERVICE_PATH.read_text(encoding="utf-8")

        self.assertNotIn("CREATOR_ID", source)
        self.assertNotIn("/api/creators", source)
        for path in extract_request_paths(source):
            self.assertNotIn("{creatorId}", path)


if __name__ == "__main__":
    unittest.main()
