"""Tests for offline recompute worker orchestration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import call, patch


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from spark_jobs.offline_recompute_worker import process_request, update_request_status  # noqa: E402


class OfflineRecomputeWorkerTest(unittest.TestCase):
    def test_update_request_status_does_not_require_batch_run_when_marking_running(self) -> None:
        connection = FakeConnection()
        config = object()
        with patch("spark_jobs.offline_recompute_worker.connect_mysql", return_value=connection):
            update_request_status(config, "req_001", "RUNNING", mark_started=True)

        sql, values = connection.cursor_obj.executed[0]
        self.assertIn("status = %s", sql)
        self.assertIn("started_at = %s", sql)
        self.assertEqual(values[0], "RUNNING")
        self.assertIsNone(values[1])
        self.assertEqual(values[-1], "req_001")
        self.assertTrue(connection.committed)

    def test_process_request_runs_daily_then_reports_for_all_scope(self) -> None:
        request = {
            "request_id": "req_001",
            "creator_id": "creator_001",
            "period_start": "2026-06-14",
            "period_end": "2026-06-14",
            "recompute_scope": "ALL",
        }
        config = object()

        with (
            patch("spark_jobs.offline_recompute_worker.update_request_status") as update_mock,
            patch("spark_jobs.offline_recompute_worker.run_daily_recompute", return_value={"offline_creator_daily_metrics": 1}) as daily_mock,
            patch("spark_jobs.offline_recompute_worker.run_report_recompute", return_value={"creator_reports": 3}) as report_mock,
        ):
            result = process_request(config, request)

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["counts"]["offline_creator_daily_metrics"], 1)
        self.assertEqual(result["counts"]["creator_reports"], 3)
        daily_mock.assert_called_once()
        report_mock.assert_called_once()
        first_call = update_mock.call_args_list[0]
        self.assertEqual(first_call, call(config, "req_001", "RUNNING", mark_started=True))
        self.assertEqual(update_mock.call_args_list[-1].kwargs["batch_run_id"], result["batchRunId"])
        self.assertTrue(update_mock.call_args_list[-1].kwargs["mark_finished"])


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, list[object]]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, sql: str, values: list[object]) -> None:
        self.executed.append((sql, values))


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_obj = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


if __name__ == "__main__":
    unittest.main()
