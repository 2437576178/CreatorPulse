"""Smoke tests for the CreatorPulse MVP mock API."""

from __future__ import annotations

import sys
from pathlib import Path


API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app import create_app  # noqa: E402


ENDPOINTS = {
    "/api/creators/demo/dashboard/growth": "growthDashboard",
    "/api/creators/demo/fans": "fansAnalysis",
    "/api/creators/demo/videos": "videoAnalysis",
    "/api/creators/demo/distribution": "contentDistribution",
    "/api/creators/demo/opportunities": "opportunities",
    "/api/creators/demo/profile": "profile",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    app = create_app()
    client = app.test_client()

    health = client.get("/api/health")
    require(health.status_code == 200, "health endpoint should return 200")
    health_payload = health.get_json()
    require(health_payload["status"] == "ok", "health status should be ok")
    require(health_payload["counts"]["videos"] == 27, "health should report 27 videos")
    require(20 <= health_payload["counts"]["insights"] <= 30, "health should report 20-30 insights")

    for endpoint, expected_name in ENDPOINTS.items():
        response = client.get(endpoint)
        require(response.status_code == 200, f"{endpoint} should return 200")
        payload = response.get_json()
        require(payload["creator"]["creatorId"] == "creator_001", f"{endpoint} should include creator")
        require(payload["meta"]["schemaVersion"] == "mvp-1", f"{endpoint} should include schema version")
        require(isinstance(payload["data"], dict), f"{endpoint} data should be an object")

        if expected_name != "profile":
            require("insights" in payload["data"], f"{endpoint} should include insights")

    missing = client.get("/api/creators/missing/fans")
    require(missing.status_code == 404, "missing creator should return 404")
    missing_payload = missing.get_json()
    require(missing_payload["error"]["code"] == "NOT_FOUND", "404 should use structured error body")

    print("MVP mock API tests passed")


if __name__ == "__main__":
    main()
