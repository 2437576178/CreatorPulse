# CreatorPulse Spark JDBC Smoke Job

This folder implements roadmap phase six: prove Spark can write MySQL through JDBC before connecting Kafka.

The first job reads the static MVP mock JSON, computes:

- platform-level playback and follower summaries
- top video follower contributions

Then it can write the results to:

- `spark_platform_metric_summaries`
- `spark_video_follower_contributions`

The same rows are also generated during mock MySQL import dry-runs and are
mapped back through the Flask ViewModel contract:

- `videoAnalysis.sparkContributions`
- `contentDistribution.sparkPlatformSummaries`

The Flask API derives MVP `SPARK_RULE_ENGINE` insights from these aggregate
outputs. This keeps SparkSQL-style findings evidence-based while the project
stays in the rule/template Insight phase.

## Dry Run

```powershell
python spark_jobs\static_mock_to_mysql.py
```

## Real Spark JDBC Write

After MySQL schema is created and `.env` is filled:

```powershell
spark-submit spark_jobs\static_mock_to_mysql.py --execute
```

This stage does not connect Kafka. Kafka connectivity is intentionally kept as a later independent test.

## Parse Kafka-Style Events

After generating local mock events:

```powershell
python kafka_tools\mock_producer.py
python spark_jobs\kafka_events_to_mysql.py
```

This parses the NDJSON events and computes the same summary rows that the later
Spark Streaming job should write to MySQL. It is deliberately offline and
testable before VM Kafka is connected.

You can run the producer, consumer validation, and this offline aggregation as
one local closed-loop check:

```powershell
python kafka_tools\run_closed_loop.py
```

## Structured Streaming Entry

Validate streaming configuration without connecting Kafka or MySQL:

```powershell
python spark_jobs\kafka_streaming_to_mysql.py
```

After Kafka connectivity, MySQL schema/import, and Spark JDBC are confirmed:

```powershell
spark-submit spark_jobs\kafka_streaming_to_mysql.py --execute
```

The streaming job subscribes to `video_stats_topic`, aggregates video events,
and writes to:

- `spark_platform_metric_summaries`
- `spark_video_follower_contributions`
- `video_metric_snapshots`
- `video_traffic_source_metrics`
- `creator_metric_snapshots`

The first two tables are Spark diagnostic/result tables. The last three are
the page-facing metric tables used by the Flask API, so a newly registered
creator can leave the "waiting for events" state after the first event batch.
