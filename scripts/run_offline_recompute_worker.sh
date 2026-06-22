#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/creatorpulse/app}"
DATA_HOME="${DATA_HOME:-/opt/creatorpulse/data}"
LOG_DIR="${DATA_HOME}/logs"
ENV_FILE="${APP_HOME}/.env.generator"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LIMIT="${LIMIT:-5}"

mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/offline-recompute-worker.log"

cd "${APP_HOME}"
"${PYTHON_BIN}" "${APP_HOME}/spark_jobs/offline_recompute_worker.py" \
  --env-file "${ENV_FILE}" \
  --limit "${LIMIT}" \
  >> "${LOG_FILE}" 2>&1

echo "Offline recompute worker finished."
echo "Log: ${LOG_FILE}"
