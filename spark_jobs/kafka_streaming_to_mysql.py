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
from urllib.parse import urlparse


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT_DIR / ".env"
ALLOWED_OUTPUT_MODES = {"append", "update"}
STREAMING_SOURCE_TOPIC = "video_stats_topic"
MAIN_TABLE_PRIMARY_KEYS = {
    "video_metric_snapshots": ["snapshot_id"],
    "video_traffic_source_metrics": ["video_id", "source"],
    "creator_metric_snapshots": ["snapshot_id", "creator_id", "metric_date"],
}
STREAMING_STEPS = [
    "read video_stats_topic from Kafka",
    "parse video_stats event schema",
    "aggregate platform metric summaries",
    "rank video follower contributions",
    "upsert video metric snapshots",
    "upsert video traffic source metrics",
    "upsert creator metric snapshots",
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
                {"name": "interaction_rate", "type": "double", "nullable": True, "metadata": {}},
                {"name": "completion_rate", "type": "double", "nullable": True, "metadata": {}},
                {"name": "average_watch_seconds", "type": "integer", "nullable": True, "metadata": {}},
            ],
        }, "nullable": False, "metadata": {}},
        {"name": "growth", "type": {
            "type": "struct",
            "fields": [
                {"name": "play_growth_5s", "type": "long", "nullable": True, "metadata": {}},
                {"name": "new_followers", "type": "long", "nullable": False, "metadata": {}},
                {"name": "profile_visits", "type": "long", "nullable": False, "metadata": {}},
            ],
        }, "nullable": False, "metadata": {}},
        {"name": "traffic_source", "type": {
            "type": "map",
            "keyType": "string",
            "valueType": {
                "type": "struct",
                "fields": [
                    {"name": "views", "type": "long", "nullable": False, "metadata": {}},
                    {"name": "view_ratio", "type": "double", "nullable": True, "metadata": {}},
                    {"name": "new_followers", "type": "long", "nullable": False, "metadata": {}},
                    {"name": "conversion_rate", "type": "double", "nullable": True, "metadata": {}},
                    {"name": "save_rate", "type": "double", "nullable": True, "metadata": {}},
                    {"name": "comment_rate", "type": "double", "nullable": True, "metadata": {}},
                ],
            },
            "valueContainsNull": False,
        }, "nullable": True, "metadata": {}},
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
    video_metric_table: str = "video_metric_snapshots"
    traffic_source_table: str = "video_traffic_source_metrics"
    creator_metric_table: str = "creator_metric_snapshots"


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


def parse_mysql_jdbc_url(jdbc_url: str) -> dict[str, Any]:
    if not jdbc_url.startswith("jdbc:mysql://"):
        raise RuntimeError("SPARK_MYSQL_JDBC_URL must start with jdbc:mysql://")
    parsed = urlparse(jdbc_url.replace("jdbc:mysql://", "mysql://", 1))
    if not parsed.hostname or not parsed.path.strip("/"):
        raise RuntimeError("SPARK_MYSQL_JDBC_URL must include host and database")
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "database": parsed.path.strip("/"),
    }


def build_upsert_sql(table: str, columns: list[str], primary_keys: list[str]) -> str:
    column_sql = ", ".join(f"`{column}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    update_columns = [column for column in columns if column not in primary_keys]
    update_sql = ", ".join(f"`{column}` = VALUES(`{column}`)" for column in update_columns)
    return f"INSERT INTO `{table}` ({column_sql}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_sql}"


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
        "targetTables": [
            config.platform_table,
            config.contribution_table,
            config.video_metric_table,
            config.traffic_source_table,
            config.creator_metric_table,
        ],
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
            "videoMetricTable": config.video_metric_table,
            "trafficSourceTable": config.traffic_source_table,
            "creatorMetricTable": config.creator_metric_table,
            "writeMode": config.write_mode,
        },
        "executionPlan": build_execution_plan(config, execute=False),
        "schemaFields": [field["name"] for field in VIDEO_STATS_SCHEMA_JSON["fields"]],
    }


def run_streaming_job(config: StreamingConfig, jdbc: dict[str, str]) -> None:
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql.functions import (
            col,
            concat,
            count,
            current_date,
            current_timestamp,
            date_format,
            desc,
            explode,
            from_json,
            lit,
            lower,
            regexp_replace,
            row_number,
            sum as spark_sum,
            when,
        )
        from pyspark.sql.types import StructType
        from pyspark.sql.window import Window
    except ImportError as exc:
        raise RuntimeError("PySpark is not installed or this script is not running under spark-submit") from exc

    spark = SparkSession.builder.appName("CreatorPulseKafkaStreamingToMySQL").getOrCreate()
    schema = StructType.fromJson(VIDEO_STATS_SCHEMA_JSON)

    def jdbc_write(dataframe, table: str, mode: str) -> None:
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

    def mysql_upsert(dataframe, table: str) -> None:
        columns = dataframe.columns
        sql = build_upsert_sql(table, columns, MAIN_TABLE_PRIMARY_KEYS[table])
        mysql_target = parse_mysql_jdbc_url(jdbc["SPARK_MYSQL_JDBC_URL"])
        user = jdbc["SPARK_MYSQL_USER"]
        password = jdbc["SPARK_MYSQL_PASSWORD"]

        def write_partition(rows) -> None:
            batch = [tuple(row[column] for column in columns) for row in rows]
            if not batch:
                return
            import pymysql

            connection = pymysql.connect(
                host=mysql_target["host"],
                port=mysql_target["port"],
                user=user,
                password=password,
                database=mysql_target["database"],
                charset="utf8mb4",
                autocommit=False,
            )
            try:
                with connection.cursor() as cursor:
                    cursor.executemany(sql, batch)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

        dataframe.foreachPartition(write_partition)

    def write_jdbc(batch_df, batch_id: int) -> None:
        if batch_df.rdd.isEmpty():
            return

        calculated_at = current_timestamp()
        metric_date = current_date()
        run_id = lit(f"{config.run_prefix}_batch_{batch_id}")
        by_creator_video = Window.partitionBy("creator_id", "content_id").orderBy(desc("fetch_time"), desc("event_id"))
        latest_df = batch_df.withColumn("rn", row_number().over(by_creator_video)).filter(col("rn") == 1).drop("rn")

        platform_df = (
            latest_df.groupBy("creator_id", "platform")
            .agg(
                spark_sum("views").alias("total_views"),
                spark_sum("new_followers").alias("new_followers"),
                count("*").alias("video_count"),
            )
            .withColumn("run_id", run_id)
            .withColumn("conversion_rate", col("new_followers") / col("total_views"))
            .withColumn("calculated_at", calculated_at)
            .select("run_id", "creator_id", "platform", "total_views", "new_followers", "video_count", "conversion_rate", "calculated_at")
        )

        ranked_df = (
            latest_df.withColumn("rank_position", row_number().over(Window.partitionBy("creator_id").orderBy(desc("new_followers"))))
            .filter(col("rank_position") <= 10)
            .withColumn("run_id", run_id)
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

        video_metric_df = (
            latest_df.withColumn(
                "snapshot_id",
                regexp_replace(concat(lit("vms_"), col("creator_id"), lit("_"), col("content_id"), lit("_"), date_format(calculated_at, "yyyyMMddHHmmss")), "[^A-Za-z0-9_]", "_"),
            )
            .withColumn("completion_rate", col("completion_rate").cast("double"))
            .withColumn("average_watch_seconds", col("average_watch_seconds").cast("integer"))
            .withColumn("engagement_rate", (col("likes") + col("comments") + col("shares") + col("saves")) / col("views"))
            .withColumn("conversion_rate", col("new_followers") / col("views"))
            .withColumn("comment_rate", col("comments") / col("views"))
            .withColumn("save_rate", col("saves") / col("views"))
            .withColumn("share_rate", col("shares") / col("views"))
            .withColumn("collected_at", calculated_at)
            .select(
                "snapshot_id",
                col("content_id").alias("video_id"),
                "creator_id",
                "platform",
                "views",
                "likes",
                "comments",
                "shares",
                "saves",
                "profile_visits",
                "new_followers",
                "completion_rate",
                "average_watch_seconds",
                "engagement_rate",
                "conversion_rate",
                "comment_rate",
                "save_rate",
                "share_rate",
                "collected_at",
            )
        )

        traffic_source_df = (
            latest_df.select("content_id", "views", "comments", "saves", explode("traffic_source").alias("source", "metrics"))
            .withColumn("source", when(lower(col("source")) == "recommendation", "recommend").when(lower(col("source")) == "following", "follow").otherwise(lower(col("source"))))
            .select(
                col("content_id").alias("video_id"),
                "source",
                col("metrics.views").alias("views"),
                col("metrics.new_followers").alias("new_followers"),
                when(col("metrics.conversion_rate").isNotNull(), col("metrics.conversion_rate")).otherwise(col("metrics.new_followers") / col("metrics.views")).alias("conversion_rate"),
                when(col("metrics.save_rate").isNotNull(), col("metrics.save_rate")).otherwise(col("saves") / col("views")).alias("save_rate"),
                when(col("metrics.comment_rate").isNotNull(), col("metrics.comment_rate")).otherwise(col("comments") / col("views")).alias("comment_rate"),
            )
        )

        creator_metric_df = (
            latest_df.groupBy("creator_id")
            .agg(
                spark_sum("views").alias("total_views"),
                spark_sum(col("likes") + col("comments") + col("shares") + col("saves")).alias("total_interactions"),
                spark_sum("profile_visits").alias("profile_visits"),
                spark_sum("new_followers").alias("new_followers"),
                spark_sum("play_delta").alias("play_delta"),
            )
            .withColumn("snapshot_id", regexp_replace(concat(lit("cms_"), col("creator_id"), lit("_"), date_format(metric_date, "yyyyMMdd")), "[^A-Za-z0-9_]", "_"))
            .withColumn("metric_date", metric_date)
            .withColumn("lost_followers", lit(0))
            .withColumn("net_followers", col("new_followers") - col("lost_followers"))
            .withColumn("total_followers", col("new_followers"))
            .withColumn("follower_growth_rate", lit(0.0))
            .withColumn("view_to_follower_rate", col("new_followers") / col("play_delta"))
            .withColumn("stickiness_score", when(((col("total_interactions") / col("total_views")) * 420) > 100, 100).otherwise((col("total_interactions") / col("total_views")) * 420))
            .withColumn(
                "growth_health_score",
                when(
                    ((col("view_to_follower_rate") * 7200) + ((col("new_followers") / col("profile_visits")) * 120) + (col("stickiness_score") * 0.35)) > 100,
                    100,
                ).otherwise((col("view_to_follower_rate") * 7200) + ((col("new_followers") / col("profile_visits")) * 120) + (col("stickiness_score") * 0.35)),
            )
            .select(
                "snapshot_id",
                "creator_id",
                "metric_date",
                "total_followers",
                "new_followers",
                "lost_followers",
                "net_followers",
                "total_views",
                "total_interactions",
                "profile_visits",
                "follower_growth_rate",
                "view_to_follower_rate",
                "stickiness_score",
                "growth_health_score",
            )
        )

        jdbc_write(platform_df, config.platform_table, config.write_mode)
        jdbc_write(ranked_df, config.contribution_table, config.write_mode)
        mysql_upsert(video_metric_df, config.video_metric_table)
        mysql_upsert(traffic_source_df, config.traffic_source_table)
        mysql_upsert(creator_metric_df, config.creator_metric_table)

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
                "event_id",
                "fetch_time",
                "content_id",
                "title",
                col("stats.play_count").alias("views"),
                col("stats.like_count").alias("likes"),
                col("stats.comment_count").alias("comments"),
                col("stats.share_count").alias("shares"),
                col("stats.save_count").alias("saves"),
                col("stats.completion_rate").alias("completion_rate"),
                col("stats.average_watch_seconds").alias("average_watch_seconds"),
                col("growth.new_followers").alias("new_followers"),
                col("growth.profile_visits").alias("profile_visits"),
                when(col("growth.play_growth_5s").isNotNull() & (col("growth.play_growth_5s") > 0), col("growth.play_growth_5s")).otherwise(col("stats.play_count")).alias("play_delta"),
                "traffic_source",
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
