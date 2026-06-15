"""CreatorPulse MVP Flask mock API."""

from __future__ import annotations

from typing import Any

from flask import Flask, jsonify

from mock_repository import MockDataError, get_health, get_view_model


PAGE_VIEW_MODELS = {
    "dashboard/growth": "growthDashboard",
    "fans": "fansAnalysis",
    "videos": "videoAnalysis",
    "distribution": "contentDistribution",
    "opportunities": "opportunities",
    "profile": "profile",
}


def create_app() -> Flask:
    app = Flask(__name__)
    app.json.ensure_ascii = False

    @app.get("/api/health")
    def health() -> Any:
        return jsonify(get_health())

    @app.get("/api/creators/<creator_id>/dashboard/growth")
    def growth_dashboard(creator_id: str) -> Any:
        return jsonify(get_view_model(creator_id, "growthDashboard"))

    @app.get("/api/creators/<creator_id>/fans")
    def fans_analysis(creator_id: str) -> Any:
        return jsonify(get_view_model(creator_id, "fansAnalysis"))

    @app.get("/api/creators/<creator_id>/videos")
    def video_analysis(creator_id: str) -> Any:
        return jsonify(get_view_model(creator_id, "videoAnalysis"))

    @app.get("/api/creators/<creator_id>/distribution")
    def content_distribution(creator_id: str) -> Any:
        return jsonify(get_view_model(creator_id, "contentDistribution"))

    @app.get("/api/creators/<creator_id>/opportunities")
    def opportunities(creator_id: str) -> Any:
        return jsonify(get_view_model(creator_id, "opportunities"))

    @app.get("/api/creators/<creator_id>/profile")
    def profile(creator_id: str) -> Any:
        return jsonify(get_view_model(creator_id, "profile"))

    @app.errorhandler(KeyError)
    def handle_not_found(error: KeyError) -> Any:
        return (
            jsonify(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Requested creator or view model was not found",
                        "details": {"key": str(error)},
                    }
                }
            ),
            404,
        )

    @app.errorhandler(MockDataError)
    def handle_mock_data_error(error: MockDataError) -> Any:
        return (
            jsonify(
                {
                    "error": {
                        "code": "MOCK_DATA_ERROR",
                        "message": "Mock data cannot satisfy the API contract",
                        "details": str(error),
                    }
                }
            ),
            500,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
