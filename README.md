# CreatorPulse MVP

CreatorPulse is currently a runnable MVP prototype:

- unified mock data and rule-based Insight
- Flask API with mock / MySQL repository switch
- Vue/Vite frontend for six primary pages
- MySQL schema and mock import dry-runs
- Spark and Kafka-style dry-run jobs before real VM Kafka is connected
- Spark summary outputs wired into Flask ViewModels and the Vue video/content pages
- explicit Flask ViewModel contract checks shared by mock and MySQL data sources
- data-contract audit for schema/import/ViewModel/OpenAPI drift before real services
- data-quality audit for mock formulas, traffic-source rollups, Spark dry-run parity, and Insight evidence
- machine-readable OpenAPI contract served at `/api/openapi.json`

## Verify MVP

Run the full local verification:

```powershell
python scripts\verify_mvp.py
```

This command runs backend/data tests, database dry-runs, Spark/Kafka dry-runs,
frontend build, Vite browser smoke test, Flask-served frontend smoke test, and
`git diff --check`.

For a faster non-browser check:

```powershell
python scripts\verify_mvp.py --skip-browser
```

To see what is ready in dry-run mode and what real-service config is still
missing:

```powershell
python scripts\status_mvp.py
python scripts\report_env_readiness.py
```

`report_env_readiness.py` groups `.env` keys by rollout phase and redacts
secret values. It does not perform network checks or write external services.
The same redacted readiness block is also embedded in `status_mvp.py` as
`envReadiness`, so the main status report shows the next stage, blocking
configuration keys, preflight results, and rollout plan together.
`status_mvp.py` also includes `realServiceReadinessSummary`, a compact summary
of blocked rollout stages, stages that can enter strict preflight, stages ready
for guarded execution, and the next blocking `.env` keys. This summary is
read-only and keeps all real-service execution switches off.

To print the ordered real-service rollout plan without executing anything:

```powershell
python scripts\run_real_service_sequence.py
python scripts\run_real_service_sequence.py --stage mysql
python scripts\run_real_service_sequence.py --stage spark-jdbc
python scripts\run_real_service_sequence.py --stage kafka
python scripts\run_real_service_sequence.py --stage full-pipeline
```

To inspect the detailed dry-run execution plans for all real-service phases in
one report:

```powershell
python scripts\report_real_service_plans.py
python scripts\report_real_service_plans.py --stage mysql
python scripts\report_real_service_plans.py --stage spark-jdbc
python scripts\report_real_service_plans.py --stage kafka
python scripts\report_real_service_plans.py --stage full-pipeline
python scripts\report_execution_checklist.py
python scripts\report_execution_checklist.py --stage mysql
python scripts\report_execution_checklist.py --stage spark-jdbc
python scripts\report_execution_checklist.py --stage kafka
python scripts\report_execution_checklist.py --stage full-pipeline
python scripts\audit_real_service_readiness.py
python scripts\export_real_service_report_bundle.py
```

`report_real_service_plans.py` combines the MySQL setup plan, Spark JDBC static
write plan, Kafka closed-loop plan, and Kafka -> Spark -> MySQL streaming plan.
Use `--stage` to inspect one phase at a time. It keeps all real execution
switches off: no MySQL write, no Kafka connection, and no Spark Streaming
startup.

`report_execution_checklist.py` combines redacted `.env` readiness, preflight
summaries, manual gates, and rollout steps into one dry-run checklist. It shows
whether each phase is ready for strict preflight or still blocked before any
`--execute` command is attempted. Use `--stage` to focus the checklist on the
next real-service phase you are preparing.

`audit_real_service_readiness.py` cross-checks the real-service sequence,
execution-plan report, and execution checklist. It verifies that all tools use
the same rollout stages, stage filters return the matching slice, and dry-run
safety flags stay off before real execution is explicitly enabled.

`export_real_service_report_bundle.py` writes the current status, environment
readiness, rollout sequence, execution plans, execution checklist, and readiness
audit into one local report directory with a `manifest.json`. It is also
read-only: no MySQL write, Kafka connection, or Spark Streaming startup.

These read-only report commands also support optional JSON artifact export with
`--output`, for example:

```powershell
python scripts\report_execution_checklist.py --stage mysql --output reports\mysql-checklist.json
python scripts\audit_real_service_readiness.py --output reports\real-service-readiness-audit.json
python scripts\export_real_service_report_bundle.py --stage mysql --output-dir reports\mysql-readiness-bundle
```

The individual report commands do not write files unless `--output` is
provided. The bundle export command writes to `--output-dir`, defaulting under
`reports/`. The local `reports/` folder is ignored by git.

The status report also includes `nextRecommendedStep`, which is intentionally
conservative. It recommends `.env` setup or strict preflight commands before
any real MySQL import, Spark JDBC write, or Kafka produce/consume step. It also
includes `nextRolloutStage` and `nextRolloutPlan`, so the next focused dry-run
plan is visible directly in the status JSON.
Use `realServiceReadinessSummary` when you only need the short answer: what is
blocked, what can be preflighted, and which keys should be filled next.

The API response shape is guarded by `api/view_model_contract.py`; both mock
API responses and MySQL-mapped ViewModels are checked by the verification suite.
Frontend service paths are also checked against the OpenAPI page endpoints.
The same boundary is also exposed as OpenAPI JSON:

```powershell
python api\app.py
# then open http://127.0.0.1:5000/api/openapi.json
```

To update and verify the static OpenAPI artifact:

```powershell
python scripts\export_openapi.py
python scripts\export_openapi.py --check
```

The generated file is [api/openapi.json](api/openapi.json).

Before real MySQL / Spark / Kafka execution, run the dry-run data-contract audit:

```powershell
python scripts\audit_data_contract.py
python scripts\audit_object_coverage.py
python scripts\audit_data_quality.py
```

The contract audit compares MySQL schema columns, mock import rows,
MySQL-mapped ViewModels, and OpenAPI page contracts. The object coverage audit
shows which MVP data objects are stored in MySQL and which page ViewModels
consume them, including objects intentionally stored for later use. The data
quality audit checks business formulas, traffic-source totals, Spark dry-run
rollup parity, and whether Insights include evidence and recommended actions.

## Environment Preflight

Check whether local commands, config files, MySQL, Spark, and Kafka settings are ready:

```powershell
python scripts\preflight.py
```

Warnings are allowed in normal MVP dry-run mode. Before real MySQL/Kafka/Spark execution, use strict mode:

```powershell
python scripts\preflight.py --strict
```

You can also check real-service readiness independently:

```powershell
python scripts\preflight.py --target local-mysql --strict
python scripts\preflight.py --target spark-jdbc --strict
python scripts\preflight.py --target kafka --strict
python scripts\preflight.py --target full-pipeline --strict
```

The local MySQL strict preflight checks TCP reachability, placeholder values,
and a real MySQL login with `SELECT 1`. It does not create databases or write
rows; that only happens in `scripts\setup_local_mysql.py --execute`.

## Local MySQL Flow

Create a local `.env` from the template, fill your local MySQL values, then run:

```powershell
python scripts\init_env.py
python scripts\preflight.py --target local-mysql --strict
python scripts\setup_local_mysql.py --execute
```

`init_env.py` will not overwrite an existing `.env` unless you explicitly pass
`--force`, so your local credentials stay under your control.

`setup_local_mysql.py` applies the schema, imports mock rows, verifies actual
MySQL table row counts against the expected mock counts, then verifies the Flask
API in `CREATORPULSE_DATA_SOURCE=mysql` mode. The `--execute` path always
treats preflight warnings as failures before any write happens. Without
`--execute`, it is a dry-run that validates schema parsing, row mapping, and API
contract shape without connecting to MySQL. The dry-run output includes
`executionPlan`, which shows the strict preflight requirement, planned setup
steps, target table count, and planned row counts before any MySQL write.

After a real import, you can run the optional live MySQL API contract test:

```powershell
python api\tests\test_mysql_api_integration.py
```

It skips cleanly when `.env` is missing or still contains placeholder MySQL
credentials.

The import includes the current Spark summary tables:

- `spark_platform_metric_summaries`
- `spark_video_follower_contributions`

Those rows are exposed by the Flask API as page ViewModel fields and are used by
the Vue video analysis and content distribution pages.

The API also derives two MVP rule-based insights from those Spark outputs using
`SPARK_RULE_ENGINE`, so Spark aggregate results can drive page conclusions
without introducing AI-generated copy yet.

## Spark JDBC Live Check

After MySQL import works and `.env` contains real `SPARK_MYSQL_*` values, run:

```powershell
python scripts\preflight.py --target spark-jdbc --strict
$env:CREATORPULSE_RUN_SPARK_JDBC_LIVE='1'
python spark_jobs\tests\test_static_mysql_jdbc_integration.py
```

The Spark JDBC strict preflight checks `spark-submit`, MySQL TCP reachability,
JDBC URL shape, MySQL Connector/J driver name, `SPARK_MYSQL_WRITE_MODE=append`,
and MySQL login readiness before live Spark writes are enabled.

Without `--execute`, `spark_jobs\static_mock_to_mysql.py` is a dry-run. Its JSON
output includes `executionPlan`, showing the two target Spark result tables,
the JDBC write mode, and planned row counts before any MySQL write.

`spark_jobs\static_mock_to_mysql.py --execute` also performs its own Spark JDBC
config guard and returns a JSON failure if placeholder credentials, a non-MySQL
JDBC URL, a non-MySQL driver, or a non-`append` write mode is detected.

The live test is opt-in because it writes the two Spark result tables through
JDBC. With the default `.env.example` value, it skips safely during normal
verification.

Kafka remains decoupled from the Flask / Vue / MySQL main path until VM
connectivity is confirmed.

## Kafka Live Check

After the VM Kafka broker is reachable and `.env` contains a real
`KAFKA_BOOTSTRAP_SERVERS` value, run:

```powershell
python scripts\preflight.py --target kafka --strict
$env:CREATORPULSE_RUN_KAFKA_LIVE='1'
python kafka_tools\tests\test_kafka_live_integration.py
```

The live test is opt-in because it produces and consumes the MVP mock events
through Kafka. With the default `.env.example` value, it skips safely during
normal verification.

Without `--execute-kafka`, `kafka_tools\run_closed_loop.py` stays local. Its
JSON output includes `executionPlan`, showing planned event counts, event type
coverage, and offline Spark-style row counts before any Kafka connection.

Kafka strict preflight validates the bootstrap server shape and rejects the
template `192.168.56.10:9092` value as a placeholder. `mock_producer.py
--execute-kafka` and `run_closed_loop.py --execute-kafka` also return JSON
failures before producing or consuming when the bootstrap config is still a
placeholder or malformed.

For lower-level troubleshooting, the setup script is equivalent to:

```powershell
python database\apply_schema.py --execute
python database\import_mock_to_mysql.py --execute
```

## Kafka -> Spark -> MySQL Streaming Check

Only run the full streaming job after the three independent live checks have
already succeeded:

```powershell
python scripts\run_real_service_sequence.py
python scripts\preflight.py --target local-mysql --strict
python scripts\setup_local_mysql.py --execute
python scripts\preflight.py --target spark-jdbc --strict
$env:CREATORPULSE_RUN_SPARK_JDBC_LIVE='1'
python spark_jobs\tests\test_static_mysql_jdbc_integration.py
python scripts\preflight.py --target kafka --strict
$env:CREATORPULSE_RUN_KAFKA_LIVE='1'
python kafka_tools\tests\test_kafka_live_integration.py
python scripts\preflight.py --target full-pipeline --strict
$env:CREATORPULSE_RUN_FULL_PIPELINE_LIVE='1'
spark-submit spark_jobs\kafka_streaming_to_mysql.py --execute
```

The `full-pipeline` preflight checks the combined requirements for streaming:
MySQL login, Spark submit availability, Spark JDBC config, Kafka bootstrap
config, Kafka TCP reachability, the streaming output mode, and whether
`MYSQL_DATABASE` matches the database name inside `SPARK_MYSQL_JDBC_URL`. It
does not require the MySQL host and JDBC host to match, because Spark may run in
a VM and reach the same MySQL database through a different host address. It
still does not write rows or consume Kafka messages. Writes only happen in the
final `spark-submit ... --execute` command, and that command also requires
`CREATORPULSE_RUN_FULL_PIPELINE_LIVE=1` as a second explicit opt-in.

Without `--execute`, `spark_jobs\kafka_streaming_to_mysql.py` is a dry-run. Its
JSON output includes `executionPlan`, showing the source topic, trigger
interval, checkpoint directory, output mode, MySQL write mode, target tables,
and both required execution gates before streaming can start.

`scripts\run_real_service_sequence.py` is intentionally dry-run only in the
current MVP. It prints the required order as JSON so the sequence can be
reviewed by tools and humans, but it does not create MySQL tables, connect to
Kafka, or start Spark streaming. Use `--stage mysql`, `--stage spark-jdbc`,
`--stage kafka`, or `--stage full-pipeline` when you only want the next focused
rollout plan.

## Run Built Frontend Through Flask

Build the Vue frontend, then start Flask:

```powershell
cd frontend
npm run build
cd ..
python api\app.py
```

Then open `http://127.0.0.1:5000`. API routes remain under `/api/...`.
