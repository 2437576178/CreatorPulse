"""Python 3.6 compatible Spark Streaming job for the CentOS VM.

The local development job uses newer Python typing syntax. The VM currently
ships Python 3.6, so this file keeps the runtime path small and compatible.
"""

import os
from datetime import datetime


STREAMING_SOURCE_TOPIC = "video_stats_topic"


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
        {
            "name": "stats",
            "type": {
                "type": "struct",
                "fields": [
                    {"name": "play_count", "type": "long", "nullable": False, "metadata": {}},
                    {"name": "like_count", "type": "long", "nullable": False, "metadata": {}},
                    {"name": "comment_count", "type": "long", "nullable": False, "metadata": {}},
                    {"name": "share_count", "type": "long", "nullable": False, "metadata": {}},
                    {"name": "save_count", "type": "long", "nullable": False, "metadata": {}},
                ],
            },
            "nullable": False,
            "metadata": {},
        },
        {
            "name": "growth",
            "type": {
                "type": "struct",
                "fields": [
                    {"name": "new_followers", "type": "long", "nullable": False, "metadata": {}},
                    {"name": "profile_visits", "type": "long", "nullable": False, "metadata": {}},
                ],
            },
            "nullable": False,
            "metadata": {},
        },
    ],
}


def required_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError("%s is required" % name)
    return value


def main():
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import col, count, current_timestamp, desc, from_json, lit
    from pyspark.sql.functions import row_number, sum as spark_sum
    from pyspark.sql.types import StructType
    from pyspark.sql.window import Window

    bootstrap_servers = required_env("KAFKA_BOOTSTRAP_SERVERS")
    checkpoint_dir = required_env("SPARK_STREAM_CHECKPOINT_DIR")
    jdbc = {
        "url": required_env("SPARK_MYSQL_JDBC_URL"),
        "user": required_env("SPARK_MYSQL_USER"),
        "password": required_env("SPARK_MYSQL_PASSWORD"),
        "driver": os.environ.get("SPARK_MYSQL_DRIVER", "com.mysql.cj.jdbc.Driver"),
    }
    trigger_seconds = int(os.environ.get("SPARK_STREAM_TRIGGER_SECONDS", "10"))
    write_mode = os.environ.get("SPARK_MYSQL_WRITE_MODE", "append")
    run_prefix = os.environ.get("SPARK_STREAM_RUN_PREFIX") or datetime.now().strftime("kafka_stream_%Y%m%d_%H%M%S")

    spark = SparkSession.builder.appName("CreatorPulseKafkaStreamingToMySQLPy36").getOrCreate()
    schema = StructType.fromJson(VIDEO_STATS_SCHEMA_JSON)

    def write_jdbc(batch_df, batch_id):
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
            .withColumn("run_id", lit("%s_batch_%s" % (run_prefix, batch_id)))
            .withColumn("conversion_rate", col("new_followers") / col("total_views"))
            .withColumn("calculated_at", calculated_at)
            .select(
                "run_id",
                "creator_id",
                "platform",
                "total_views",
                "new_followers",
                "video_count",
                "conversion_rate",
                "calculated_at",
            )
        )

        ranked_df = (
            batch_df.withColumn("rank_position", row_number().over(Window.orderBy(desc("new_followers"))))
            .filter(col("rank_position") <= 10)
            .withColumn("run_id", lit("%s_batch_%s" % (run_prefix, batch_id)))
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

        for dataframe, table in (
            (platform_df, "spark_platform_metric_summaries"),
            (ranked_df, "spark_video_follower_contributions"),
        ):
            (
                dataframe.write.format("jdbc")
                .option("url", jdbc["url"])
                .option("dbtable", table)
                .option("user", jdbc["user"])
                .option("password", jdbc["password"])
                .option("driver", jdbc["driver"])
                .mode(write_mode)
                .save()
            )

        print("CREATORPULSE_STREAM_BATCH_OK batch_id=%s" % batch_id)

    kafka_df = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", bootstrap_servers)
        .option("subscribe", STREAMING_SOURCE_TOPIC)
        .option("startingOffsets", os.environ.get("SPARK_STREAM_STARTING_OFFSETS", "latest"))
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
        .outputMode("append")
        .option("checkpointLocation", checkpoint_dir)
        .trigger(processingTime="%s seconds" % trigger_seconds)
        .start()
    )
    query.awaitTermination()


if __name__ == "__main__":
    main()
