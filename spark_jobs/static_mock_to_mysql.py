"""Spark JDBC smoke job for CreatorPulse MVP.

This job intentionally reads static mock JSON instead of Kafka. Its purpose is
to prove the Spark -> MySQL JDBC path before adding streaming complexity.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json"
DEFAULT_ENV_PATH = ROOT_DIR / ".env"
PLACEHOLDER_VALUES = {"your_user", "your_password"}
ALLOWED_WRITE_MODES = {"append"}
SPARK_RESULT_TABLES = ["spark_platform_metric_summaries", "spark_video_follower_contributions"]
SPARK_JDBC_STEPS = [
    "require Spark JDBC config",
    "calculate platform metric summaries",
    "calculate video follower contributions",
    "write Spark result tables through JDBC",
]


def pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def load_env_file(path: Path = DEFAULT_ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_mock(path: Path = DEFAULT_DATA_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def calculate_platform_summaries(data: dict[str, Any], run_id: str, calculated_at: str) -> list[dict[str, Any]]:
    by_platform: dict[str, list[dict[str, Any]]] = {}
    for snapshot in data["videoMetricSnapshots"]:
        by_platform.setdefault(snapshot["platform"], []).append(snapshot)

    rows = []
    for platform, snapshots in sorted(by_platform.items()):
        total_views = sum(item["views"] for item in snapshots)
        new_followers = sum(item["newFollowers"] for item in snapshots)
        rows.append(
            {
                "run_id": run_id,
                "creator_id": data["creator"]["creatorId"],
                "platform": platform,
                "total_views": total_views,
                "new_followers": new_followers,
                "video_count": len(snapshots),
                "conversion_rate": pct(new_followers, total_views),
                "calculated_at": calculated_at,
            }
        )
    return rows


def calculate_video_contributions(
    data: dict[str, Any],
    run_id: str,
    calculated_at: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    videos_by_id = {item["videoId"]: item for item in data["videos"]}
    ranked = sorted(data["videoMetricSnapshots"], key=lambda item: item["newFollowers"], reverse=True)[:limit]

    rows = []
    for position, snapshot in enumerate(ranked, start=1):
        video = videos_by_id[snapshot["videoId"]]
        rows.append(
            {
                "run_id": run_id,
                "rank_position": position,
                "creator_id": snapshot["creatorId"],
                "video_id": snapshot["videoId"],
                "platform": snapshot["platform"],
                "title": video["title"],
                "views": snapshot["views"],
                "new_followers": snapshot["newFollowers"],
                "conversion_rate": snapshot["conversionRate"],
                "calculated_at": calculated_at,
            }
        )
    return rows


def require_jdbc_config() -> dict[str, str]:
    required = ["SPARK_MYSQL_JDBC_URL", "SPARK_MYSQL_USER", "SPARK_MYSQL_PASSWORD", "SPARK_MYSQL_DRIVER"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError(f"Missing Spark JDBC environment variables: {', '.join(missing)}")

    config = {key: os.environ[key] for key in required}
    issues = []
    if config["SPARK_MYSQL_USER"] in PLACEHOLDER_VALUES:
        issues.append("SPARK_MYSQL_USER is still a placeholder")
    if config["SPARK_MYSQL_PASSWORD"] in PLACEHOLDER_VALUES:
        issues.append("SPARK_MYSQL_PASSWORD is still a placeholder")
    if not config["SPARK_MYSQL_JDBC_URL"].startswith("jdbc:mysql://"):
        issues.append("SPARK_MYSQL_JDBC_URL must start with jdbc:mysql://")
    if config["SPARK_MYSQL_DRIVER"] not in {"com.mysql.cj.jdbc.Driver", "com.mysql.jdbc.Driver"}:
        issues.append("SPARK_MYSQL_DRIVER must be a MySQL Connector/J driver")

    write_mode = os.environ.get("SPARK_MYSQL_WRITE_MODE", "append")
    if write_mode not in ALLOWED_WRITE_MODES:
        issues.append("SPARK_MYSQL_WRITE_MODE write mode must be append")
    config["SPARK_MYSQL_WRITE_MODE"] = write_mode

    if issues:
        raise RuntimeError(f"Spark JDBC config failed: {'; '.join(issues)}")

    return config


def build_execution_plan(execute: bool, counts: dict[str, int], write_mode: str) -> dict[str, Any]:
    return {
        "willWriteMySQL": execute,
        "requiresExecuteFlag": True,
        "writeMode": write_mode,
        "steps": SPARK_JDBC_STEPS,
        "targetTables": SPARK_RESULT_TABLES,
        "plannedRows": counts,
    }


def write_rows_with_spark(rows: list[dict[str, Any]], table: str, jdbc: dict[str, str], mode: str) -> None:
    try:
        from pyspark.sql import SparkSession
    except ImportError as exc:
        raise RuntimeError("PySpark is not installed or this script is not running under spark-submit") from exc

    spark = SparkSession.builder.appName("CreatorPulseStaticMockToMySQL").getOrCreate()
    try:
        dataframe = spark.createDataFrame(rows)
        (
            dataframe.write.format("jdbc")
            .option("url", jdbc["SPARK_MYSQL_JDBC_URL"])
            .option("dbtable", table)
            .option("user", jdbc["SPARK_MYSQL_USER"])
            .option("password", jdbc["SPARK_MYSQL_PASSWORD"])
            .option("driver", jdbc["SPARK_MYSQL_DRIVER"])
            .mode(mode)
            .save()
        )
    finally:
        spark.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute MVP Spark summaries and optionally write MySQL through JDBC")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--run-id", default="spark_static_mock_001")
    parser.add_argument("--execute", action="store_true", help="Write results to MySQL through Spark JDBC")
    args = parser.parse_args()

    load_env_file(args.env_file)
    data = load_mock(args.data)
    calculated_at = datetime.now(UTC).replace(microsecond=0, tzinfo=None).isoformat()
    platform_rows = calculate_platform_summaries(data, args.run_id, calculated_at)
    contribution_rows = calculate_video_contributions(data, args.run_id, calculated_at)

    try:
        if args.execute:
            jdbc = require_jdbc_config()
            mode = jdbc["SPARK_MYSQL_WRITE_MODE"]
            write_rows_with_spark(platform_rows, "spark_platform_metric_summaries", jdbc, mode)
            write_rows_with_spark(contribution_rows, "spark_video_follower_contributions", jdbc, mode)
            status = "spark-jdbc-write"
        else:
            status = "dry-run"

        counts = {
            "spark_platform_metric_summaries": len(platform_rows),
            "spark_video_follower_contributions": len(contribution_rows),
        }
        print(
            json.dumps(
                {
                    "status": "ok",
                    "mode": status,
                    "counts": counts,
                    "executionPlan": build_execution_plan(args.execute, counts, os.environ.get("SPARK_MYSQL_WRITE_MODE", "append")),
                    "sample": {
                        "platform": platform_rows[0] if platform_rows else None,
                        "videoContribution": contribution_rows[0] if contribution_rows else None,
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    except Exception as exc:  # noqa: BLE001 - CLI returns structured Spark setup failures.
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
