"""Python 3.6 compatible Spark Streaming job for the CentOS VM.

The local development job uses newer Python typing syntax. The VM currently
ships Python 3.6, so this file keeps the runtime path small and compatible.
"""

import os
from datetime import datetime
try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse


STREAMING_SOURCE_TOPIC = "video_stats_topic"
MAIN_TABLE_PRIMARY_KEYS = {
    "video_metric_snapshots": ["snapshot_id"],
    "video_traffic_source_metrics": ["video_id", "source"],
    "creator_metric_snapshots": ["snapshot_id", "creator_id", "metric_date"],
}


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
                    {"name": "interaction_rate", "type": "double", "nullable": True, "metadata": {}},
                    {"name": "completion_rate", "type": "double", "nullable": True, "metadata": {}},
                    {"name": "average_watch_seconds", "type": "integer", "nullable": True, "metadata": {}},
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
                    {"name": "play_growth_5s", "type": "long", "nullable": True, "metadata": {}},
                    {"name": "like_delta", "type": "long", "nullable": True, "metadata": {}},
                    {"name": "comment_delta", "type": "long", "nullable": True, "metadata": {}},
                    {"name": "share_delta", "type": "long", "nullable": True, "metadata": {}},
                    {"name": "save_delta", "type": "long", "nullable": True, "metadata": {}},
                    {"name": "new_followers_delta", "type": "long", "nullable": True, "metadata": {}},
                    {"name": "new_followers", "type": "long", "nullable": False, "metadata": {}},
                    {"name": "profile_visits", "type": "long", "nullable": False, "metadata": {}},
                ],
            },
            "nullable": False,
            "metadata": {},
        },
        {
            "name": "traffic_source",
            "type": {
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
            },
            "nullable": True,
            "metadata": {},
        },
    ],
}


def required_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError("%s is required" % name)
    return value


def parse_mysql_jdbc_url(jdbc_url):
    if not jdbc_url.startswith("jdbc:mysql://"):
        raise RuntimeError("SPARK_MYSQL_JDBC_URL must start with jdbc:mysql://")
    parsed = urlparse(jdbc_url.replace("jdbc:mysql://", "mysql://", 1))
    if not parsed.hostname or not parsed.path.strip("/"):
        raise RuntimeError("SPARK_MYSQL_JDBC_URL must include host and database")
    return {"host": parsed.hostname, "port": parsed.port or 3306, "database": parsed.path.strip("/")}


def build_upsert_sql(table, columns, primary_keys):
    column_sql = ", ".join(["`%s`" % column for column in columns])
    placeholders = ", ".join(["%s"] * len(columns))
    update_columns = [column for column in columns if column not in primary_keys]
    update_sql = ", ".join(["`%s` = VALUES(`%s`)" % (column, column) for column in update_columns])
    return "INSERT INTO `%s` (%s) VALUES (%s) ON DUPLICATE KEY UPDATE %s" % (table, column_sql, placeholders, update_sql)


def main():
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import col, concat, count, current_date, current_timestamp, date_format, desc, explode, from_json, lit, lower
    from pyspark.sql.functions import regexp_replace, row_number, sum as spark_sum, to_date, to_json, when
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

    def jdbc_write(dataframe, table, mode):
        (
            dataframe.write.format("jdbc")
            .option("url", jdbc["url"])
            .option("dbtable", table)
            .option("user", jdbc["user"])
            .option("password", jdbc["password"])
            .option("driver", jdbc["driver"])
            .mode(mode)
            .save()
        )

    def mysql_upsert(dataframe, table):
        columns = dataframe.columns
        sql = build_upsert_sql(table, columns, MAIN_TABLE_PRIMARY_KEYS[table])
        mysql_target = parse_mysql_jdbc_url(jdbc["url"])
        user = jdbc["user"]
        password = jdbc["password"]

        def write_partition(rows):
            batch = [tuple([row[column] for column in columns]) for row in rows]
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

    def write_jdbc(batch_df, batch_id):
        if batch_df.rdd.isEmpty():
            return

        calculated_at = current_timestamp()
        metric_date = current_date()
        run_id = lit("%s_batch_%s" % (run_prefix, batch_id))
        by_creator_video = Window.partitionBy("creator_id", "content_id").orderBy(desc("fetch_time"), desc("event_id"))
        latest_df = batch_df.withColumn("rn", row_number().over(by_creator_video)).filter(col("rn") == 1).drop("rn")
        raw_event_df = (
            batch_df.withColumn("event_date", to_date(col("fetch_time")))
            .withColumn("raw_payload_json", to_json(col("event_json")))
            .select(
                "event_id",
                "creator_id",
                "platform",
                col("content_id").alias("video_id"),
                "event_type",
                "event_date",
                "fetch_time",
                "play_delta",
                "like_delta",
                "comment_delta",
                "share_delta",
                "save_delta",
                col("profile_visits").alias("profile_visit_delta"),
                col("new_followers_delta").alias("new_follower_delta"),
                lit(0).alias("lost_follower_delta"),
                "raw_payload_json",
            )
        )
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
            .withColumn("stickiness_score", when(((col("total_interactions") / col("total_views")) * 180) > 100, 100).otherwise((col("total_interactions") / col("total_views")) * 180))
            .withColumn(
                "growth_health_score",
                when(
                    ((col("view_to_follower_rate") * 900) + ((col("new_followers") / col("profile_visits")) * 100) + (col("stickiness_score") * 0.25)) > 100,
                    100,
                ).otherwise((col("view_to_follower_rate") * 900) + ((col("new_followers") / col("profile_visits")) * 100) + (col("stickiness_score") * 0.25)),
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

        jdbc_write(raw_event_df, "raw_video_stat_events", "append")
        jdbc_write(platform_df, "spark_platform_metric_summaries", write_mode)
        jdbc_write(ranked_df, "spark_video_follower_contributions", write_mode)
        mysql_upsert(video_metric_df, "video_metric_snapshots")
        mysql_upsert(traffic_source_df, "video_traffic_source_metrics")
        mysql_upsert(creator_metric_df, "creator_metric_snapshots")

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
        .filter(col("event.event_type") == "video_stats")
        .select(
            col("event.creator_id").alias("creator_id"),
            col("event.platform").alias("platform"),
            col("event.event_id").alias("event_id"),
            col("event.event_type").alias("event_type"),
            col("event.fetch_time").alias("fetch_time"),
            col("event.content_id").alias("content_id"),
            col("event.title").alias("title"),
            col("event.stats.play_count").alias("views"),
            col("event.stats.like_count").alias("likes"),
            col("event.stats.comment_count").alias("comments"),
            col("event.stats.share_count").alias("shares"),
            col("event.stats.save_count").alias("saves"),
            col("event.stats.completion_rate").alias("completion_rate"),
            col("event.stats.average_watch_seconds").alias("average_watch_seconds"),
            col("event.growth.new_followers").alias("new_followers"),
            when(col("event.growth.new_followers_delta").isNotNull(), col("event.growth.new_followers_delta")).otherwise(col("event.growth.new_followers")).alias("new_followers_delta"),
            col("event.growth.profile_visits").alias("profile_visits"),
            when(col("event.growth.play_growth_5s").isNotNull() & (col("event.growth.play_growth_5s") > 0), col("event.growth.play_growth_5s")).otherwise(col("event.stats.play_count")).alias("play_delta"),
            when(col("event.growth.like_delta").isNotNull(), col("event.growth.like_delta")).otherwise((col("event.stats.like_count") * lit(0.0012)).cast("long")).alias("like_delta"),
            when(col("event.growth.comment_delta").isNotNull(), col("event.growth.comment_delta")).otherwise((col("event.stats.comment_count") * lit(0.0012)).cast("long")).alias("comment_delta"),
            when(col("event.growth.share_delta").isNotNull(), col("event.growth.share_delta")).otherwise((col("event.stats.share_count") * lit(0.0012)).cast("long")).alias("share_delta"),
            when(col("event.growth.save_delta").isNotNull(), col("event.growth.save_delta")).otherwise((col("event.stats.save_count") * lit(0.0012)).cast("long")).alias("save_delta"),
            col("event.traffic_source").alias("traffic_source"),
            col("event").alias("event_json"),
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
