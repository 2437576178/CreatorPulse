#!/usr/bin/env bash
set -euo pipefail

DATA_HOME="${DATA_HOME:-/opt/creatorpulse/data}"
LOG_DIR="${DATA_HOME}/logs"

echo "Offline logs: ${LOG_DIR}"
ls -1t \
  "${LOG_DIR}"/offline-daily-*.log \
  "${LOG_DIR}"/offline-reports-*.log \
  "${LOG_DIR}"/offline-recompute-worker.log \
  2>/dev/null | head -20 || true

echo
echo "Suggested cron:"
echo "10 0 * * * /opt/creatorpulse/app/scripts/run_offline_daily.sh"
echo "20 0 * * * /opt/creatorpulse/app/scripts/run_offline_reports.sh DAILY"
echo "30 0 * * 1 /opt/creatorpulse/app/scripts/run_offline_reports.sh WEEKLY \$(date -d 'last monday -7 days' +\\%F) \$(date -d 'last sunday' +\\%F)"
echo "40 0 1 * * /opt/creatorpulse/app/scripts/run_offline_reports.sh MONTHLY \$(date -d 'last month' +\\%Y-\\%m-01) \$(date -d \"\$(date +\\%Y-\\%m-01) -1 day\" +\\%F)"
echo "* * * * * /opt/creatorpulse/app/scripts/run_offline_recompute_worker.sh"
