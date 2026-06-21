"""ViewModel contract validation for CreatorPulse MVP API responses."""

from __future__ import annotations

from typing import Any


VIEW_MODEL_REQUIRED_FIELDS = {
    "growthDashboard": {
        "currentSnapshot": dict,
        "topVideos": list,
        "insights": list,
    },
    "fansAnalysis": {
        "trend": list,
        "audienceProfile": dict,
        "insights": list,
    },
    "videoAnalysis": {
        "videos": list,
        "snapshots": list,
        "topVideos": list,
        "sparkContributions": list,
        "insights": list,
    },
    "contentDistribution": {
        "sparkPlatformSummaries": list,
        "insights": list,
    },
    "opportunities": {
        "topics": list,
        "insights": list,
    },
    "profile": {
        "platformAccounts": list,
        "insights": list,
    },
}


class ViewModelContractError(AssertionError):
    """Raised when a ViewModel does not satisfy the MVP API contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ViewModelContractError(message)


def validate_insight_shape(insight: dict[str, Any], context: str) -> None:
    for field in ["insightId", "creatorId", "type", "scope", "targetId", "title", "summary", "priority", "generatedBy", "pageTargets"]:
        require(field in insight, f"{context} insight missing {field}")
    require(isinstance(insight.get("evidenceMetrics"), list), f"{context} insight evidenceMetrics must be a list")
    require(isinstance(insight.get("recommendedActions"), list), f"{context} insight recommendedActions must be a list")
    require(len(insight["evidenceMetrics"]) >= 2, f"{context} insight needs at least 2 evidence metrics")
    require(len(insight["recommendedActions"]) >= 1, f"{context} insight needs at least 1 recommended action")


def validate_view_model(name: str, view_model: dict[str, Any]) -> None:
    require(name in VIEW_MODEL_REQUIRED_FIELDS, f"Unknown ViewModel: {name}")
    require(isinstance(view_model, dict), f"{name} must be an object")

    for field, expected_type in VIEW_MODEL_REQUIRED_FIELDS[name].items():
        require(field in view_model, f"{name} missing field: {field}")
        require(isinstance(view_model[field], expected_type), f"{name}.{field} must be {expected_type.__name__}")

    for insight in view_model.get("insights", []):
        validate_insight_shape(insight, name)

    if name == "growthDashboard":
        require("totalFollowers" in view_model["currentSnapshot"], "growthDashboard.currentSnapshot missing totalFollowers")
        waiting_for_events = view_model["currentSnapshot"].get("dataStatus") == "WAITING_FOR_EVENTS"
        if not waiting_for_events:
            require(view_model["topVideos"], "growthDashboard.topVideos cannot be empty")

    if name == "fansAnalysis":
        require(view_model["trend"], "fansAnalysis.trend cannot be empty")
        require("highValueSegments" in view_model["audienceProfile"], "fansAnalysis.audienceProfile missing highValueSegments")

    if name == "videoAnalysis":
        require(view_model["videos"], "videoAnalysis.videos cannot be empty")

    if name == "contentDistribution":
        require(isinstance(view_model["sparkPlatformSummaries"], list), "contentDistribution.sparkPlatformSummaries must be a list")

    if name == "opportunities":
        require(view_model["topics"], "opportunities.topics cannot be empty")

    if name == "profile":
        require(view_model["platformAccounts"], "profile.platformAccounts cannot be empty")


def validate_view_models(view_models: dict[str, Any]) -> None:
    require(set(view_models) == set(VIEW_MODEL_REQUIRED_FIELDS), "ViewModel key set does not match contract")
    for name, view_model in view_models.items():
        validate_view_model(name, view_model)


def validate_api_payload(payload: dict[str, Any], expected_view_model: str) -> None:
    require("meta" in payload, "API payload missing meta")
    require("creator" in payload, "API payload missing creator")
    require("data" in payload, "API payload missing data")
    require(payload["meta"].get("schemaVersion") == "mvp-1", "API payload schemaVersion must be mvp-1")
    require(payload["creator"].get("creatorId"), "API payload creatorId cannot be empty")
    validate_view_model(expected_view_model, payload["data"])
