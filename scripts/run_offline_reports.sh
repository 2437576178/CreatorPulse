#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/creatorpulse/app}"
DATA_HOME="${DATA_HOME:-/opt/creatorpulse/data}"
LOG_DIR="${DATA_HOME}/logs"
ENV_FILE="${APP_HOME}/.env.generator"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "${LOG_DIR}"

REPORT_TYPE="${1:-DAILY}"
PERIOD_START="${2:-$(date -d yesterday +%F)}"
PERIOD_END="${3:-${PERIOD_START}}"
LOG_FILE="${LOG_DIR}/offline-reports-${REPORT_TYPE}-${PERIOD_START}-${PERIOD_END}.log"

cd "${APP_HOME}"
"${PYTHON_BIN}" "${APP_HOME}/spark_jobs/offline_reports.py" \
  --report-type "${REPORT_TYPE}" \
  --period-start "${PERIOD_START}" \
  --period-end "${PERIOD_END}" \
  --env-file "${ENV_FILE}" \
  --triggered-by SCHEDULED \
  --execute \
  >> "${LOG_FILE}" 2>&1

echo "Offline reports finished: ${REPORT_TYPE} ${PERIOD_START}..${PERIOD_END}"
echo "Log: ${LOG_FILE}"
