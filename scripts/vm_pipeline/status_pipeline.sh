#!/usr/bin/env bash
set -euo pipefail

DATA_HOME="${DATA_HOME:-/opt/creatorpulse/data}"
PID_DIR="${DATA_HOME}/pids"
LOG_DIR="${DATA_HOME}/logs"

show_process() {
  local name="$1"
  local pid_file="$2"

  if [[ -s "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; then
    echo "${name}: running pid=$(cat "${pid_file}")"
  elif [[ -s "${pid_file}" ]]; then
    echo "${name}: stale pid=$(cat "${pid_file}")"
  else
    echo "${name}: stopped"
  fi
}

show_process "Flume" "${PID_DIR}/creatorpulse-flume.pid"
show_process "Mock generator" "${PID_DIR}/creatorpulse-mock-generator.pid"
show_process "Spark Streaming" "${PID_DIR}/creatorpulse-spark-streaming.pid"

echo "Logs: ${LOG_DIR}"
ls -1 "${LOG_DIR}"/flume-video-stats.log "${LOG_DIR}"/mock-generator.log "${LOG_DIR}"/spark-kafka-streaming.log 2>/dev/null || true
