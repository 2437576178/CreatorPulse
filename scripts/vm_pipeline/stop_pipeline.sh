#!/usr/bin/env bash
set -euo pipefail

DATA_HOME="${DATA_HOME:-/opt/creatorpulse/data}"
PID_DIR="${DATA_HOME}/pids"

stop_process() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -s "${pid_file}" ]]; then
    echo "${name} is not recorded."
    return
  fi

  local pid
  pid="$(cat "${pid_file}")"
  if kill -0 "${pid}" 2>/dev/null; then
    kill "${pid}" 2>/dev/null || true
    sleep 3
    if kill -0 "${pid}" 2>/dev/null; then
      kill -9 "${pid}" 2>/dev/null || true
    fi
    echo "Stopped ${name}: ${pid}"
  else
    echo "${name} was not running: ${pid}"
  fi
  rm -f "${pid_file}"
}

stop_process "Spark Streaming" "${PID_DIR}/creatorpulse-spark-streaming.pid"
stop_process "Mock generator" "${PID_DIR}/creatorpulse-mock-generator.pid"
stop_process "Flume" "${PID_DIR}/creatorpulse-flume.pid"

echo "Pipeline stopped."
