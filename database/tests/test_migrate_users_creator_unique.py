"""Tests for users.creator_id uniqueness migration safeguards."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT_DIR = Path(__file__).resolve().parents[2]
DATABASE_DIR = ROOT_DIR / "database"
sys.path.insert(0, str(DATABASE_DIR))

from migrate_users_creator_unique import migrate_users_creator_unique  # noqa: E402


class MigrateUsersCreatorUniqueTest(unittest.TestCase):
    @patch("pymysql.connect")
    def test_rejects_duplicate_creator_bindings_before_altering_table(self, connect: MagicMock) -> None:
        connection = connect.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = (("creator_001", 2),)

        with self.assertRaisesRegex(RuntimeError, "duplicate users.creator_id"):
            migrate_users_creator_unique(
                MagicMock(host="127.0.0.1", port=3306, user="u", password="p", database="creatorpulse")
            )

        executed_sql = " ".join(call.args[0] for call in cursor.execute.call_args_list)
        self.assertNotIn("ALTER TABLE users ADD UNIQUE KEY", executed_sql)
        connection.rollback.assert_called_once()

    @patch("pymysql.connect")
    def test_creates_unique_key_without_dropping_foreign_key_support_index(self, connect: MagicMock) -> None:
        connection = connect.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = ()
        cursor.fetchone.return_value = (0,)

        result = migrate_users_creator_unique(
            MagicMock(host="127.0.0.1", port=3306, user="u", password="p", database="creatorpulse")
        )

        executed_sql = " ".join(call.args[0] for call in cursor.execute.call_args_list)
        self.assertEqual(result, {"usersCreatorUniqueKey": "created"})
        self.assertNotIn("ALTER TABLE users DROP INDEX idx_users_creator", executed_sql)
        self.assertIn("ALTER TABLE users ADD UNIQUE KEY uk_users_creator", executed_sql)
        connection.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
