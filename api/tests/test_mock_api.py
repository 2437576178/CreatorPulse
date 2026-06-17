"""Smoke tests for the CreatorPulse MVP mock API."""

from __future__ import annotations

import os
import sys
from pathlib import Path


API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app import create_app  # noqa: E402
from repository import clear_repository_cache  # noqa: E402
from view_model_contract import validate_api_payload  # noqa: E402


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
    os.environ["CREATORPULSE_DATA_SOURCE"] = "mock"
    clear_repository_cache()

    app = create_app()
    client = app.test_client()

    health = client.get("/api/health")
    require(health.status_code == 200, "health endpoint should return 200")
    health_payload = health.get_json()
    require(health_payload["status"] == "ok", "health status should be ok")
    require(health_payload["counts"]["videos"] == 27, "health should report 27 videos")
    require(20 <= health_payload["counts"]["insights"] <= 32, "health should report rule and runtime Spark insights")
    require(health_payload["counts"]["sparkPlatformMetricSummaries"] == 3, "health should report 3 Spark platform rows")
    require(health_payload["counts"]["sparkVideoFollowerContributions"] == 10, "health should report 10 Spark contribution rows")

    for endpoint, expected_name in ENDPOINTS.items():
        response = client.get(endpoint)
        require(response.status_code == 200, f"{endpoint} should return 200")
        payload = response.get_json()
        require(payload["creator"]["creatorId"] == "creator_001", f"{endpoint} should include creator")
        require(payload["meta"]["schemaVersion"] == "mvp-1", f"{endpoint} should include schema version")
        require(isinstance(payload["data"], dict), f"{endpoint} data should be an object")
        validate_api_payload(payload, expected_name)

        if expected_name != "profile":
            require("insights" in payload["data"], f"{endpoint} should include insights")
        if expected_name == "videoAnalysis":
            require(len(payload["data"]["sparkContributions"]) == 10, "video endpoint should expose Spark contributions")
            require(
                any(item["generatedBy"] == "SPARK_RULE_ENGINE" for item in payload["data"]["insights"]),
                "video endpoint should include Spark-generated insight",
            )
        if expected_name == "contentDistribution":
            require(
                len(payload["data"]["sparkPlatformSummaries"]) == 3,
                "distribution endpoint should expose Spark platform summaries",
            )
            require(
                any(item["generatedBy"] == "SPARK_RULE_ENGINE" for item in payload["data"]["insights"]),
                "distribution endpoint should include Spark-generated insight",
            )

    missing = client.get("/api/creators/missing/fans")
    require(missing.status_code == 404, "missing creator should return 404")
    missing_payload = missing.get_json()
    require(missing_payload["error"]["code"] == "NOT_FOUND", "404 should use structured error body")

    print("MVP mock API tests passed")


if __name__ == "__main__":
    main()
