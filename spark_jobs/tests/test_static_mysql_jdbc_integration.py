"""Optional live Spark JDBC integration test.

This test is skipped unless .env contains real SPARK_MYSQL_* values and
CREATORPULSE_RUN_SPARK_JDBC_LIVE=1 is set. It runs the static Spark job through
spark-submit and writes the two MVP Spark result tables through JDBC.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from spark_jobs.static_mock_to_mysql import DEFAULT_ENV_PATH, load_env_file  # noqa: E402


PLACEHOLDER_VALUES = {"your_user", "your_password"}
SPARK_JDBC_KEYS = [
    "SPARK_MYSQL_JDBC_URL",
    "SPARK_MYSQL_USER",
    "SPARK_MYSQL_PASSWORD",
    "SPARK_MYSQL_DRIVER",
]


def spark_jdbc_env_ready() -> tuple[bool, str]:
    load_env_file(DEFAULT_ENV_PATH)
    if os.environ.get("CREATORPULSE_RUN_SPARK_JDBC_LIVE") != "1":
        return False, "set CREATORPULSE_RUN_SPARK_JDBC_LIVE=1 to allow live Spark JDBC writes"

    if not DEFAULT_ENV_PATH.exists():
        return False, ".env not found"

    missing = [key for key in SPARK_JDBC_KEYS if not os.environ.get(key)]
    if missing:
        return False, f"missing Spark JDBC config: {', '.join(missing)}"

    placeholders = [key for key in SPARK_JDBC_KEYS if os.environ.get(key) in PLACEHOLDER_VALUES]
    if placeholders:
        return False, f"placeholder Spark JDBC config: {', '.join(placeholders)}"

    if shutil.which("spark-submit") is None:
        return False, "spark-submit not found on PATH"

    return True, "ready"


class SparkJDBCIntegrationTest(unittest.TestCase):
    def test_skip_helper_requires_explicit_opt_in(self) -> None:
        original = os.environ.pop("CREATORPULSE_RUN_SPARK_JDBC_LIVE", None)
        try:
            ready, reason = spark_jdbc_env_ready()
        finally:
            if original is not None:
                os.environ["CREATORPULSE_RUN_SPARK_JDBC_LIVE"] = original

        self.assertFalse(ready)
        self.assertIn("CREATORPULSE_RUN_SPARK_JDBC_LIVE=1", reason)

    def test_live_static_spark_job_writes_jdbc_tables(self) -> None:
        ready, reason = spark_jdbc_env_ready()
        if not ready:
            self.skipTest(f"Live Spark JDBC integration skipped: {reason}")

        result = subprocess.run(
            [
                "spark-submit",
                str(ROOT_DIR / "spark_jobs" / "static_mock_to_mysql.py"),
                "--execute",
                "--run-id",
                "spark_live_integration_test",
            ],
            cwd=ROOT_DIR,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "spark-jdbc-write")
        self.assertEqual(payload["counts"]["spark_platform_metric_summaries"], 3)
        self.assertEqual(payload["counts"]["spark_video_follower_contributions"], 10)


if __name__ == "__main__":
    unittest.main()
