"""Tests for MVP readiness status report."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.status_mvp import build_status  # noqa: E402
from scripts.preflight import CheckResult  # noqa: E402


class StatusMVPTest(unittest.TestCase):
    def test_reports_dry_run_capabilities_and_next_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            status = build_status(env_file)

        self.assertEqual(status["status"], "ready-for-dry-run")
        capability_names = {item["name"] for item in status["dryRunCapabilities"]}
        self.assertIn("envInitialization", capability_names)
        self.assertIn("envReadinessReport", capability_names)
        self.assertIn("mockDataAndInsights", capability_names)
        self.assertIn("dataContractAudit", capability_names)
        self.assertIn("objectCoverageAudit", capability_names)
        self.assertIn("dataQualityAudit", capability_names)
        self.assertIn("openapiExport", capability_names)
        self.assertIn("sparkStaticAndKafkaStyleDryRun", capability_names)
        self.assertIn("fullPipelinePreflight", capability_names)
        self.assertIn("realServiceSequencePlan", capability_names)
        self.assertIn("realServiceExecutionPlanReport", capability_names)
        self.assertIn("realServiceExecutionChecklist", capability_names)
        self.assertIn("realServiceReadinessAudit", capability_names)
        self.assertIn("realServiceReportBundleExport", capability_names)
        self.assertIn("mysql", status["realExecutionNextSteps"])
        self.assertIn("sparkJdbc", status["realExecutionNextSteps"])
        self.assertIn("kafka", status["realExecutionNextSteps"])
        self.assertIn("sparkJdbc", status["preflight"])
        self.assertIn("kafka", status["preflight"])
        self.assertIn("envReadiness", status)
        self.assertEqual(status["envReadiness"]["status"], "needs-values")
        self.assertIn("localMysql", status["envReadiness"]["blockingByStage"])
        self.assertTrue(status["envReadiness"]["safety"]["redactsSecrets"])
        self.assertEqual(status["nextRecommendedStep"]["stage"], "configure-env")
        self.assertEqual(status["nextRecommendedStep"]["command"], "python scripts\\init_env.py")
        self.assertEqual(status["nextRolloutStage"], "all")
        self.assertEqual(status["nextRolloutPlan"]["stage"], "all")
        self.assertEqual(status["realServiceReadinessSummary"]["status"], "blocked")
        self.assertIn("mysql", status["realServiceReadinessSummary"]["blockedStages"])
        self.assertIn("spark-jdbc", status["realServiceReadinessSummary"]["blockedStages"])
        self.assertIn("MYSQL_USER", status["realServiceReadinessSummary"]["nextBlockingKeys"])
        self.assertEqual(status["realServiceReadinessSummary"]["readyForStrictPreflightStages"], [])
        self.assertEqual(status["realServiceReadinessSummary"]["readyForExecuteStages"], [])
        self.assertFalse(status["realServiceReadinessSummary"]["safety"]["willWriteMySQL"])
        self.assertFalse(status["realServiceReadinessSummary"]["safety"]["willConnectKafka"])
        self.assertFalse(status["realServiceReadinessSummary"]["safety"]["willStartStreaming"])
        self.assertTrue(all(step["willExecute"] is False for step in status["nextRolloutPlan"]["steps"]))
        self.assertTrue(any("--target spark-jdbc" in item for item in status["realExecutionNextSteps"]["sparkJdbc"]))
        self.assertTrue(any("CREATORPULSE_RUN_SPARK_JDBC_LIVE=1" in item for item in status["realExecutionNextSteps"]["sparkJdbc"]))
        self.assertTrue(any("--target kafka" in item for item in status["realExecutionNextSteps"]["kafka"]))
        self.assertTrue(any("CREATORPULSE_RUN_KAFKA_LIVE=1" in item for item in status["realExecutionNextSteps"]["kafka"]))
        self.assertTrue(any("CREATORPULSE_RUN_FULL_PIPELINE_LIVE=1" in item for item in status["realExecutionNextSteps"]["fullPipeline"]))
        self.assertGreater(status["preflight"]["all"]["summary"]["counts"]["warning"], 0)

    def test_recommends_local_mysql_preflight_when_env_exists_but_service_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "MYSQL_HOST=127.0.0.1",
                        "MYSQL_PORT=1",
                        "MYSQL_DATABASE=creatorpulse",
                        "MYSQL_USER=creatorpulse",
                        "MYSQL_PASSWORD=secret",
                        "SPARK_MYSQL_JDBC_URL=jdbc:mysql://127.0.0.1:1/creatorpulse",
                        "SPARK_MYSQL_USER=creatorpulse",
                        "SPARK_MYSQL_PASSWORD=secret",
                        "SPARK_MYSQL_DRIVER=com.mysql.cj.jdbc.Driver",
                        "KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:1",
                    ]
                ),
                encoding="utf-8",
            )
            status = build_status(env_file)

        self.assertEqual(status["nextRecommendedStep"]["stage"], "local-mysql-preflight")
        self.assertEqual(status["envReadiness"]["stages"]["localMysql"]["status"], "ready-for-strict-preflight")
        self.assertIn("mysql", status["realServiceReadinessSummary"]["readyForStrictPreflightStages"])
        self.assertIn("mysql", status["realServiceReadinessSummary"]["blockedStages"])
        self.assertNotIn("MYSQL_PASSWORD", status["realServiceReadinessSummary"]["nextBlockingKeys"])
        self.assertNotIn("secret", str(status["envReadiness"]))
        self.assertEqual(status["nextRecommendedStep"]["command"], "python scripts\\preflight.py --target local-mysql --strict")
        self.assertEqual(status["nextRolloutStage"], "mysql")
        self.assertEqual(
            [step["name"] for step in status["nextRolloutPlan"]["steps"]],
            ["localMysqlPreflight", "localMysqlImport"],
        )

    def test_recommends_full_pipeline_preflight_after_individual_targets_are_ready(self) -> None:
        def fake_run_checks(_env_file: Path, target: str = "all") -> list[CheckResult]:
            checks = [CheckResult("env file", "ok", ".env")]
            if target in {"all", "local-mysql", "full-pipeline"}:
                checks.append(CheckResult("mysql login", "ok", "MySQL login ok"))
            if target in {"all", "spark-jdbc", "full-pipeline"}:
                checks.append(CheckResult("spark jdbc config", "ok", "JDBC config shape ok; write mode append"))
            if target in {"all", "kafka", "full-pipeline"}:
                checks.append(CheckResult("kafka bootstrap config", "ok", "Kafka bootstrap config shape ok"))
            if target == "full-pipeline":
                checks.append(CheckResult("streaming output mode", "warning", "SPARK_STREAM_OUTPUT_MODE must be append or update"))
            return checks

        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "MYSQL_HOST=127.0.0.1",
                        "MYSQL_PORT=3306",
                        "MYSQL_DATABASE=creatorpulse",
                        "MYSQL_USER=creatorpulse",
                        "MYSQL_PASSWORD=secret",
                        "SPARK_MYSQL_JDBC_URL=jdbc:mysql://127.0.0.1:3306/creatorpulse",
                        "SPARK_MYSQL_USER=creatorpulse",
                        "SPARK_MYSQL_PASSWORD=secret",
                        "SPARK_MYSQL_DRIVER=com.mysql.cj.jdbc.Driver",
                        "KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:9092",
                    ]
                ),
                encoding="utf-8",
            )
            with patch("scripts.status_mvp.run_checks", side_effect=fake_run_checks):
                status = build_status(env_file)

        self.assertIn("fullPipeline", status["preflight"])
        self.assertEqual(status["nextRecommendedStep"]["stage"], "full-pipeline-preflight")
        self.assertEqual(status["nextRecommendedStep"]["command"], "python scripts\\preflight.py --target full-pipeline --strict")
        self.assertIn("mysql", status["realServiceReadinessSummary"]["readyForExecuteStages"])
        self.assertIn("spark-jdbc", status["realServiceReadinessSummary"]["readyForExecuteStages"])
        self.assertIn("kafka", status["realServiceReadinessSummary"]["readyForExecuteStages"])
        self.assertIn("full-pipeline", status["realServiceReadinessSummary"]["readyForStrictPreflightStages"])
        self.assertIn("full-pipeline", status["realServiceReadinessSummary"]["blockedStages"])
        self.assertEqual(status["nextRolloutStage"], "full-pipeline")
        self.assertEqual(
            [step["name"] for step in status["nextRolloutPlan"]["steps"]],
            ["fullPipelinePreflight", "fullPipelineStreaming"],
        )
        self.assertIn("fullPipeline", status["realExecutionNextSteps"])


if __name__ == "__main__":
    unittest.main()
