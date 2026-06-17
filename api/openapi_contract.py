"""OpenAPI contract for the CreatorPulse MVP Flask API."""

from __future__ import annotations

from typing import Any


PAGE_ENDPOINTS = {
    "/api/me/dashboard/growth": "growthDashboard",
    "/api/me/fans": "fansAnalysis",
    "/api/me/videos": "videoAnalysis",
    "/api/me/distribution": "contentDistribution",
    "/api/me/opportunities": "opportunities",
    "/api/me/profile": "profile",
}

LEGACY_CREATOR_PAGE_ENDPOINTS = {
    "/api/creators/{creatorId}/dashboard/growth": "growthDashboard",
    "/api/creators/{creatorId}/fans": "fansAnalysis",
    "/api/creators/{creatorId}/videos": "videoAnalysis",
    "/api/creators/{creatorId}/distribution": "contentDistribution",
    "/api/creators/{creatorId}/opportunities": "opportunities",
    "/api/creators/{creatorId}/profile": "profile",
}


def openapi_schema() -> dict[str, Any]:
    paths: dict[str, Any] = {
        "/api/health": {
            "get": {
                "summary": "MVP API health and data counts",
                "operationId": "getHealth",
                "responses": {
                    "200": {
                        "description": "Health summary",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/HealthResponse"}}},
                    }
                },
            }
        },
        "/api/auth/login": {
            "post": {
                "summary": "Log in with an account bound to one creator",
                "operationId": "login",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/LoginRequest"}}},
                },
                "responses": {
                    "200": {
                        "description": "Authenticated user and creator mapping",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/AuthUserResponse"}}},
                    },
                    "400": {
                        "description": "Missing email or password",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
                    },
                    "401": {
                        "description": "Invalid email or password",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
                    },
                },
            }
        },
        "/api/auth/logout": {
            "post": {
                "summary": "Clear the current session",
                "operationId": "logout",
                "responses": {
                    "200": {
                        "description": "Session cleared",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/StatusResponse"}}},
                    }
                },
            }
        },
        "/api/me": {
            "get": {
                "summary": "Get the current logged-in user and bound creator id",
                "operationId": "getMe",
                "responses": {
                    "200": {
                        "description": "Current user",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/AuthUserResponse"}}},
                    },
                    "401": {
                        "description": "Login required",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
                    },
                },
            }
        },
    }

    for path, view_model in PAGE_ENDPOINTS.items():
        paths[path] = page_endpoint_operation(
            view_model,
            summary=f"Get current creator {view_model} page ViewModel",
            operation_id=f"getMy{view_model[0].upper()}{view_model[1:]}",
            parameters=[],
            unauthorized=True,
        )

    for path, view_model in LEGACY_CREATOR_PAGE_ENDPOINTS.items():
        paths[path] = page_endpoint_operation(
            view_model,
            summary=f"Get {view_model} page ViewModel by creator id",
            operation_id=f"get{view_model[0].upper()}{view_model[1:]}ByCreatorId",
            parameters=[
                {
                    "name": "creatorId",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                    "description": "Internal/dev compatibility route. Frontend should use /api/me endpoints.",
                }
            ],
            deprecated=True,
        )

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "CreatorPulse MVP API",
            "version": "mvp-1",
            "description": "Stable Flask API contract for CreatorPulse login and session-scoped ViewModels.",
        },
        "paths": paths,
        "components": {"schemas": component_schemas()},
    }


def page_endpoint_operation(
    view_model: str,
    summary: str,
    operation_id: str,
    parameters: list[dict[str, Any]],
    unauthorized: bool = False,
    deprecated: bool = False,
) -> dict[str, Any]:
    responses: dict[str, Any] = {
        "200": {
            "description": "Page ViewModel payload",
            "content": {
                "application/json": {
                    "schema": {
                        "allOf": [
                            {"$ref": "#/components/schemas/PageResponseBase"},
                            {
                                "type": "object",
                                "properties": {"data": {"$ref": f"#/components/schemas/{view_model}"}},
                                "required": ["data"],
                            },
                        ]
                    }
                }
            },
        },
        "404": {
            "description": "Creator or ViewModel not found",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
        },
        "500": {
            "description": "Configured data source cannot satisfy the API contract",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
        },
    }
    if unauthorized:
        responses["401"] = {
            "description": "Login required",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
        }

    return {
        "get": {
            "summary": summary,
            "operationId": operation_id,
            "parameters": parameters,
            "deprecated": deprecated,
            "responses": responses,
        }
    }


def object_schema(required: list[str], properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": True,
        "required": required,
        "properties": properties or {},
    }


def component_schemas() -> dict[str, Any]:
    insight = object_schema(
        [
            "insightId",
            "creatorId",
            "type",
            "scope",
            "targetId",
            "title",
            "summary",
            "priority",
            "evidenceMetrics",
            "recommendedActions",
            "generatedBy",
            "pageTargets",
        ],
        {
            "insightId": {"type": "string"},
            "generatedBy": {"type": "string", "enum": ["RULE_ENGINE", "SPARK_RULE_ENGINE"]},
            "pageTargets": {"type": "array", "items": {"type": "string"}},
            "evidenceMetrics": {"type": "array", "items": {"type": "object"}},
            "recommendedActions": {"type": "array", "items": {"type": "object"}},
        },
    )
    return {
        "HealthResponse": object_schema(["status", "schemaVersion", "generatedAt", "counts"]),
        "ErrorResponse": object_schema(["error"]),
        "StatusResponse": object_schema(["status"], {"status": {"type": "string"}}),
        "LoginRequest": object_schema(
            ["email", "password"],
            {
                "email": {"type": "string", "format": "email"},
                "password": {"type": "string", "format": "password"},
            },
        ),
        "AuthUser": object_schema(
            ["userId", "creatorId", "email", "displayName", "role"],
            {
                "userId": {"type": "string"},
                "creatorId": {"type": "string"},
                "email": {"type": "string", "format": "email"},
                "displayName": {"type": "string"},
                "role": {"type": "string"},
            },
        ),
        "AuthUserResponse": object_schema(["user"], {"user": {"$ref": "#/components/schemas/AuthUser"}}),
        "Meta": object_schema(["schemaVersion", "generatedAt"]),
        "Creator": object_schema(["creatorId", "displayName", "nicheTags", "timezone"]),
        "Insight": insight,
        "PageResponseBase": object_schema(
            ["meta", "creator", "data"],
            {
                "meta": {"$ref": "#/components/schemas/Meta"},
                "creator": {"$ref": "#/components/schemas/Creator"},
            },
        ),
        "growthDashboard": object_schema(
            ["currentSnapshot", "topVideos", "insights"],
            {
                "currentSnapshot": {"type": "object"},
                "topVideos": {"type": "array", "items": {"type": "object"}},
                "insights": {"type": "array", "items": {"$ref": "#/components/schemas/Insight"}},
            },
        ),
        "fansAnalysis": object_schema(
            ["trend", "audienceProfile", "insights"],
            {
                "trend": {"type": "array", "items": {"type": "object"}},
                "audienceProfile": {"type": "object"},
                "insights": {"type": "array", "items": {"$ref": "#/components/schemas/Insight"}},
            },
        ),
        "videoAnalysis": object_schema(
            ["videos", "snapshots", "topVideos", "sparkContributions", "insights"],
            {
                "videos": {"type": "array", "items": {"type": "object"}},
                "snapshots": {"type": "array", "items": {"type": "object"}},
                "topVideos": {"type": "array", "items": {"type": "object"}},
                "sparkContributions": {"type": "array", "items": {"type": "object"}},
                "insights": {"type": "array", "items": {"$ref": "#/components/schemas/Insight"}},
            },
        ),
        "contentDistribution": object_schema(
            ["sparkPlatformSummaries", "insights"],
            {
                "sparkPlatformSummaries": {"type": "array", "items": {"type": "object"}},
                "insights": {"type": "array", "items": {"$ref": "#/components/schemas/Insight"}},
            },
        ),
        "opportunities": object_schema(
            ["topics", "insights"],
            {
                "topics": {"type": "array", "items": {"type": "object"}},
                "insights": {"type": "array", "items": {"$ref": "#/components/schemas/Insight"}},
            },
        ),
        "profile": object_schema(
            ["platformAccounts", "insights"],
            {
                "platformAccounts": {"type": "array", "items": {"type": "object"}},
                "insights": {"type": "array", "items": {"$ref": "#/components/schemas/Insight"}},
            },
        ),
    }
