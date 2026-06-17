"""Structured MVP data quality audit for mock data and dry-run aggregates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.import_mock_to_mysql import load_json  # noqa: E402
from spark_jobs.static_mock_to_mysql import calculate_platform_summaries, calculate_video_contributions  # noqa: E402


TOLERANCE = 0.000001
REQUIRED_PAGE_PREFIXES = ["growth.", "fans.", "video.", "content.", "opportunities.", "profile."]


def pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def close_enough(actual: float, expected: float, tolerance: float = TOLERANCE) -> bool:
    return abs(actual - expected) <= tolerance


def max_rate_error(rows: list[tuple[float, float]]) -> float:
    if not rows:
        return 0.0
    return max(abs(actual - expected) for actual, expected in rows)


def audit_video_snapshot_formulas(data: dict[str, Any]) -> dict[str, Any]:
    failures = []
    errors: list[tuple[float, float]] = []
    video_ids = {item["videoId"] for item in data["videos"]}
    seen_video_ids = set()

    for row in data["videoMetricSnapshots"]:
        video_id = row["videoId"]
        seen_video_ids.add(video_id)
        if video_id not in video_ids:
            failures.append(f"{video_id}: unknown video")
            continue
        if not (row["newFollowers"] <= row["profileVisits"] <= row["views"]):
            failures.append(f"{video_id}: invalid conversion chain")
        interactions = row["likes"] + row["comments"] + row["shares"] + row["saves"]
        expected_rates = [
            (row["conversionRate"], pct(row["newFollowers"], row["views"])),
            (row["commentRate"], pct(row["comments"], row["views"])),
            (row["saveRate"], pct(row["saves"], row["views"])),
            (row["shareRate"], pct(row["shares"], row["views"])),
            (row["engagementRate"], pct(interactions, row["views"])),
        ]
        for actual, expected in expected_rates:
            errors.append((actual, expected))
            if not close_enough(actual, expected):
                failures.append(f"{video_id}: rate mismatch {actual} != {expected}")

    missing = sorted(video_ids - seen_video_ids)
    for video_id in missing:
        failures.append(f"{video_id}: missing snapshot")

    return {
        "status": "ok" if not failures else "failed",
        "checkedRows": len(data["videoMetricSnapshots"]),
        "maxRateError": max_rate_error(errors),
        "failures": failures,
    }


def audit_traffic_source_rollups(data: dict[str, Any]) -> dict[str, Any]:
    by_video: dict[str, list[dict[str, Any]]] = {}
    for row in data["videoTrafficSourceMetrics"]:
        by_video.setdefault(row["videoId"], []).append(row)

    failures = []
    rate_errors: list[tuple[float, float]] = []
    for snapshot in data["videoMetricSnapshots"]:
        video_id = snapshot["videoId"]
        rows = by_video.get(video_id, [])
        if len(rows) != 5:
            failures.append(f"{video_id}: expected 5 source rows, got {len(rows)}")
            continue
        views = sum(row["views"] for row in rows)
        followers = sum(row["newFollowers"] for row in rows)
        if views != snapshot["views"]:
            failures.append(f"{video_id}: source views {views} != snapshot views {snapshot['views']}")
        if followers != snapshot["newFollowers"]:
            failures.append(f"{video_id}: source followers {followers} != snapshot followers {snapshot['newFollowers']}")
        for row in rows:
            expected = pct(row["newFollowers"], row["views"])
            rate_errors.append((row["conversionRate"], expected))
            if not close_enough(row["conversionRate"], expected):
                failures.append(f"{video_id}:{row['source']}: conversion mismatch")

    return {
        "status": "ok" if not failures else "failed",
        "checkedVideos": len(data["videoMetricSnapshots"]),
        "sourceRows": len(data["videoTrafficSourceMetrics"]),
        "maxRateError": max_rate_error(rate_errors),
        "failures": failures,
    }


def audit_creator_trend_formulas(data: dict[str, Any]) -> dict[str, Any]:
    rows = data["creatorMetricSnapshots"]
    failures = []
    rate_errors: list[tuple[float, float]] = []
    if rows != sorted(rows, key=lambda item: item["date"]):
        failures.append("creatorMetricSnapshots are not sorted by date")

    for row in rows:
        if row["netFollowers"] != row["newFollowers"] - row["lostFollowers"]:
            failures.append(f"{row['date']}: netFollowers mismatch")
        previous_total = row["totalFollowers"] - row["netFollowers"]
        expected_growth = pct(row["netFollowers"], previous_total)
        expected_view_to_follower = pct(row["newFollowers"], row["totalViews"])
        for actual, expected in [
            (row["followerGrowthRate"], expected_growth),
            (row["viewToFollowerRate"], expected_view_to_follower),
        ]:
            rate_errors.append((actual, expected))
            if not close_enough(actual, expected):
                failures.append(f"{row['date']}: trend rate mismatch")

    return {
        "status": "ok" if not failures else "failed",
        "checkedRows": len(rows),
        "maxRateError": max_rate_error(rate_errors),
        "failures": failures,
    }


def audit_spark_rollup_parity(data: dict[str, Any]) -> dict[str, Any]:
    platform_rows = calculate_platform_summaries(data, "quality_audit", data["meta"]["generatedAt"])
    contribution_rows = calculate_video_contributions(data, "quality_audit", data["meta"]["generatedAt"])
    snapshot_total_views = sum(item["views"] for item in data["videoMetricSnapshots"])
    snapshot_followers = sum(item["newFollowers"] for item in data["videoMetricSnapshots"])
    spark_views = sum(item["total_views"] for item in platform_rows)
    spark_followers = sum(item["new_followers"] for item in platform_rows)

    failures = []
    if spark_views != snapshot_total_views:
        failures.append(f"spark total views {spark_views} != snapshot total views {snapshot_total_views}")
    if spark_followers != snapshot_followers:
        failures.append(f"spark followers {spark_followers} != snapshot followers {snapshot_followers}")
    if len(platform_rows) != 3:
        failures.append(f"expected 3 platform rows, got {len(platform_rows)}")
    if len(contribution_rows) != 10:
        failures.append(f"expected 10 contribution rows, got {len(contribution_rows)}")

    return {
        "status": "ok" if not failures else "failed",
        "platformRows": len(platform_rows),
        "contributionRows": len(contribution_rows),
        "totalViews": spark_views,
        "newFollowers": spark_followers,
        "failures": failures,
    }


def audit_insight_quality(data: dict[str, Any]) -> dict[str, Any]:
    missing_evidence = []
    missing_actions = []
    all_targets = set()
    for insight in data["insights"]:
        if len(insight.get("evidenceMetrics", [])) < 2:
            missing_evidence.append(insight["insightId"])
        if len(insight.get("recommendedActions", [])) < 1:
            missing_actions.append(insight["insightId"])
        all_targets.update(insight.get("pageTargets", []))

    missing_prefixes = [
        prefix
        for prefix in REQUIRED_PAGE_PREFIXES
        if not any(target.startswith(prefix) for target in all_targets)
    ]
    failures = missing_evidence + missing_actions + missing_prefixes
    return {
        "status": "ok" if not failures else "failed",
        "checkedInsights": len(data["insights"]),
        "insightsMissingEvidence": missing_evidence,
        "insightsMissingActions": missing_actions,
        "missingPagePrefixes": missing_prefixes,
    }


def build_quality_report() -> dict[str, Any]:
    data = load_json()
    checks = {
        "videoSnapshotFormulas": audit_video_snapshot_formulas(data),
        "trafficSourceRollups": audit_traffic_source_rollups(data),
        "creatorTrendFormulas": audit_creator_trend_formulas(data),
        "sparkRollupParity": audit_spark_rollup_parity(data),
        "insightQuality": audit_insight_quality(data),
    }
    failed = [name for name, result in checks.items() if result["status"] != "ok"]
    return {
        "status": "ok" if not failed else "failed",
        "summary": {
            "failedChecks": failed,
            "checkedVideos": len(data["videos"]),
            "checkedInsights": len(data["insights"]),
        },
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit CreatorPulse MVP mock data quality")
    parser.parse_args()

    report = build_quality_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
