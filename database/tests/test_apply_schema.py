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
        self.assertEqual(counts["createTables"], 14)
        self.assertEqual(counts["total"], 16)

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
