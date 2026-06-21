"""Tests for CreatorPulse API repository selection."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from config import ConfigError, get_data_source  # noqa: E402
from mock_repository import MockRepository  # noqa: E402
from mysql_repository import MySQLRepository  # noqa: E402
from repository import clear_repository_cache, get_repository  # noqa: E402


class RepositoryFactoryTest(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("CREATORPULSE_DATA_SOURCE", None)
        clear_repository_cache()

    def test_defaults_to_mock_repository(self) -> None:
        os.environ.pop("CREATORPULSE_DATA_SOURCE", None)
        clear_repository_cache()

        with patch("config.load_env_file"):
            repository = get_repository()
            data_source = get_data_source()

        self.assertIsInstance(repository, MockRepository)
        self.assertEqual(data_source, "mock")

    def test_can_select_mysql_repository_without_connecting(self) -> None:
        os.environ["CREATORPULSE_DATA_SOURCE"] = "mysql"
        clear_repository_cache()

        repository = get_repository()

        self.assertIsInstance(repository, MySQLRepository)

    def test_rejects_unknown_data_source(self) -> None:
        os.environ["CREATORPULSE_DATA_SOURCE"] = "kafka"
        clear_repository_cache()

        with self.assertRaises(ConfigError):
            get_repository()


if __name__ == "__main__":
    unittest.main()
