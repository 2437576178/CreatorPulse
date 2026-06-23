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
        "/api/me/avatar": {
            "post": {
                "summary": "Upload avatar image for the current creator",
                "operationId": "uploadMyAvatar",
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["avatar"],
                                "properties": {
                                    "avatar": {
                                        "type": "string",
                                        "format": "binary",
                                    }
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Updated authenticated user",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/AuthUserResponse"}}},
                    },
                    "400": {
                        "description": "Invalid avatar file",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
                    },
                    "401": {
                        "description": "Login required",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
                    },
                },
            }
        },
        "/api/me/reports": {
            "get": {
                "summary": "List offline reports for the current creator",
                "operationId": "listMyReports",
                "parameters": [
                    {
                        "name": "type",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string", "enum": ["DAILY", "WEEKLY", "MONTHLY"]},
                    },
                    {"name": "page", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1}},
                    {"name": "pageSize", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1, "maximum": 100}},
                ],
                "responses": {
                    "200": {
                        "description": "Paginated current creator reports",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ReportListResponse"}}},
                    },
                    "401": {
                        "description": "Login required",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
                    },
                },
            }
        },
        "/api/me/reports/{reportId}": {
            "get": {
                "summary": "Get one offline report for the current creator",
                "operationId": "getMyReport",
                "parameters": [
                    {"name": "reportId", "in": "path", "required": True, "schema": {"type": "string"}},
                ],
                "responses": {
                    "200": {
                        "description": "Current creator report detail",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Report"}}},
                    },
                    "401": {
                        "description": "Login required",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
                    },
                    "404": {
                        "description": "Report not found",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
                    },
                },
            }
        },
        "/api/admin/offline/status": {
            "get": {
                "summary": "Get offline job status, recent batch runs, and recent reports",
                "operationId": "getAdminOfflineStatus",
                "responses": {
                    "200": {
                        "description": "Offline processing status",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/AdminOfflineStatus"}}},
                    }
                },
            }
        },
        "/api/admin/offline/recompute": {
            "post": {
                "summary": "Create a pending offline recompute request",
                "operationId": "createOfflineRecomputeRequest",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/RecomputeRequestCreate"}}},
                },
                "responses": {
                    "201": {
                        "description": "Pending recompute request",
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/RecomputeRequest"}}},
                    },
                    "400": {
                        "description": "Invalid recompute request",
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
            ["userId", "creatorId", "email", "displayName", "role", "avatarUrl"],
            {
                "userId": {"type": "string"},
                "creatorId": {"type": "string"},
                "email": {"type": "string", "format": "email"},
                "displayName": {"type": "string"},
                "role": {"type": "string"},
                "avatarUrl": {"type": "string"},
            },
        ),
        "AuthUserResponse": object_schema(["user"], {"user": {"$ref": "#/components/schemas/AuthUser"}}),
        "Report": object_schema(
            ["reportId", "creatorId", "reportType", "periodStart", "periodEnd", "status", "title", "summary", "highlights", "risks", "actions", "metrics", "generatedAt", "batchRunId"],
            {
                "reportId": {"type": "string"},
                "creatorId": {"type": "string"},
                "reportType": {"type": "string", "enum": ["DAILY", "WEEKLY", "MONTHLY"]},
                "periodStart": {"type": "string", "format": "date"},
                "periodEnd": {"type": "string", "format": "date"},
                "status": {"type": "string", "enum": ["GENERATED", "EMPTY", "FAILED"]},
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "highlights": {"type": "array", "items": {"type": "string"}},
                "risks": {"type": "array", "items": {"type": "string"}},
                "actions": {"type": "array", "items": {"type": "string"}},
                "metrics": {"type": "object", "additionalProperties": True},
                "generatedAt": {"type": "string"},
                "batchRunId": {"type": "string"},
            },
        ),
        "ReportListResponse": object_schema(
            ["items", "page", "pageSize", "total"],
            {
                "items": {"type": "array", "items": {"$ref": "#/components/schemas/Report"}},
                "page": {"type": "integer"},
                "pageSize": {"type": "integer"},
                "total": {"type": "integer"},
            },
        ),
        "AdminOfflineStatus": object_schema(
            ["dataSource", "rawEventCount", "creatorDailyCount", "reportCount", "pendingRecomputeCount", "recentRuns", "recentReports"],
            {
                "dataSource": {"type": "string"},
                "rawEventCount": {"type": "integer"},
                "creatorDailyCount": {"type": "integer"},
                "reportCount": {"type": "integer"},
                "pendingRecomputeCount": {"type": "integer"},
                "recentRuns": {"type": "array", "items": {"type": "object"}},
                "recentReports": {"type": "array", "items": {"$ref": "#/components/schemas/Report"}},
            },
        ),
        "RecomputeRequestCreate": object_schema(
            ["creatorId", "periodStart", "periodEnd"],
            {
                "creatorId": {"type": "string"},
                "periodStart": {"type": "string", "format": "date"},
                "periodEnd": {"type": "string", "format": "date"},
                "recomputeScope": {
                    "type": "string",
                    "enum": ["CREATOR_DAILY", "PLATFORM_DAILY", "VIDEO_DAILY", "CONTENT_TYPE_DAILY", "REPORTS", "ALL"],
                },
                "requestedBy": {"type": "string"},
            },
        ),
        "RecomputeRequest": object_schema(
            ["requestId", "creatorId", "periodStart", "periodEnd", "recomputeScope", "status", "requestedBy", "requestedAt"],
            {
                "requestId": {"type": "string"},
                "creatorId": {"type": "string"},
                "periodStart": {"type": "string", "format": "date"},
                "periodEnd": {"type": "string", "format": "date"},
                "recomputeScope": {"type": "string"},
                "status": {"type": "string"},
                "requestedBy": {"type": "string"},
                "requestedAt": {"type": "string"},
            },
        ),
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
            ["currentSnapshot", "newFollowers", "syncLatencySeconds", "topVideos", "contentTypeRows", "insights"],
            {
                "currentSnapshot": {"type": "object"},
                "newFollowers": {"type": "integer"},
                "syncLatencySeconds": {"type": "integer"},
                "topVideos": {"type": "array", "items": {"type": "object"}},
                "contentTypeRows": {"type": "array", "items": {"type": "object"}},
                "insights": {"type": "array", "items": {"$ref": "#/components/schemas/Insight"}},
            },
        ),
        "fansAnalysis": object_schema(
            ["trend", "newFollowers", "syncLatencySeconds", "audienceProfile", "insights"],
            {
                "trend": {"type": "array", "items": {"type": "object"}},
                "newFollowers": {"type": "integer"},
                "syncLatencySeconds": {"type": "integer"},
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
            ["sparkPlatformSummaries", "syncLatencySeconds", "insights"],
            {
                "sparkPlatformSummaries": {"type": "array", "items": {"type": "object"}},
                "syncLatencySeconds": {"type": "integer"},
                "insights": {"type": "array", "items": {"$ref": "#/components/schemas/Insight"}},
            },
        ),
        "opportunities": object_schema(
            ["topics", "syncLatencySeconds", "insights"],
            {
                "topics": {"type": "array", "items": {"type": "object"}},
                "syncLatencySeconds": {"type": "integer"},
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
