"""Tests for the additional demo creator seed data."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DATABASE_DIR = ROOT_DIR / "database"
API_DIR = ROOT_DIR / "api"
sys.path.insert(0, str(DATABASE_DIR))
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(ROOT_DIR))

from mysql_repository import MySQLRepository  # noqa: E402
from seed_additional_creator import TECH_CREATOR, TECH_USER, build_rows  # noqa: E402
from view_model_contract import validate_view_models  # noqa: E402


class SeedAdditionalCreatorTest(unittest.TestCase):
    def test_builds_complete_creator_three_dataset(self) -> None:
        rows = build_rows()
        contract = MySQLRepository().to_contract(rows, TECH_CREATOR["creator_id"])

        self.assertEqual(TECH_USER["creator_id"], TECH_CREATOR["creator_id"])
        self.assertEqual(contract["creator"]["creatorId"], "creator_003")
        self.assertEqual(contract["creator"]["displayName"], "数码效率研究所")
        self.assertEqual({item["creatorId"] for item in contract["videos"]}, {"creator_003"})
        self.assertEqual({item["creatorId"] for item in contract["insights"]}, {"creator_003"})
        self.assertEqual({item["creatorId"] for item in contract["sparkOutputs"]["platformMetricSummaries"]}, {"creator_003"})
        self.assertGreaterEqual(len(contract["videos"]), 24)
        self.assertGreaterEqual(len(contract["insights"]), 20)
        validate_view_models(contract["viewModels"])


if __name__ == "__main__":
    unittest.main()
