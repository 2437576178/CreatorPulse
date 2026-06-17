"""Spark Structured Streaming job: Kafka -> aggregate -> MySQL.

Default mode is dry-run and validates configuration plus the intended sink
tables. Use --execute only after Kafka VM connectivity and MySQL JDBC are both
confirmed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT_DIR / ".env"
ALLOWED_OUTPUT_MODES = {"append", "update"}
STREAMING_SOURCE_TOPIC = "video_stats_topic"
STREAMING_STEPS = [
    "read video_stats_topic from Kafka",
    "parse video_stats event schema",
    "aggregate platform metric summaries",
    "rank video follower contributions",
    "write Spark result tables through JDBC foreachBatch",
]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from kafka_tools.check_connectivity import check_bootstrap_config, load_env_file
    from .static_mock_to_mysql import require_jdbc_config
except ImportError:
    from kafka_tools.check_connectivity import check_bootstrap_config, load_env_file
    from static_mock_to_mysql import require_jdbc_config


VIDEO_STATS_SCHEMA_JSON = {
    "type": "struct",
    "fields": [
        {"name": "event_id", "type": "string", "nullable": False, "metadata": {}},
        {"name": "event_type", "type": "string", "nullable": False, "metadata": {}},
        {"name": "platform", "type": "string", "nullable": False, "metadata": {}},
        {"name": "fetch_time", "type": "string", "nullable": False, "metadata": {}},
        {"name": "creator_id", "type": "string", "nullable": False, "metadata": {}},
        {"name": "content_id", "type": "string", "nullable": False, "metadata": {}},
        {"name": "title", "type": "string", "nullable": True, "metadata": {}},
        {"name": "stats", "type": {
            "type": "struct",
            "fields": [
                {"name": "play_count", "type": "long", "nullable": False, "metadata": {}},
                {"name": "like_count", "type": "long", "nullable": False, "metadata": {}},
                {"name": "comment_count", "type": "long", "nullable": False, "metadata": {}},
                {"name": "share_count", "type": "long", "nullable": False, "metadata": {}},
                {"name": "save_count", "type": "long", "nullable": False, "metadata": {}},
            ],
        }, "nullable": False, "metadata": {}},
        {"name": "growth", "type": {
            "type": "struct",
            "fields": [
                {"name": "new_followers", "type": "long", "nullable": False, "metadata": {}},
                {"name": "profile_visits", "type": "long", "nullable": False, "metadata": {}},
            ],
        }, "nullable": False, "metadata": {}},
    ],
}


@dataclass(frozen=True)
class StreamingConfig:
    bootstrap_servers: str
    checkpoint_dir: str
    trigger_seconds: int
    output_mode: str
    write_mode: str
    run_prefix: str
    platform_table: str = "spark_platform_metric_summaries"
    contribution_table: str = "spark_video_follower_contributions"


def load_streaming_config() -> StreamingConfig:
    bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "").strip()
    if not bootstrap_servers:
        raise RuntimeError("KAFKA_BOOTSTRAP_SERVERS is required for streaming")

    trigger_seconds = int(os.environ.get("SPARK_STREAM_TRIGGER_SECONDS", "30"))
    if trigger_seconds <= 0:
        raise RuntimeError("SPARK_STREAM_TRIGGER_SECONDS must be greater than 0")

    return StreamingConfig(
        bootstrap_servers=bootstrap_servers,
        checkpoint_dir=os.environ.get("SPARK_STREAM_CHECKPOINT_DIR", str(ROOT_DIR / "spark_jobs" / "checkpoints")),
        trigger_seconds=trigger_seconds,
        output_mode=os.environ.get("SPARK_STREAM_OUTPUT_MODE", "update"),
        write_mode=os.environ.get("SPARK_MYSQL_WRITE_MODE", "append"),
        run_prefix=os.environ.get("SPARK_STREAM_RUN_PREFIX", datetime.now(UTC).strftime("kafka_stream_%Y%m%d_%H%M%S")),
    )


def require_streaming_config() -> StreamingConfig:
    config = load_streaming_config()
    issues = []

    bootstrap = check_bootstrap_config(config.bootstrap_servers)
    if bootstrap["status"] != "ok":
        issues.append(bootstrap["message"])

    if config.output_mode not in ALLOWED_OUTPUT_MODES:
        issues.append("SPARK_STREAM_OUTPUT_MODE output mode must be append or update")

    if issues:
        raise RuntimeError(f"Spark streaming config failed: {'; '.join(issues)}")

    return config


def require_full_pipeline_live_flag() -> None:
    if os.environ.get("CREATORPULSE_RUN_FULL_PIPELINE_LIVE") != "1":
        raise RuntimeError("Set CREATORPULSE_RUN_FULL_PIPELINE_LIVE=1 before --execute to allow Kafka -> Spark -> MySQL streaming writes")


def build_execution_plan(config: StreamingConfig, execute: bool) -> dict:
    return {
        "willStartStreaming": execute,
        "requiresExecuteFlag": True,
        "requiresFullPipelineLiveFlag": True,
        "sourceTopic": STREAMING_SOURCE_TOPIC,
        "triggerSeconds": config.trigger_seconds,
        "checkpointDir": config.checkpoint_dir,
        "runPrefix": config.run_prefix,
        "outputMode": config.output_mode,
        "writeMode": config.write_mode,
        "targetTables": [config.platform_table, config.contribution_table],
        "steps": STREAMING_STEPS,
    }


def dry_run_summary(config: StreamingConfig, jdbc: dict[str, str] | None = None) -> dict:
    return {
        "status": "ok",
        "mode": "dry-run",
        "kafka": {
            "bootstrapServers": config.bootstrap_servers,
            "topic": STREAMING_SOURCE_TOPIC,
            "triggerSeconds": config.trigger_seconds,
            "checkpointDir": config.checkpoint_dir,
            "runPrefix": config.run_prefix,
        },
        "mysql": {
            "jdbcConfigured": bool(jdbc),
            "platformTable": config.platform_table,
            "contributionTable": config.contribution_table,
            "writeMode": config.write_mode,
        },
        "executionPlan": build_execution_plan(config, execute=False),
        "schemaFields": [field["name"] for field in VIDEO_STATS_SCHEMA_JSON["fields"]],
    }


def run_streaming_job(config: StreamingConfig, jdbc: dict[str, str]) -> None:
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql.functions import col, count, current_timestamp, desc, from_json, lit, row_number, sum as spark_sum
        from pyspark.sql.types import StructType
        from pyspark.sql.window import Window
    except ImportError as exc:
        raise RuntimeError("PySpark is not installed or this script is not running under spark-submit") from exc

    spark = SparkSession.builder.appName("CreatorPulseKafkaStreamingToMySQL").getOrCreate()
    schema = StructType.fromJson(VIDEO_STATS_SCHEMA_JSON)

    def write_jdbc(batch_df, batch_id: int) -> None:
        if batch_df.rdd.isEmpty():
            return

        calculated_at = current_timestamp()
        platform_df = (
            batch_df.groupBy("creator_id", "platform")
            .agg(
                spark_sum("views").alias("total_views"),
                spark_sum("new_followers").alias("new_followers"),
                count("*").alias("video_count"),
            )
            .withColumn("run_id", lit(f"{config.run_prefix}_batch_{batch_id}"))
            .withColumn("conversion_rate", col("new_followers") / col("total_views"))
            .withColumn("calculated_at", calculated_at)
            .select("run_id", "creator_id", "platform", "total_views", "new_followers", "video_count", "conversion_rate", "calculated_at")
        )

        ranked_df = (
            batch_df.withColumn("rank_position", row_number().over(Window.orderBy(desc("new_followers"))))
            .filter(col("rank_position") <= 10)
            .withColumn("run_id", lit(f"{config.run_prefix}_batch_{batch_id}"))
            .withColumn("conversion_rate", col("new_followers") / col("views"))
            .withColumn("calculated_at", calculated_at)
            .select(
                "run_id",
                "rank_position",
                "creator_id",
                col("content_id").alias("video_id"),
                "platform",
                "title",
                "views",
                "new_followers",
                "conversion_rate",
                "calculated_at",
            )
        )

        for dataframe, table in [(platform_df, config.platform_table), (ranked_df, config.contribution_table)]:
            (
                dataframe.write.format("jdbc")
                .option("url", jdbc["SPARK_MYSQL_JDBC_URL"])
                .option("dbtable", table)
                .option("user", jdbc["SPARK_MYSQL_USER"])
                .option("password", jdbc["SPARK_MYSQL_PASSWORD"])
                .option("driver", jdbc["SPARK_MYSQL_DRIVER"])
                .mode(config.write_mode)
                .save()
            )

    try:
        kafka_df = (
            spark.readStream.format("kafka")
            .option("kafka.bootstrap.servers", config.bootstrap_servers)
            .option("subscribe", STREAMING_SOURCE_TOPIC)
            .option("startingOffsets", "latest")
            .load()
        )
        parsed_df = (
            kafka_df.select(from_json(col("value").cast("string"), schema).alias("event"))
            .select("event.*")
            .filter(col("event_type") == "video_stats")
            .select(
                "creator_id",
                "platform",
                "content_id",
                "title",
                col("stats.play_count").alias("views"),
                col("growth.new_followers").alias("new_followers"),
            )
        )
        query = (
            parsed_df.writeStream.foreachBatch(write_jdbc)
            .outputMode(config.output_mode)
            .option("checkpointLocation", config.checkpoint_dir)
            .trigger(processingTime=f"{config.trigger_seconds} seconds")
            .start()
        )
        query.awaitTermination()
    finally:
        spark.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Kafka -> Spark Structured Streaming -> MySQL job")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--execute", action="store_true", help="Actually start Spark Structured Streaming")
    args = parser.parse_args()

    load_env_file(args.env_file)

    try:
        config = require_streaming_config() if args.execute else load_streaming_config()
        jdbc = require_jdbc_config() if args.execute else None

        if args.execute:
            require_full_pipeline_live_flag()
            run_streaming_job(config, jdbc or {})
        else:
            print(json.dumps(dry_run_summary(config, jdbc), ensure_ascii=False, indent=2))
    except Exception as exc:  # noqa: BLE001 - CLI returns structured streaming setup failures.
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
