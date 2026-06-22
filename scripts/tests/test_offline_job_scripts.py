"""Static checks for offline job shell scripts."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT_DIR / "scripts"


class OfflineJobScriptsTest(unittest.TestCase):
    def test_daily_script_runs_execute_mode(self) -> None:
        content = (SCRIPT_DIR / "run_offline_daily.sh").read_text(encoding="utf-8")

        self.assertIn("set -euo pipefail", content)
        self.assertIn("offline_daily_metrics.py", content)
        self.assertIn("--triggered-by SCHEDULED", content)
        self.assertIn("--execute", content)
        self.assertIn("offline-daily-", content)

    def test_reports_script_runs_execute_mode(self) -> None:
        content = (SCRIPT_DIR / "run_offline_reports.sh").read_text(encoding="utf-8")

        self.assertIn("offline_reports.py", content)
        self.assertIn("--report-type", content)
        self.assertIn("--period-start", content)
        self.assertIn("--execute", content)

    def test_recompute_worker_script_processes_requests(self) -> None:
        content = (SCRIPT_DIR / "run_offline_recompute_worker.sh").read_text(encoding="utf-8")

        self.assertIn("offline_recompute_worker.py", content)
        self.assertIn("--limit", content)
        self.assertIn("offline-recompute-worker.log", content)

    def test_status_script_documents_cron(self) -> None:
        content = (SCRIPT_DIR / "status_offline_jobs.sh").read_text(encoding="utf-8")

        self.assertIn("Suggested cron", content)
        self.assertIn("run_offline_daily.sh", content)
        self.assertIn("run_offline_reports.sh DAILY", content)
        self.assertIn("run_offline_recompute_worker.sh", content)


if __name__ == "__main__":
    unittest.main()
