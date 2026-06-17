"""Tests for local MySQL setup orchestration."""

from __future__ import annotations

import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.setup_local_mysql import API_ENDPOINTS, run_setup, verify_mysql_row_counts  # noqa: E402
from scripts.preflight import CheckResult  # noqa: E402


class SetupLocalMySQLTest(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_env = {
            key: os.environ.get(key)
            for key in [
                "CREATORPULSE_DATA_SOURCE",
                "MYSQL_HOST",
                "MYSQL_PORT",
                "MYSQL_DATABASE",
                "MYSQL_USER",
                "MYSQL_PASSWORD",
            ]
        }
        for key in self.previous_env:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def make_env_file(self) -> Path:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        path = Path(tmpdir.name) / ".env"
        path.write_text(
            "\n".join(
                [
                    "MYSQL_HOST=127.0.0.1",
                    "MYSQL_PORT=3306",
                    "MYSQL_DATABASE=creatorpulse",
                    "MYSQL_USER=test_user",
                    "MYSQL_PASSWORD=test_password",
                ]
            ),
            encoding="utf-8",
        )
        return path

    def test_dry_run_validates_schema_rows_and_contract_without_mysql(self) -> None:
        result = run_setup(self.make_env_file(), ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json", False, False)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["mode"], "dry-run")
        self.assertEqual(result["contractCheck"], "ok")
        self.assertEqual(result["rows"]["videos"], 27)
        self.assertEqual(result["schema"]["createTables"], 13)
        self.assertEqual(result["executionPlan"]["willWriteMySQL"], False)
        self.assertEqual(
            result["executionPlan"]["steps"],
            [
                "local-mysql strict preflight",
                "apply schema statements",
                "upsert mock rows",
                "verify MySQL row counts",
                "verify Flask API in mysql mode",
            ],
        )
        self.assertEqual(result["executionPlan"]["targetTables"], 13)
        self.assertEqual(result["executionPlan"]["plannedRows"]["videos"], 27)

    def test_execute_applies_schema_imports_rows_and_verifies_api(self) -> None:
        preflight_ok = [
            CheckResult("env file", "ok", "configured"),
            CheckResult("mysql login", "ok", "login ok"),
        ]
        with patch("scripts.setup_local_mysql.run_checks", return_value=preflight_ok), patch(
            "scripts.setup_local_mysql.apply_schema"
        ) as apply_schema_mock, patch(
            "scripts.setup_local_mysql.write_mysql"
        ) as write_mysql_mock, patch(
            "scripts.setup_local_mysql.verify_mysql_row_counts"
        ) as verify_counts_mock, patch("scripts.setup_local_mysql.verify_mysql_api") as verify_api_mock:
            verify_counts_mock.return_value = {"creators": 1, "videos": 27}
            verify_api_mock.return_value = {endpoint: 200 for endpoint in API_ENDPOINTS}

            result = run_setup(
                self.make_env_file(),
                ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json",
                True,
                False,
            )

        apply_schema_mock.assert_called_once()
        write_mysql_mock.assert_called_once()
        verify_counts_mock.assert_called_once()
        verify_api_mock.assert_called_once()
        self.assertEqual(result["mode"], "mysql-setup")
        self.assertEqual(result["executionPlan"]["willWriteMySQL"], True)
        self.assertEqual(result["mysqlRowCounts"]["videos"], 27)
        self.assertEqual(result["apiStatusCodes"]["/api/health"], 200)

    def test_execute_requires_strict_preflight_even_without_flag(self) -> None:
        preflight_warning = [
            CheckResult("env MYSQL_USER", "warning", "placeholder value still present"),
            CheckResult("mysql login", "warning", "cannot verify login yet"),
        ]
        with patch("scripts.setup_local_mysql.run_checks", return_value=preflight_warning), patch(
            "scripts.setup_local_mysql.apply_schema"
        ) as apply_schema_mock, patch("scripts.setup_local_mysql.write_mysql") as write_mysql_mock:
            with self.assertRaisesRegex(RuntimeError, "Local MySQL preflight failed"):
                run_setup(
                    self.make_env_file(),
                    ROOT_DIR / "mvp_mock" / "data" / "creatorpulse_mvp_mock.json",
                    True,
                    False,
                )

        apply_schema_mock.assert_not_called()
        write_mysql_mock.assert_not_called()

    def test_cli_reports_preflight_failure_as_json_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "\n".join(
                    [
                        "MYSQL_HOST=127.0.0.1",
                        "MYSQL_PORT=3306",
                        "MYSQL_DATABASE=creatorpulse",
                        "MYSQL_USER=your_user",
                        "MYSQL_PASSWORD=your_password",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/setup_local_mysql.py",
                    "--env-file",
                    str(env_file),
                    "--execute",
                ],
                cwd=ROOT_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "failed")
        self.assertIn("Local MySQL preflight failed", payload["error"])

    def test_verify_mysql_row_counts_checks_every_expected_table(self) -> None:
        config = MagicMock()
        expected_counts = {"creators": 1, "videos": 27}
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(1,), (27,)]
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor

        with patch("scripts.setup_local_mysql.pymysql_connect", return_value=connection) as connect_mock:
            actual = verify_mysql_row_counts(expected_counts, config)

        self.assertEqual(actual, expected_counts)
        connect_mock.assert_called_once_with(config)
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertIn("`creators`", cursor.execute.call_args_list[0].args[0])
        self.assertIn("`videos`", cursor.execute.call_args_list[1].args[0])
        connection.close.assert_called_once()

    def test_verify_mysql_row_counts_fails_on_mismatch(self) -> None:
        config = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = (0,)
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor

        with patch("scripts.setup_local_mysql.pymysql_connect", return_value=connection):
            with self.assertRaisesRegex(RuntimeError, "MySQL row count mismatch"):
                verify_mysql_row_counts({"creators": 1}, config)


if __name__ == "__main__":
    unittest.main()
