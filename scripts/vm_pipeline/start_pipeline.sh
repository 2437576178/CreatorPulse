#!/usr/bin/env bash
set -euo pipefail

APP_HOME="${APP_HOME:-/opt/creatorpulse/app}"
DATA_HOME="${DATA_HOME:-/opt/creatorpulse/data}"
LOG_DIR="${DATA_HOME}/logs"
PID_DIR="${DATA_HOME}/pids"
SPOOL_DIR="${DATA_HOME}/flume_spool/video_stats"
GENERATOR_ENV="${APP_HOME}/.env.generator"

JAVA_HOME="${JAVA_HOME:-/usr/local/java/jdk1.8.0_201}"
SPARK_HOME="${SPARK_HOME:-/usr/local/spark-local}"
KAFKA_HOME="${KAFKA_HOME:-/usr/local/kafka_2.13-3.3.1}"
FLUME_HOME="${FLUME_HOME:-/usr/local/flume}"
PATH="${JAVA_HOME}/bin:${SPARK_HOME}/bin:${KAFKA_HOME}/bin:${FLUME_HOME}/bin:${PATH}"
export JAVA_HOME SPARK_HOME KAFKA_HOME FLUME_HOME PATH

MYSQL_HOST="${MYSQL_HOST:-192.168.88.1}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_DATABASE="${MYSQL_DATABASE:-creatorpulse}"
MYSQL_USER="${MYSQL_USER:-spark_user}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-spark_password}"

KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"
SPARK_STREAM_TRIGGER_SECONDS="${SPARK_STREAM_TRIGGER_SECONDS:-10}"
SPARK_STREAM_CHECKPOINT_DIR="${SPARK_STREAM_CHECKPOINT_DIR:-${DATA_HOME}/spark_checkpoints/video_stats_live}"
SPARK_STREAM_STARTING_OFFSETS="${SPARK_STREAM_STARTING_OFFSETS:-latest}"
SPARK_STREAM_RUN_PREFIX="${SPARK_STREAM_RUN_PREFIX:-kafka_stream_live_$(date +%Y%m%d_%H%M%S)}"
GENERATOR_BATCH_SIZE="${GENERATOR_BATCH_SIZE:-12}"
GENERATOR_INTERVAL="${GENERATOR_INTERVAL:-30}"

mkdir -p "${LOG_DIR}" "${PID_DIR}" "${SPOOL_DIR}" "$(dirname "${GENERATOR_ENV}")" "${SPARK_STREAM_CHECKPOINT_DIR}"

write_generator_env() {
  cat > "${GENERATOR_ENV}" <<ENV
MYSQL_HOST=${MYSQL_HOST}
MYSQL_PORT=${MYSQL_PORT}
MYSQL_DATABASE=${MYSQL_DATABASE}
MYSQL_USER=${MYSQL_USER}
MYSQL_PASSWORD=${MYSQL_PASSWORD}
ENV
  chmod 600 "${GENERATOR_ENV}"
}

is_running() {
  local pid_file="$1"
  [[ -s "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" 2>/dev/null
}

require_port() {
  local port="$1"
  local name="$2"
  if ! (netstat -lnt 2>/dev/null || ss -lnt 2>/dev/null) | grep -q ":${port} "; then
    echo "${name} is not listening on port ${port}" >&2
    exit 1
  fi
}

start_flume() {
  local pid_file="${PID_DIR}/creatorpulse-flume.pid"
  if is_running "${pid_file}"; then
    echo "Flume already running: $(cat "${pid_file}")"
    return
  fi

  nohup flume-ng agent \
    --name agent \
    --conf "${FLUME_HOME}/conf" \
    --conf-file "${APP_HOME}/flume/creatorpulse-video-stats.conf" \
    > "${LOG_DIR}/flume-video-stats.log" 2>&1 &
  echo $! > "${pid_file}"
  echo "Started Flume: $(cat "${pid_file}")"
}

start_generator() {
  local pid_file="${PID_DIR}/creatorpulse-mock-generator.pid"
  if is_running "${pid_file}"; then
    echo "Mock generator already running: $(cat "${pid_file}")"
    return
  fi

  nohup python3 "${APP_HOME}/mock_generator/generate_events.py" \
    --batch-size "${GENERATOR_BATCH_SIZE}" \
    --interval "${GENERATOR_INTERVAL}" \
    --env-file "${GENERATOR_ENV}" \
    --require-db \
    > "${LOG_DIR}/mock-generator.log" 2>&1 &
  echo $! > "${pid_file}"
  echo "Started mock generator: $(cat "${pid_file}")"
}

start_spark_streaming() {
  local pid_file="${PID_DIR}/creatorpulse-spark-streaming.pid"
  if is_running "${pid_file}"; then
    echo "Spark Streaming already running: $(cat "${pid_file}")"
    return
  fi

  export PYSPARK_PYTHON="${PYSPARK_PYTHON:-python3}"
  export PYSPARK_DRIVER_PYTHON="${PYSPARK_DRIVER_PYTHON:-python3}"
  export KAFKA_BOOTSTRAP_SERVERS
  export SPARK_MYSQL_JDBC_URL="jdbc:mysql://${MYSQL_HOST}:${MYSQL_PORT}/${MYSQL_DATABASE}?useSSL=false&characterEncoding=utf8&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true"
  export SPARK_MYSQL_USER="${MYSQL_USER}"
  export SPARK_MYSQL_PASSWORD="${MYSQL_PASSWORD}"
  export SPARK_MYSQL_DRIVER="${SPARK_MYSQL_DRIVER:-com.mysql.cj.jdbc.Driver}"
  export SPARK_MYSQL_WRITE_MODE="${SPARK_MYSQL_WRITE_MODE:-append}"
  export SPARK_STREAM_TRIGGER_SECONDS
  export SPARK_STREAM_CHECKPOINT_DIR
  export SPARK_STREAM_STARTING_OFFSETS
  export SPARK_STREAM_RUN_PREFIX

  nohup spark-submit --master local[2] \
    "${APP_HOME}/spark_jobs/kafka_streaming_to_mysql_py36.py" \
    > "${LOG_DIR}/spark-kafka-streaming.log" 2>&1 &
  echo $! > "${pid_file}"
  echo "Started Spark Streaming: $(cat "${pid_file}")"
}

write_generator_env
require_port 2181 "Zookeeper"
require_port 9092 "Kafka"

cd "${APP_HOME}"
start_flume
start_generator
start_spark_streaming

echo "Pipeline started."
echo "Logs: ${LOG_DIR}"
echo "PIDs: ${PID_DIR}"
