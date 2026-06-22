"""Tests for schema parsing and validation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DATABASE_DIR = ROOT_DIR / "database"
sys.path.insert(0, str(DATABASE_DIR))

from apply_schema import SchemaError, load_schema_statements, split_sql_statements, statement_counts  # noqa: E402


class ApplySchemaTest(unittest.TestCase):
    def test_loads_expected_schema_statements(self) -> None:
        statements = load_schema_statements()
        counts = statement_counts(statements)

        self.assertEqual(counts["createDatabase"], 1)
        self.assertEqual(counts["useDatabase"], 1)
        self.assertEqual(counts["createTables"], 22)
        self.assertEqual(counts["total"], 24)

    def test_schema_includes_offline_processing_tables(self) -> None:
        schema_sql = (DATABASE_DIR / "schema.sql").read_text(encoding="utf-8")

        expected_tables = [
            "raw_video_stat_events",
            "offline_creator_daily_metrics",
            "offline_platform_daily_metrics",
            "offline_video_daily_metrics",
            "offline_content_type_daily_metrics",
            "creator_reports",
            "offline_batch_runs",
            "offline_recompute_requests",
        ]

        for table_name in expected_tables:
            with self.subTest(table_name=table_name):
                self.assertIn(f"CREATE TABLE IF NOT EXISTS {table_name}", schema_sql)

        self.assertIn("UNIQUE KEY uk_offline_creator_daily_metrics_creator_date", schema_sql)
        self.assertIn("UNIQUE KEY uk_offline_platform_daily_metrics_creator_platform_date", schema_sql)
        self.assertIn("UNIQUE KEY uk_offline_video_daily_metrics_creator_video_date", schema_sql)
        self.assertIn("UNIQUE KEY uk_offline_content_type_daily_metrics_creator_type_date", schema_sql)
        self.assertIn("UNIQUE KEY uk_creator_reports_creator_type_period", schema_sql)
        self.assertIn("KEY idx_raw_video_stat_events_creator_date", schema_sql)
        self.assertIn("KEY idx_offline_batch_runs_status", schema_sql)

    def test_split_ignores_line_comments(self) -> None:
        statements = split_sql_statements(
            """
            -- comment
            CREATE DATABASE IF NOT EXISTS demo;
            USE demo;
            """
        )

        self.assertEqual(statements, ["CREATE DATABASE IF NOT EXISTS demo", "USE demo"])

    def test_rejects_trailing_statement_without_semicolon(self) -> None:
        with self.assertRaises(SchemaError):
            split_sql_statements("CREATE DATABASE IF NOT EXISTS demo")


if __name__ == "__main__":
    unittest.main()
