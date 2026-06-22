"""CreatorPulse MVP Flask mock API."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from admin_simulation import AdminSimulationRepository
from auth import (
    AuthRepository,
    AuthenticationFailed,
    Unauthenticated,
    clear_session_user,
    current_user,
    set_session_user,
)
from config import ConfigError, get_secret_key
from mock_repository import MockDataError
from mysql_repository import MySQLRepositoryError
from openapi_contract import openapi_schema
from platform_catalog import list_platforms
from repository import RepositoryError, get_repository


PAGE_VIEW_MODELS = {
    "dashboard/growth": "growthDashboard",
    "fans": "fansAnalysis",
    "videos": "videoAnalysis",
    "distribution": "contentDistribution",
    "opportunities": "opportunities",
    "profile": "profile",
}

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
UPLOAD_DIR = ROOT_DIR / "api" / "uploads" / "avatars"
ALLOWED_AVATAR_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_AVATAR_BYTES = 2 * 1024 * 1024


def create_app() -> Flask:
    app = Flask(__name__)
    app.json.ensure_ascii = False
    app.secret_key = get_secret_key()

    @app.get("/api/health")
    def health() -> Any:
        return jsonify(get_repository().get_health())

    @app.get("/api/platforms")
    def platforms() -> Any:
        include_disabled = request.args.get("includeDisabled") in {"1", "true", "True"}
        return jsonify({"platforms": list_platforms(include_disabled=include_disabled)})

    @app.get("/api/openapi.json")
    def openapi() -> Any:
        return jsonify(openapi_schema())

    @app.post("/api/auth/login")
    def login() -> Any:
        payload = request.get_json(silent=True) or {}
        email = str(payload.get("email", ""))
        password = str(payload.get("password", ""))
        if not email or not password:
            return (
                jsonify({"error": {"code": "VALIDATION_ERROR", "message": "Email and password are required"}}),
                400,
            )

        user = AuthRepository().authenticate(email, password)
        set_session_user(user)
        return jsonify({"user": user.to_payload()})

    @app.post("/api/auth/register")
    def register() -> Any:
        payload = request.get_json(silent=True) or {}
        email = str(payload.get("email", ""))
        password = str(payload.get("password", ""))
        display_name = str(payload.get("displayName", ""))
        platforms = payload.get("platforms") or []
        if not isinstance(platforms, list):
            return (
                jsonify({"error": {"code": "VALIDATION_ERROR", "message": "Platforms must be a list"}}),
                400,
            )

        try:
            user = AuthRepository().register(email, password, display_name, platforms)
        except ValueError as error:
            return jsonify({"error": {"code": "VALIDATION_ERROR", "message": str(error)}}), 400

        set_session_user(user)
        return jsonify({"user": user.to_payload()})

    @app.post("/api/auth/logout")
    def logout() -> Any:
        clear_session_user()
        return jsonify({"status": "ok"})

    @app.get("/api/me")
    def me() -> Any:
        return jsonify({"user": current_user().to_payload()})

    @app.post("/api/me/avatar")
    def update_my_avatar() -> Any:
        user = current_user()
        uploaded = request.files.get("avatar")
        if uploaded is None or not uploaded.filename:
            return jsonify({"error": {"code": "VALIDATION_ERROR", "message": "Avatar image is required"}}), 400

        mime_type = uploaded.mimetype
        if mime_type not in ALLOWED_AVATAR_MIME_TYPES:
            return jsonify({"error": {"code": "VALIDATION_ERROR", "message": "Only JPG, PNG, or WebP images are supported"}}), 400

        uploaded.seek(0, 2)
        size = uploaded.tell()
        uploaded.seek(0)
        if size > MAX_AVATAR_BYTES:
            return jsonify({"error": {"code": "VALIDATION_ERROR", "message": "Avatar image must be 2MB or smaller"}}), 400

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        extension = ALLOWED_AVATAR_MIME_TYPES[mime_type]
        safe_stem = secure_filename(Path(uploaded.filename).stem) or "avatar"
        filename = f"{user.creator_id}_{safe_stem}_{uuid4().hex[:10]}{extension}"
        uploaded.save(UPLOAD_DIR / filename)

        avatar_url = f"/uploads/avatars/{filename}"
        AuthRepository().update_avatar_url(user.creator_id, avatar_url)
        refreshed_user = AuthRepository().get_user(user.user_id)
        return jsonify({"user": refreshed_user.to_payload()})

    @app.get("/api/me/dashboard/growth")
    def my_growth_dashboard() -> Any:
        user = current_user()
        return jsonify(get_repository().get_view_model(user.creator_id, "growthDashboard"))

    @app.get("/api/me/fans")
    def my_fans_analysis() -> Any:
        user = current_user()
        return jsonify(get_repository().get_view_model(user.creator_id, "fansAnalysis"))

    @app.get("/api/me/videos")
    def my_video_analysis() -> Any:
        user = current_user()
        return jsonify(get_repository().get_view_model(user.creator_id, "videoAnalysis"))

    @app.get("/api/me/distribution")
    def my_content_distribution() -> Any:
        user = current_user()
        return jsonify(get_repository().get_view_model(user.creator_id, "contentDistribution"))

    @app.get("/api/me/opportunities")
    def my_opportunities() -> Any:
        user = current_user()
        return jsonify(get_repository().get_view_model(user.creator_id, "opportunities"))

    @app.get("/api/me/profile")
    def my_profile() -> Any:
        user = current_user()
        return jsonify(get_repository().get_view_model(user.creator_id, "profile"))

    @app.get("/api/me/reports")
    def my_reports() -> Any:
        user = current_user()
        report_type = request.args.get("type")
        page = max(int(request.args.get("page", "1")), 1)
        page_size = min(max(int(request.args.get("pageSize", "10")), 1), 100)
        return jsonify(get_repository().list_reports(user.creator_id, report_type=report_type, page=page, page_size=page_size))

    @app.get("/api/me/reports/<report_id>")
    def my_report_detail(report_id: str) -> Any:
        user = current_user()
        return jsonify(get_repository().get_report(user.creator_id, report_id))

    @app.get("/api/admin/simulation/status")
    def admin_simulation_status() -> Any:
        return jsonify(AdminSimulationRepository().get_status())

    @app.get("/api/admin/simulation/creators")
    def admin_simulation_creators() -> Any:
        return jsonify(AdminSimulationRepository().list_creators())

    @app.get("/api/admin/simulation/events")
    def admin_simulation_events() -> Any:
        limit = min(max(int(request.args.get("limit", "30")), 1), 100)
        return jsonify(AdminSimulationRepository().list_events(limit=limit))

    @app.get("/api/admin/offline/status")
    def admin_offline_status() -> Any:
        return jsonify(AdminSimulationRepository().get_offline_status())

    @app.post("/api/admin/offline/recompute")
    def admin_offline_recompute() -> Any:
        payload = request.get_json(silent=True) or {}
        creator_id = str(payload.get("creatorId", ""))
        period_start = str(payload.get("periodStart", ""))
        period_end = str(payload.get("periodEnd", ""))
        recompute_scope = str(payload.get("recomputeScope", "ALL"))
        requested_by = str(payload.get("requestedBy", "admin"))
        if not creator_id or not period_start or not period_end:
            return (
                jsonify({"error": {"code": "VALIDATION_ERROR", "message": "creatorId, periodStart, and periodEnd are required"}}),
                400,
            )
        try:
            result = AdminSimulationRepository().create_recompute_request(
                creator_id=creator_id,
                period_start=period_start,
                period_end=period_end,
                recompute_scope=recompute_scope,
                requested_by=requested_by,
            )
        except ValueError as error:
            return jsonify({"error": {"code": "VALIDATION_ERROR", "message": str(error)}}), 400
        return jsonify(result), 201

    @app.get("/api/creators/<creator_id>/dashboard/growth")
    def growth_dashboard(creator_id: str) -> Any:
        return jsonify(get_repository().get_view_model(creator_id, "growthDashboard"))

    @app.get("/api/creators/<creator_id>/fans")
    def fans_analysis(creator_id: str) -> Any:
        return jsonify(get_repository().get_view_model(creator_id, "fansAnalysis"))

    @app.get("/api/creators/<creator_id>/videos")
    def video_analysis(creator_id: str) -> Any:
        return jsonify(get_repository().get_view_model(creator_id, "videoAnalysis"))

    @app.get("/api/creators/<creator_id>/distribution")
    def content_distribution(creator_id: str) -> Any:
        return jsonify(get_repository().get_view_model(creator_id, "contentDistribution"))

    @app.get("/api/creators/<creator_id>/opportunities")
    def opportunities(creator_id: str) -> Any:
        return jsonify(get_repository().get_view_model(creator_id, "opportunities"))

    @app.get("/api/creators/<creator_id>/profile")
    def profile(creator_id: str) -> Any:
        return jsonify(get_repository().get_view_model(creator_id, "profile"))

    @app.get("/")
    def serve_frontend_index() -> Any:
        if not (FRONTEND_DIST / "index.html").exists():
            return (
                jsonify(
                    {
                        "error": {
                            "code": "FRONTEND_BUILD_MISSING",
                            "message": "frontend/dist/index.html was not found. Run: cd frontend && npm run build",
                        }
                    }
                ),
                404,
            )
        return send_from_directory(FRONTEND_DIST, "index.html")

    @app.get("/assets/<path:filename>")
    def serve_frontend_asset(filename: str) -> Any:
        return send_from_directory(FRONTEND_DIST / "assets", filename)

    @app.get("/uploads/avatars/<path:filename>")
    def serve_avatar_upload(filename: str) -> Any:
        return send_from_directory(UPLOAD_DIR, filename)

    @app.get("/<path:path>")
    def serve_frontend_spa(path: str) -> Any:
        if path.startswith("api/"):
            raise KeyError(path)
        return serve_frontend_index()

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

    @app.errorhandler(ConfigError)
    @app.errorhandler(RepositoryError)
    @app.errorhandler(MySQLRepositoryError)
    def handle_repository_error(error: Exception) -> Any:
        return (
            jsonify(
                {
                    "error": {
                        "code": "DATA_SOURCE_ERROR",
                        "message": "Configured data source cannot satisfy the API contract",
                        "details": str(error),
                    }
                }
            ),
            500,
        )

    @app.errorhandler(Unauthenticated)
    def handle_unauthenticated(error: Unauthenticated) -> Any:
        return jsonify({"error": {"code": "UNAUTHENTICATED", "message": str(error)}}), 401

    @app.errorhandler(AuthenticationFailed)
    def handle_authentication_failed(error: AuthenticationFailed) -> Any:
        return jsonify({"error": {"code": "AUTHENTICATION_FAILED", "message": str(error)}}), 401

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
