#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/creatorpulse/app}"
DATA_HOME="${DATA_HOME:-/opt/creatorpulse/data}"
LOG_DIR="${DATA_HOME}/logs"
ENV_FILE="${APP_HOME}/.env.generator"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "${LOG_DIR}"

TARGET_DATE="${1:-$(date -d yesterday +%F)}"
LOG_FILE="${LOG_DIR}/offline-daily-${TARGET_DATE}.log"

cd "${APP_HOME}"
"${PYTHON_BIN}" "${APP_HOME}/spark_jobs/offline_daily_metrics.py" \
  --start-date "${TARGET_DATE}" \
  --end-date "${TARGET_DATE}" \
  --env-file "${ENV_FILE}" \
  --triggered-by SCHEDULED \
  --execute \
  >> "${LOG_FILE}" 2>&1

echo "Offline daily metrics finished: ${TARGET_DATE}"
echo "Log: ${LOG_FILE}"
