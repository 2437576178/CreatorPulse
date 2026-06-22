"""Tests for MySQL row-to-contract mapping without a live database."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.import_mock_to_mysql import build_table_rows, load_json  # noqa: E402
from mysql_repository import MySQLRepository  # noqa: E402
from registration_service import seed_registered_creator_rows  # noqa: E402


class MySQLRepositoryMappingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mock_data = load_json()
        cls.table_rows = build_table_rows(cls.mock_data)
        cls.contract = MySQLRepository().to_contract(cls.table_rows)

    def test_restores_core_contract_counts(self) -> None:
        self.assertEqual(self.contract["creator"]["creatorId"], "creator_001")
        self.assertEqual(len(self.contract["platformAccounts"]), 3)
        self.assertEqual(len(self.contract["videos"]), 27)
        self.assertEqual(len(self.contract["videoMetricSnapshots"]), 27)
        self.assertEqual(len(self.contract["videoTrafficSourceMetrics"]), 135)
        self.assertEqual(len(self.contract["creatorMetricSnapshots"]), 7)
        self.assertEqual(len(self.contract["topicTrendSnapshots"]), 10)
        self.assertGreaterEqual(len(self.contract["insights"]), 5)
        self.assertEqual({item["generatedBy"] for item in self.contract["insights"]}, {"SPARK_RULE_ENGINE"})
        self.assertEqual(len(self.contract["sparkOutputs"]["platformMetricSummaries"]), 3)
        self.assertEqual(len(self.contract["sparkOutputs"]["videoFollowerContributions"]), 10)

    def test_restores_view_model_shape(self) -> None:
        view_models = self.contract["viewModels"]

        self.assertIn("growthDashboard", view_models)
        self.assertIn("fansAnalysis", view_models)
        self.assertIn("videoAnalysis", view_models)
        self.assertIn("contentDistribution", view_models)
        self.assertIn("opportunities", view_models)
        self.assertIn("profile", view_models)
        self.assertTrue(view_models["growthDashboard"]["topVideos"])
        self.assertTrue(view_models["fansAnalysis"]["audienceProfile"])
        self.assertTrue(view_models["opportunities"]["topics"])
        self.assertEqual(len(view_models["videoAnalysis"]["sparkContributions"]), 10)
        self.assertEqual(len(view_models["contentDistribution"]["sparkPlatformSummaries"]), 3)

    def test_restores_insight_children(self) -> None:
        insight = self.contract["insights"][0]

        self.assertIn("evidenceMetrics", insight)
        self.assertIn("recommendedActions", insight)
        self.assertGreaterEqual(len(insight["evidenceMetrics"]), 2)
        self.assertGreaterEqual(len(insight["recommendedActions"]), 1)

    def test_filters_contract_rows_by_creator_id(self) -> None:
        second_creator_rows = clone_rows_for_second_creator(self.table_rows)
        rows = {table: self.table_rows[table] + second_creator_rows[table] for table in self.table_rows}

        contract = MySQLRepository().to_contract(rows, "creator_002")

        self.assertEqual(contract["creator"]["creatorId"], "creator_002")
        self.assertTrue(contract["videos"])
        self.assertTrue(contract["insights"])
        self.assertTrue(contract["sparkOutputs"]["videoFollowerContributions"])
        self.assertEqual({item["creatorId"] for item in contract["platformAccounts"]}, {"creator_002"})
        self.assertEqual({item["creatorId"] for item in contract["videos"]}, {"creator_002"})
        self.assertEqual({item["creatorId"] for item in contract["videoMetricSnapshots"]}, {"creator_002"})
        self.assertEqual({item["creatorId"] for item in contract["creatorMetricSnapshots"]}, {"creator_002"})
        self.assertEqual({item["creatorId"] for item in contract["insights"]}, {"creator_002"})
        self.assertEqual({item["creatorId"] for item in contract["sparkOutputs"]["platformMetricSummaries"]}, {"creator_002"})

    def test_registered_profile_only_creator_gets_empty_metric_view_models(self) -> None:
        rows = seed_registered_creator_rows("creator_profile_only", "Profile Only", ["DOUYIN", "BILIBILI"])

        contract = MySQLRepository().to_contract(rows, "creator_profile_only")
        view_models = contract["viewModels"]

        self.assertEqual(contract["creator"]["creatorId"], "creator_profile_only")
        self.assertTrue(contract["videos"])
        self.assertEqual(contract["videoMetricSnapshots"], [])
        self.assertEqual(contract["creatorMetricSnapshots"], [])
        self.assertEqual(view_models["growthDashboard"]["topVideos"], [])
        self.assertEqual(view_models["growthDashboard"]["currentSnapshot"]["dataStatus"], "WAITING_FOR_EVENTS")
        self.assertEqual(view_models["fansAnalysis"]["trend"][0]["dataStatus"], "WAITING_FOR_EVENTS")
        self.assertEqual(view_models["videoAnalysis"]["sparkContributions"], [])
        self.assertEqual(view_models["contentDistribution"]["sparkPlatformSummaries"], [])

    def test_growth_total_followers_comes_from_platform_accounts(self) -> None:
        rows = {table: [dict(row) for row in table_rows] for table, table_rows in self.table_rows.items()}
        for index, row in enumerate(rows["platform_accounts"]):
            row["follower_count"] = (index + 1) * 1000
        latest_creator_snapshot = rows["creator_metric_snapshots"][-1]
        latest_creator_snapshot["total_followers"] = 9

        contract = MySQLRepository().to_contract(rows, "creator_001")

        self.assertEqual(contract["viewModels"]["growthDashboard"]["totalFollowers"], 6000)
        self.assertEqual(contract["viewModels"]["growthDashboard"]["currentSnapshot"]["totalFollowers"], 6000)

    def test_growth_top_kpis_expose_totals_and_deltas(self) -> None:
        contract = MySQLRepository().to_contract(self.table_rows, "creator_001")
        growth = contract["viewModels"]["growthDashboard"]

        self.assertEqual(growth["platformCount"], len(contract["platformAccounts"]))
        self.assertEqual(growth["newPlatformCount"], 0)
        self.assertEqual(growth["videoCount"], len(contract["videos"]))
        self.assertIsInstance(growth["newVideoCount"], int)
        self.assertEqual(growth["totalViews"], sum(row["views"] for row in contract["videoMetricSnapshots"]))
        self.assertGreaterEqual(growth["newViews"], 0)
        self.assertEqual(growth["totalFollowers"], sum(row["followerCount"] for row in contract["platformAccounts"]))

    def test_api_contract_exposes_latest_metric_snapshots_and_latest_spark_rows_only(self) -> None:
        rows = {table: [dict(row) for row in table_rows] for table, table_rows in self.table_rows.items()}
        first_video = rows["video_metric_snapshots"][0]
        rows["video_metric_snapshots"].append(
            {
                **first_video,
                "snapshot_id": f"{first_video['snapshot_id']}_older",
                "views": 1,
                "new_followers": 0,
                "collected_at": "2026-01-01 00:00:00",
            }
        )

        rows["spark_platform_metric_summaries"].extend(
            [
                {
                    **row,
                    "run_id": "older_platform_run",
                    "total_views": 1,
                    "new_followers": 0,
                    "calculated_at": "2026-01-01 00:00:00",
                }
                for row in rows["spark_platform_metric_summaries"]
            ]
        )
        stale_platform = {
            **rows["spark_platform_metric_summaries"][0],
            "run_id": "newer_stale_platform_run",
            "platform": rows["spark_platform_metric_summaries"][0]["platform"],
            "total_views": 2,
            "new_followers": 0,
            "calculated_at": "2027-01-02 00:00:00",
        }
        rows["spark_platform_metric_summaries"].append(stale_platform)
        rows["spark_video_follower_contributions"].extend(
            [
                {
                    **row,
                    "run_id": "older_contribution_run",
                    "views": 1,
                    "new_followers": 0,
                    "calculated_at": "2026-01-01 00:00:00",
                }
                for row in rows["spark_video_follower_contributions"]
            ]
        )
        stale_contribution = {
            **rows["spark_video_follower_contributions"][0],
            "run_id": "newer_stale_contribution_run",
            "views": 2,
            "new_followers": 0,
            "calculated_at": "2027-01-02 00:00:00",
        }
        rows["spark_video_follower_contributions"].append(stale_contribution)

        contract = MySQLRepository().to_contract(rows, "creator_001")

        snapshots_for_first_video = [item for item in contract["videoMetricSnapshots"] if item["videoId"] == first_video["video_id"]]
        self.assertEqual(len(snapshots_for_first_video), 1)
        self.assertNotEqual(snapshots_for_first_video[0]["views"], 1)
        self.assertEqual(len(contract["sparkOutputs"]["platformMetricSummaries"]), 3)
        self.assertIn("newer_stale_platform_run", {item["runId"] for item in contract["sparkOutputs"]["platformMetricSummaries"]})
        self.assertNotIn("older_platform_run", {item["runId"] for item in contract["sparkOutputs"]["platformMetricSummaries"]})
        self.assertEqual(
            len({item["platform"] for item in contract["sparkOutputs"]["platformMetricSummaries"]}),
            len(contract["sparkOutputs"]["platformMetricSummaries"]),
        )
        self.assertEqual(len(contract["sparkOutputs"]["videoFollowerContributions"]), 10)
        self.assertIn("newer_stale_contribution_run", {item["runId"] for item in contract["sparkOutputs"]["videoFollowerContributions"]})
        self.assertNotIn("older_contribution_run", {item["runId"] for item in contract["sparkOutputs"]["videoFollowerContributions"]})
        self.assertEqual(
            len({item["videoId"] for item in contract["sparkOutputs"]["videoFollowerContributions"]}),
            len(contract["sparkOutputs"]["videoFollowerContributions"]),
        )


def clone_rows_for_second_creator(rows: dict[str, list[dict]]) -> dict[str, list[dict]]:
    cloned = {table: [] for table in rows}
    id_map: dict[str, str] = {}

    def remap(value: str | None) -> str | None:
        if value is None:
            return None
        if value not in id_map:
            id_map[value] = f"{value}_c2"
        return id_map[value]

    for row in rows["creators"]:
        cloned["creators"].append({**row, "creator_id": "creator_002", "display_name": "第二个达人"})

    for table in [
        "platform_accounts",
        "videos",
        "video_metric_snapshots",
        "creator_metric_snapshots",
        "audience_profile_snapshots",
        "insights",
        "spark_platform_metric_summaries",
        "spark_video_follower_contributions",
    ]:
        for row in rows[table]:
            next_row = {**row, "creator_id": "creator_002"}
            for column in ["account_id", "video_id", "snapshot_id", "insight_id", "action_id", "run_id"]:
                if column in next_row:
                    next_row[column] = remap(next_row[column])
            if table == "spark_video_follower_contributions":
                next_row["rank_position"] = row["rank_position"]
            cloned[table].append(next_row)

    for row in rows["video_traffic_source_metrics"]:
        cloned["video_traffic_source_metrics"].append({**row, "video_id": remap(row["video_id"])})

    for row in rows["insight_evidence_metrics"]:
        cloned["insight_evidence_metrics"].append({**row, "insight_id": remap(row["insight_id"])})

    for row in rows["recommended_actions"]:
        cloned["recommended_actions"].append(
            {**row, "action_id": remap(row["action_id"]), "insight_id": remap(row["insight_id"])}
        )

    cloned["topic_trend_snapshots"] = []
    return cloned


if __name__ == "__main__":
    unittest.main()
