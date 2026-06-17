"""Tests for Flask static frontend hosting."""

from __future__ import annotations

import os
import sys
from pathlib import Path


API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app import create_app  # noqa: E402
from repository import clear_repository_cache  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    os.environ["CREATORPULSE_DATA_SOURCE"] = "mock"
    clear_repository_cache()

    app = create_app()
    client = app.test_client()

    index = client.get("/")
    require(index.status_code == 200, "root should serve frontend index after build")
    require(b"CreatorPulse" in index.data, "frontend index should include CreatorPulse title")

    spa = client.get("/video")
    require(spa.status_code == 200, "SPA fallback should serve index")
    require(spa.data == index.data, "SPA fallback should return the same index file")

    health = client.get("/api/health")
    require(health.status_code == 200, "API route should still work")
    require(health.is_json, "API route should return JSON")

    openapi = client.get("/api/openapi.json")
    require(openapi.status_code == 200, "OpenAPI route should not be handled by SPA fallback")
    require(openapi.is_json, "OpenAPI route should return JSON")
    require(openapi.get_json()["openapi"] == "3.0.3", "OpenAPI route should return OpenAPI schema")

    print("Static frontend hosting tests passed")


if __name__ == "__main__":
    main()
