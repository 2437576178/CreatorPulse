"""Tests for local preflight checks."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.preflight import (  # noqa: E402
    check_database_name_alignment,
    check_env_values,
    check_kafka_bootstrap_config,
    check_mysql_login,
    check_spark_jdbc_config,
    load_env,
    parse_jdbc_database_name,
    parse_host_port,
    run_checks,
    summarize,
)


class PreflightTest(unittest.TestCase):
    def test_loads_env_file_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".env"
            path.write_text("MYSQL_HOST=127.0.0.1\nMYSQL_PORT=3306\n", encoding="utf-8")

            values = load_env(path)

        self.assertEqual(values["MYSQL_HOST"], "127.0.0.1")
        self.assertEqual(values["MYSQL_PORT"], "3306")

    def test_parse_host_port(self) -> None:
        self.assertEqual(parse_host_port("node1:9092"), ("node1", 9092))
        self.assertIsNone(parse_host_port("node1"))
        self.assertIsNone(parse_host_port("node1:not-a-port"))

    def test_parse_jdbc_database_name(self) -> None:
        self.assertEqual(parse_jdbc_database_name("jdbc:mysql://127.0.0.1:3306/creatorpulse"), "creatorpulse")
        self.assertEqual(parse_jdbc_database_name("jdbc:mysql://node1:3306/creatorpulse?useSSL=false"), "creatorpulse")
        self.assertIsNone(parse_jdbc_database_name("mysql://127.0.0.1:3306/creatorpulse"))
        self.assertIsNone(parse_jdbc_database_name("jdbc:mysql://127.0.0.1:3306/"))

    def test_env_placeholder_is_warning(self) -> None:
        results = check_env_values({"MYSQL_USER": "your_user"})
        user_result = next(item for item in results if item.name == "env MYSQL_USER")

        self.assertEqual(user_result.status, "warning")

    def test_summarize_reports_errors(self) -> None:
        class Result:
            def __init__(self, status: str) -> None:
                self.status = status

        summary = summarize([Result("ok"), Result("warning"), Result("error")])

        self.assertEqual(summary["status"], "failed")
        self.assertEqual(summary["counts"]["warning"], 1)

    def test_local_mysql_target_does_not_check_kafka_or_spark(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".env"
            path.write_text(
                "\n".join(
                    [
                        "MYSQL_HOST=127.0.0.1",
                        "MYSQL_PORT=3306",
                        "MYSQL_DATABASE=creatorpulse",
                        "MYSQL_USER=local_user",
                        "MYSQL_PASSWORD=local_password",
                    ]
                ),
                encoding="utf-8",
            )

            results = run_checks(path, target="local-mysql")

        names = {item.name for item in results}
        self.assertIn("env MYSQL_HOST", names)
        self.assertIn("mysql tcp", names)
        self.assertNotIn("env KAFKA_BOOTSTRAP_SERVERS", names)
        self.assertNotIn("spark-submit", names)

    def test_spark_jdbc_target_does_not_check_kafka_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".env"
            path.write_text(
                "\n".join(
                    [
                        "SPARK_MYSQL_JDBC_URL=jdbc:mysql://127.0.0.1:3306/creatorpulse",
                        "SPARK_MYSQL_USER=spark_user",
                        "SPARK_MYSQL_PASSWORD=spark_password",
                        "SPARK_MYSQL_DRIVER=com.mysql.cj.jdbc.Driver",
                    ]
                ),
                encoding="utf-8",
            )

            results = run_checks(path, target="spark-jdbc")

        names = {item.name for item in results}
        self.assertIn("spark-submit", names)
        self.assertIn("mysql tcp", names)
        self.assertIn("env SPARK_MYSQL_JDBC_URL", names)
        self.assertNotIn("env KAFKA_BOOTSTRAP_SERVERS", names)

    def test_kafka_target_does_not_check_mysql_or_spark_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".env"
            path.write_text("KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:9092\n", encoding="utf-8")

            results = run_checks(path, target="kafka")

        names = {item.name for item in results}
        self.assertIn("kafka tcp", names)
        self.assertIn("env KAFKA_BOOTSTRAP_SERVERS", names)
        self.assertNotIn("mysql tcp", names)
        self.assertNotIn("spark-submit", names)
        self.assertNotIn("env MYSQL_HOST", names)

    def test_mysql_login_skips_when_credentials_are_placeholder(self) -> None:
        result = check_mysql_login(
            {
                "MYSQL_HOST": "127.0.0.1",
                "MYSQL_PORT": "3306",
                "MYSQL_DATABASE": "creatorpulse",
                "MYSQL_USER": "your_user",
                "MYSQL_PASSWORD": "your_password",
            }
        )

        self.assertEqual(result.status, "warning")
        self.assertIn("placeholder", result.message)

    def test_mysql_login_runs_select_one_with_real_credentials(self) -> None:
        cursor = Mock()
        cursor.fetchone.side_effect = [(1,), (1,)]
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor

        with patch("scripts.preflight.pymysql_connect", return_value=connection) as connect_mock:
            result = check_mysql_login(
                {
                    "MYSQL_HOST": "127.0.0.1",
                    "MYSQL_PORT": "3306",
                    "MYSQL_DATABASE": "creatorpulse",
                    "MYSQL_USER": "real_user",
                    "MYSQL_PASSWORD": "real_password",
                }
            )

        self.assertEqual(result.status, "ok")
        connect_mock.assert_called_once()
        self.assertEqual(cursor.execute.call_args_list[0].args[0], "SELECT 1")
        self.assertIn("SCHEMA_NAME", cursor.execute.call_args_list[1].args[0])
        connection.close.assert_called_once()

    def test_local_mysql_target_includes_login_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".env"
            path.write_text(
                "\n".join(
                    [
                        "MYSQL_HOST=127.0.0.1",
                        "MYSQL_PORT=3306",
                        "MYSQL_DATABASE=creatorpulse",
                        "MYSQL_USER=local_user",
                        "MYSQL_PASSWORD=local_password",
                    ]
                ),
                encoding="utf-8",
            )

            with patch("scripts.preflight.check_mysql_login") as login_check:
                login_check.return_value.name = "mysql login"
                login_check.return_value.status = "ok"
                login_check.return_value.message = "login ok"
                results = run_checks(path, target="local-mysql")

        names = {item.name for item in results}
        self.assertIn("mysql login", names)

    def test_spark_jdbc_config_accepts_mysql_jdbc_url_driver_and_mode(self) -> None:
        result = check_spark_jdbc_config(
            {
                "SPARK_MYSQL_JDBC_URL": "jdbc:mysql://127.0.0.1:3306/creatorpulse",
                "SPARK_MYSQL_USER": "spark_user",
                "SPARK_MYSQL_PASSWORD": "spark_password",
                "SPARK_MYSQL_DRIVER": "com.mysql.cj.jdbc.Driver",
                "SPARK_MYSQL_WRITE_MODE": "append",
            }
        )

        self.assertEqual(result.status, "ok")

    def test_spark_jdbc_config_rejects_bad_url_driver_or_write_mode(self) -> None:
        result = check_spark_jdbc_config(
            {
                "SPARK_MYSQL_JDBC_URL": "mysql://127.0.0.1:3306/creatorpulse",
                "SPARK_MYSQL_USER": "spark_user",
                "SPARK_MYSQL_PASSWORD": "spark_password",
                "SPARK_MYSQL_DRIVER": "org.postgresql.Driver",
                "SPARK_MYSQL_WRITE_MODE": "overwrite",
            }
        )

        self.assertEqual(result.status, "warning")
        self.assertIn("JDBC URL", result.message)
        self.assertIn("driver", result.message)
        self.assertIn("write mode", result.message)

    def test_spark_jdbc_target_includes_config_shape_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".env"
            path.write_text(
                "\n".join(
                    [
                        "SPARK_MYSQL_JDBC_URL=jdbc:mysql://127.0.0.1:3306/creatorpulse",
                        "SPARK_MYSQL_USER=spark_user",
                        "SPARK_MYSQL_PASSWORD=spark_password",
                        "SPARK_MYSQL_DRIVER=com.mysql.cj.jdbc.Driver",
                        "SPARK_MYSQL_WRITE_MODE=append",
                    ]
                ),
                encoding="utf-8",
            )

            results = run_checks(path, target="spark-jdbc")

        names = {item.name for item in results}
        self.assertIn("spark jdbc config", names)

    def test_database_name_alignment_accepts_matching_mysql_and_jdbc_database(self) -> None:
        result = check_database_name_alignment(
            {
                "MYSQL_DATABASE": "creatorpulse",
                "SPARK_MYSQL_JDBC_URL": "jdbc:mysql://192.168.1.10:3306/creatorpulse?useSSL=false",
            }
        )

        self.assertEqual(result.status, "ok")

    def test_database_name_alignment_warns_when_mysql_and_jdbc_database_differ(self) -> None:
        result = check_database_name_alignment(
            {
                "MYSQL_DATABASE": "creatorpulse",
                "SPARK_MYSQL_JDBC_URL": "jdbc:mysql://192.168.1.10:3306/creatorpulse_stage",
            }
        )

        self.assertEqual(result.status, "warning")
        self.assertIn("MYSQL_DATABASE", result.message)
        self.assertIn("SPARK_MYSQL_JDBC_URL", result.message)

    def test_kafka_bootstrap_config_rejects_placeholder_or_bad_shape(self) -> None:
        for value in ["192.168.56.10:9092", "node1", "node1:not-a-port", ":9092"]:
            with self.subTest(value=value):
                result = check_kafka_bootstrap_config({"KAFKA_BOOTSTRAP_SERVERS": value})
                self.assertEqual(result.status, "warning")

    def test_kafka_target_includes_bootstrap_config_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".env"
            path.write_text("KAFKA_BOOTSTRAP_SERVERS=10.0.0.5:9092\n", encoding="utf-8")

            results = run_checks(path, target="kafka")

        names = {item.name for item in results}
        self.assertIn("kafka bootstrap config", names)

    def test_full_pipeline_target_checks_mysql_spark_and_kafka_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".env"
            path.write_text(
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
                        "SPARK_MYSQL_WRITE_MODE=append",
                        "KAFKA_BOOTSTRAP_SERVERS=10.0.0.5:9092",
                    ]
                ),
                encoding="utf-8",
            )

            results = run_checks(path, target="full-pipeline")

        names = {item.name for item in results}
        self.assertIn("mysql tcp", names)
        self.assertIn("mysql login", names)
        self.assertIn("spark-submit", names)
        self.assertIn("spark jdbc config", names)
        self.assertIn("kafka tcp", names)
        self.assertIn("kafka bootstrap config", names)
        self.assertIn("streaming output mode", names)
        self.assertIn("database name alignment", names)


if __name__ == "__main__":
    unittest.main()
