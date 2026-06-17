"""Report CreatorPulse MVP readiness and next actions."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.preflight import DEFAULT_ENV_PATH, run_checks, summarize  # noqa: E402
from scripts.report_env_readiness import build_report as build_env_readiness_report  # noqa: E402
from scripts.run_real_service_sequence import build_sequence_plan  # noqa: E402


DRY_RUN_CAPABILITIES = [
    {
        "name": "envInitialization",
        "status": "ready",
        "verifyCommand": "python scripts\\init_env.py --check",
    },
    {
        "name": "envReadinessReport",
        "status": "ready",
        "verifyCommand": "python scripts\\report_env_readiness.py",
    },
    {
        "name": "mockDataAndInsights",
        "status": "ready",
        "verifyCommand": "python mvp_mock\\validate_mock.py",
    },
    {
        "name": "flaskMockApi",
        "status": "ready",
        "verifyCommand": "python api\\tests\\test_mock_api.py",
    },
    {
        "name": "vueFrontend",
        "status": "ready",
        "verifyCommand": "cd frontend && npm run build",
    },
    {
        "name": "mysqlSchemaAndImportDryRun",
        "status": "ready",
        "verifyCommand": "python scripts\\setup_local_mysql.py",
    },
    {
        "name": "dataContractAudit",
        "status": "ready",
        "verifyCommand": "python scripts\\audit_data_contract.py",
    },
    {
        "name": "objectCoverageAudit",
        "status": "ready",
        "verifyCommand": "python scripts\\audit_object_coverage.py",
    },
    {
        "name": "dataQualityAudit",
        "status": "ready",
        "verifyCommand": "python scripts\\audit_data_quality.py",
    },
    {
        "name": "openapiExport",
        "status": "ready",
        "verifyCommand": "python scripts\\export_openapi.py --check",
    },
    {
        "name": "sparkStaticAndKafkaStyleDryRun",
        "status": "ready",
        "verifyCommand": "python kafka_tools\\run_closed_loop.py",
    },
    {
        "name": "fullPipelinePreflight",
        "status": "ready",
        "verifyCommand": "python scripts\\preflight.py --target full-pipeline",
    },
    {
        "name": "realServiceSequencePlan",
        "status": "ready",
        "verifyCommand": "python scripts\\run_real_service_sequence.py",
    },
    {
        "name": "realServiceExecutionPlanReport",
        "status": "ready",
        "verifyCommand": "python scripts\\report_real_service_plans.py",
    },
    {
        "name": "realServiceExecutionChecklist",
        "status": "ready",
        "verifyCommand": "python scripts\\report_execution_checklist.py",
    },
    {
        "name": "realServiceReadinessAudit",
        "status": "ready",
        "verifyCommand": "python scripts\\audit_real_service_readiness.py",
    },
    {
        "name": "realServiceReportBundleExport",
        "status": "ready",
        "verifyCommand": "python scripts\\export_real_service_report_bundle.py",
    },
]

REAL_EXECUTION_NEXT_STEPS = {
    "mysql": [
        "python scripts\\init_env.py",
        "Fill MYSQL_* values in .env",
        "python scripts\\preflight.py --target local-mysql --strict",
        "python scripts\\setup_local_mysql.py --execute",
    ],
    "sparkJdbc": [
        "Fill SPARK_MYSQL_JDBC_URL, SPARK_MYSQL_USER, SPARK_MYSQL_PASSWORD, SPARK_MYSQL_DRIVER in .env",
        "python scripts\\preflight.py --target spark-jdbc --strict",
        "Set CREATORPULSE_RUN_SPARK_JDBC_LIVE=1 before running the optional live test",
        "python spark_jobs\\tests\\test_static_mysql_jdbc_integration.py",
        "spark-submit spark_jobs\\static_mock_to_mysql.py --execute",
    ],
    "kafka": [
        "Fill KAFKA_BOOTSTRAP_SERVERS with the VM Kafka host:port",
        "python scripts\\preflight.py --target kafka --strict",
        "Set CREATORPULSE_RUN_KAFKA_LIVE=1 before running the optional live test",
        "python kafka_tools\\tests\\test_kafka_live_integration.py",
        "python kafka_tools\\run_closed_loop.py --execute-kafka",
    ],
    "fullPipeline": [
        "Run MySQL import, Spark JDBC live check, and Kafka live check successfully first",
        "python scripts\\preflight.py --target full-pipeline --strict",
        "Set CREATORPULSE_RUN_FULL_PIPELINE_LIVE=1 before starting the streaming job",
        "spark-submit spark_jobs\\kafka_streaming_to_mysql.py --execute",
    ],
}

ROLLOUT_STAGES = {
    "mysql": {
        "envStage": "localMysql",
        "preflightTarget": "localMysql",
    },
    "spark-jdbc": {
        "envStage": "sparkJdbc",
        "preflightTarget": "sparkJdbc",
    },
    "kafka": {
        "envStage": "kafka",
        "preflightTarget": "kafka",
    },
    "full-pipeline": {
        "envStage": "fullPipeline",
        "preflightTarget": "fullPipeline",
    },
}


def status_from_preflight(env_file: Path) -> dict:
    all_checks = run_checks(env_file, target="all")
    mysql_checks = run_checks(env_file, target="local-mysql")
    spark_checks = run_checks(env_file, target="spark-jdbc")
    kafka_checks = run_checks(env_file, target="kafka")
    full_pipeline_checks = run_checks(env_file, target="full-pipeline")
    return {
        "all": {
            "summary": summarize(all_checks),
            "checks": [asdict(item) for item in all_checks],
        },
        "localMysql": {
            "summary": summarize(mysql_checks),
            "checks": [asdict(item) for item in mysql_checks],
        },
        "sparkJdbc": {
            "summary": summarize(spark_checks),
            "checks": [asdict(item) for item in spark_checks],
        },
        "kafka": {
            "summary": summarize(kafka_checks),
            "checks": [asdict(item) for item in kafka_checks],
        },
        "fullPipeline": {
            "summary": summarize(full_pipeline_checks),
            "checks": [asdict(item) for item in full_pipeline_checks],
        },
    }


def build_status(env_file: Path) -> dict:
    preflight = status_from_preflight(env_file)
    env_readiness = build_env_readiness_report(env_file)
    next_step = next_recommended_step(preflight)
    rollout_stage = rollout_stage_for_recommendation(next_step["stage"])
    return {
        "status": "ready-for-dry-run" if preflight["all"]["summary"]["counts"]["error"] == 0 else "needs-local-fixes",
        "dryRunCapabilities": DRY_RUN_CAPABILITIES,
        "envReadiness": env_readiness,
        "preflight": preflight,
        "realServiceReadinessSummary": build_real_service_readiness_summary(env_readiness, preflight),
        "nextRecommendedStep": next_step,
        "nextRolloutStage": rollout_stage,
        "nextRolloutPlan": build_sequence_plan(stage=rollout_stage),
        "realExecutionNextSteps": REAL_EXECUTION_NEXT_STEPS,
        "fullVerifyCommand": "python scripts\\verify_mvp.py",
    }


def build_real_service_readiness_summary(env_readiness: dict, preflight: dict) -> dict:
    blocked_stages = []
    ready_for_strict_preflight = []
    ready_for_execute = []
    blocking_keys: list[str] = []

    for stage, mapping in ROLLOUT_STAGES.items():
        env_stage = mapping["envStage"]
        preflight_target = mapping["preflightTarget"]
        env_blocking = env_readiness["stages"][env_stage]["blockingKeys"]
        preflight_counts = preflight[preflight_target]["summary"]["counts"]
        has_env_blocking = bool(env_blocking)
        has_preflight_blocking = preflight_counts["warning"] > 0 or preflight_counts["error"] > 0

        if not has_env_blocking:
            ready_for_strict_preflight.append(stage)
        if not has_env_blocking and not has_preflight_blocking:
            ready_for_execute.append(stage)
        if has_env_blocking or has_preflight_blocking:
            blocked_stages.append(stage)
        for key in env_blocking:
            if key not in blocking_keys:
                blocking_keys.append(key)

    return {
        "status": "ready-for-execute" if not blocked_stages else "blocked",
        "blockedStages": blocked_stages,
        "readyForStrictPreflightStages": ready_for_strict_preflight,
        "readyForExecuteStages": ready_for_execute,
        "nextBlockingKeys": blocking_keys[:8],
        "safety": {
            "willWriteMySQL": False,
            "willConnectKafka": False,
            "willStartStreaming": False,
        },
    }


def rollout_stage_for_recommendation(stage: str) -> str:
    if stage in {"configure-env", "fix-local-errors"}:
        return "all"
    if stage == "local-mysql-preflight":
        return "mysql"
    if stage == "spark-jdbc-preflight":
        return "spark-jdbc"
    if stage == "kafka-preflight":
        return "kafka"
    if stage in {"full-pipeline-preflight", "ready-for-real-service-sequence"}:
        return "full-pipeline"
    return "all"


def has_check_message(preflight: dict, target: str, name: str, message_part: str) -> bool:
    return any(
        item["name"] == name and message_part in item["message"]
        for item in preflight[target]["checks"]
    )


def has_warnings(preflight: dict, target: str) -> bool:
    return preflight[target]["summary"]["counts"]["warning"] > 0


def next_recommended_step(preflight: dict) -> dict:
    if preflight["all"]["summary"]["counts"]["error"] > 0:
        return {
            "stage": "fix-local-errors",
            "reason": "local required files or commands are missing",
            "command": "python scripts\\preflight.py",
        }

    if has_check_message(preflight, "all", "env file", ".env not found"):
        return {
            "stage": "configure-env",
            "reason": "real MySQL, Spark JDBC, and Kafka execution need local credentials and host values",
            "command": "python scripts\\init_env.py",
            "manualFollowUp": "Fill MYSQL_*, SPARK_MYSQL_*, and KAFKA_BOOTSTRAP_SERVERS values in .env as each real-service phase starts.",
        }

    if has_warnings(preflight, "localMysql"):
        return {
            "stage": "local-mysql-preflight",
            "reason": "MySQL config, TCP reachability, or login is not ready for strict execution",
            "command": "python scripts\\preflight.py --target local-mysql --strict",
        }

    if has_warnings(preflight, "sparkJdbc"):
        return {
            "stage": "spark-jdbc-preflight",
            "reason": "MySQL is ready, but Spark JDBC config or reachability still needs verification",
            "command": "python scripts\\preflight.py --target spark-jdbc --strict",
        }

    if has_warnings(preflight, "kafka"):
        return {
            "stage": "kafka-preflight",
            "reason": "MySQL and Spark JDBC are ready, but Kafka VM connectivity still needs verification",
            "command": "python scripts\\preflight.py --target kafka --strict",
        }

    if has_warnings(preflight, "fullPipeline"):
        return {
            "stage": "full-pipeline-preflight",
            "reason": "individual services are ready; verify combined Kafka, Spark JDBC, and MySQL settings before streaming execution",
            "command": "python scripts\\preflight.py --target full-pipeline --strict",
        }

    return {
        "stage": "ready-for-real-service-sequence",
        "reason": "all preflight targets have no warnings",
        "command": "spark-submit spark_jobs\\kafka_streaming_to_mysql.py --execute",
        "manualFollowUp": "Only run after MySQL import, Spark JDBC live check, Kafka live check, and full-pipeline strict preflight have succeeded.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Report CreatorPulse MVP readiness")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    args = parser.parse_args()

    print(json.dumps(build_status(args.env_file), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
