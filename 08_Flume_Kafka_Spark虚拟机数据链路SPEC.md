# CreatorPulse Flume/Kafka/Spark 虚拟机数据链路 SPEC

## 1. 目标

本 SPEC 固定 CreatorPulse 后续数据生产链路的实施方式：在不重做前端和 Flask API 的前提下，把当前“mock/seed 直接写 MySQL”的方式升级为符合业务需求文档的完整大数据链路。

目标链路：

```text
Mock 标准事件生成器
  -> Flume 监听事件文件
  -> Kafka Topic
  -> Spark Streaming / SparkSQL
  -> Windows 本机 MySQL
  -> Flask API
  -> Vue 前端
```

该链路必须体现三个技术栈：

- Flume：负责采集 mock 事件文件并发送到 Kafka。
- Kafka：负责消息缓冲和 topic 分发。
- Spark：负责消费 Kafka、聚合计算、写入 MySQL。

## 2. 总体部署边界

推荐拆分：

```text
Windows 本机
  - MySQL
  - Flask API
  - Vue 前端

虚拟机
  - Mock 标准事件生成器
  - Flume
  - Kafka
  - Spark
```

解耦边界是 MySQL。

Flask API 和 Vue 不直接连接 Flume、Kafka、Spark。它们只读取 MySQL，因此数据生产链路可以在以下两种模式之间切换：

```text
direct_mysql
  Mock/seed 脚本直接写 MySQL，用于快速调试和无虚拟机场景。

flume_kafka_spark
  Mock 生成器 -> Flume -> Kafka -> Spark -> MySQL，用于正式展示大数据链路。
```

只要 MySQL 表结构和 `/api/me/...` ViewModel 契约不变，前端和 Flask API 不需要跟随数据链路重构。

## 3. 当前仓库现状

已具备：

- Flask API：从 MySQL 读取并返回 `/api/me/...` 页面 ViewModel。
- Vue 前端：通过登录账号映射到唯一 `creator_id`，读取 session-scoped API。
- MySQL schema：已有页面展示所需主表和 Spark 结果表。
- Kafka 工具：
  - `kafka_tools/message_contract.py`
  - `kafka_tools/mock_event_builder.py`
  - `kafka_tools/mock_producer.py`
  - `kafka_tools/mock_consumer.py`
  - `kafka_tools/run_closed_loop.py`
- Spark 工具：
  - `spark_jobs/static_mock_to_mysql.py`
  - `spark_jobs/kafka_events_to_mysql.py`
  - `spark_jobs/kafka_streaming_to_mysql.py`

当前缺口：

- 还没有 `flume/` 配置和运行说明。
- mock 增长事件还没有作为“后台持续生成器”固定下来。
- Kafka live、Spark Streaming live 仍需要虚拟机环境和 `.env` 配置验证。

## 4. 标准事件设计

### 4.1 事件原则

Mock 生成器不直接生成页面卡片数据，也不直接生成 ViewModel。它生成“平台采集后标准化的事件”。

标准事件负责模拟真实平台采集结果：

```text
不同平台原始字段
  -> 统一字段名
  -> 标准事件 JSON
  -> Kafka
```

例如：

```text
抖音 digg_count
B站 like
小红书 liked_count
  -> 统一为 like_count
```

### 4.2 Topic 规范

Kafka topic 按事件类型固定：

| event_type | Kafka Topic | 第一阶段是否实现 | 说明 |
|---|---|---:|---|
| `video_stats` | `video_stats_topic` | 是 | 视频播放、互动、转粉快照，最小闭环优先 |
| `creator_stats` | `creator_stats_topic` | 第二批 | 账号粉丝、净增、掉粉 |
| `comment` | `comment_topic` | 第二批 | 评论文本、情绪、提问信号 |
| `danmaku` | `danmaku_topic` | 第三批 | B站弹幕事件 |
| `topic_trend` | `topic_trend_topic` | 第二批 | 热点话题热度变化 |

规范化含义：

- 一个事件类型只进入一个固定 topic。
- Spark 通过 topic 和 `event_type` 判断解析 schema。
- 不允许把多种事件混在未命名的临时 topic 中。

### 4.3 `video_stats` 最小事件

第一阶段先跑通 `video_stats`：

```json
{
  "topic": "video_stats_topic",
  "event_id": "evt_...",
  "event_type": "video_stats",
  "platform": "DOUYIN",
  "fetch_time": "2026-06-16T12:00:05+08:00",
  "creator_id": "creator_003",
  "content_id": "video_douyin_01_c3",
  "title": "AI办公工具测评",
  "content_type": "TUTORIAL",
  "publish_time": "2026-06-16T09:00:00+08:00",
  "publish_hour": 9,
  "tags": ["AI办公", "数码测评"],
  "stats": {
    "play_count": 128500,
    "like_count": 12500,
    "comment_count": 1850,
    "share_count": 4200,
    "save_count": 8900,
    "interaction_rate": 0.152,
    "completion_rate": 0.68,
    "average_watch_seconds": 212
  },
  "growth": {
    "play_growth_5s": 150,
    "play_growth_1h": 12500,
    "is_accelerating": true,
    "velocity_score": 85.0,
    "new_followers": 3200,
    "profile_visits": 18000
  },
  "traffic_source": {
    "recommend": {
      "views": 70675,
      "view_ratio": 0.55,
      "new_followers": 1500,
      "conversion_rate": 0.0212
    }
  }
}
```

事件校验以 `kafka_tools/message_contract.py` 为准。

## 5. 虚拟机目录规划

建议在虚拟机中使用：

```text
/opt/creatorpulse/
  app/
    kafka_tools/
    spark_jobs/
    flume/
    mock_generator/
  data/
    flume_spool/
      video_stats/
      creator_stats/
      comment/
      danmaku/
      topic_trend/
    generator_state/
      state.json
    logs/
      mock_generator.log
      flume.log
      spark_streaming.log
```

`mock_generator` 写入 Flume 监听目录时必须采用临时文件 + rename：

```text
先写：video_stats_20260616_120005_001.tmp
写完：rename 为 video_stats_20260616_120005_001.json
```

Flume 只读取 `.json`，忽略 `.tmp`，避免读取半截 JSON。

## 6. Mock 标准事件生成器

### 6.1 职责

Mock 生成器运行在虚拟机后台，按间隔生成标准事件文件。

它负责：

- 读取初始 mock 数据或 MySQL 中的基础视频/达人数据。
- 根据增长曲线生成持续变化的播放、互动、转粉数据。
- 维护 `state.json`，记录每条视频上一次计数。
- 每批生成完整 JSON Lines 文件。
- 写入 Flume spooldir。

它不负责：

- 直接写 MySQL。
- 直接调用 Flask API。
- 直接生成前端 ViewModel。
- 直接做复杂聚合。

### 6.2 运行方式

第一版命令：

```bash
nohup python mock_generator/generate_events.py \
  --event-type video_stats \
  --interval 5 \
  --batch-size 20 \
  --spool-dir /opt/creatorpulse/data/flume_spool/video_stats \
  --state-file /opt/creatorpulse/data/generator_state/state.json \
  > /opt/creatorpulse/data/logs/mock_generator.log 2>&1 &
```

后续可用 `systemd` 管理。

### 6.3 状态文件

示例：

```json
{
  "creator_003:video_douyin_01_c3": {
    "last_play_count": 128500,
    "last_like_count": 12500,
    "last_comment_count": 1850,
    "last_new_followers": 3200,
    "last_fetch_time": "2026-06-16T12:00:00+08:00",
    "growth_type": "normal"
  }
}
```

状态文件用于保证重启后数据继续增长，而不是每次从零开始。

## 7. Flume 实施

### 7.1 Flume 职责

Flume 是采集层，不做业务计算。它只负责：

```text
监听 spooldir
  -> 读取完整 JSON Lines 文件
  -> 写入 Kafka topic
```

### 7.2 Flume Source/Channel/Sink

第一阶段使用：

- Source：`spooldir`
- Channel：`memory`，后续可改 `file`
- Sink：Kafka sink

### 7.3 Flume 配置示例

建议新增文件：

```text
flume/creatorpulse-video-stats.conf
```

配置目标：

```properties
agent.sources = videoStatsSource
agent.channels = memoryChannel
agent.sinks = kafkaSink

agent.sources.videoStatsSource.type = spooldir
agent.sources.videoStatsSource.spoolDir = /opt/creatorpulse/data/flume_spool/video_stats
agent.sources.videoStatsSource.fileHeader = false
agent.sources.videoStatsSource.basenameHeader = true
agent.sources.videoStatsSource.includePattern = ^.*\\.json$
agent.sources.videoStatsSource.ignorePattern = ^.*\\.tmp$

agent.channels.memoryChannel.type = memory
agent.channels.memoryChannel.capacity = 10000
agent.channels.memoryChannel.transactionCapacity = 1000

agent.sinks.kafkaSink.type = org.apache.flume.sink.kafka.KafkaSink
agent.sinks.kafkaSink.kafka.bootstrap.servers = localhost:9092
agent.sinks.kafkaSink.kafka.topic = video_stats_topic
agent.sinks.kafkaSink.kafka.flumeBatchSize = 100
agent.sinks.kafkaSink.kafka.producer.acks = 1

agent.sources.videoStatsSource.channels = memoryChannel
agent.sinks.kafkaSink.channel = memoryChannel
```

启动命令：

```bash
flume-ng agent \
  --name agent \
  --conf /opt/apache-flume/conf \
  --conf-file /opt/creatorpulse/app/flume/creatorpulse-video-stats.conf \
  -Dflume.root.logger=INFO,console
```

## 8. Kafka 实施

### 8.1 Topic 创建

虚拟机中创建 topic：

```bash
kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic video_stats_topic --partitions 3 --replication-factor 1
kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic creator_stats_topic --partitions 3 --replication-factor 1
kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic comment_topic --partitions 3 --replication-factor 1
kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic danmaku_topic --partitions 3 --replication-factor 1
kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic topic_trend_topic --partitions 3 --replication-factor 1
```

第一阶段只要求 `video_stats_topic` 跑通。

### 8.2 Kafka 验证

查看 topic：

```bash
kafka-topics.sh --bootstrap-server localhost:9092 --list
```

消费测试：

```bash
kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic video_stats_topic \
  --from-beginning \
  --max-messages 5
```

Windows 到虚拟机连通性检查：

```powershell
python kafka_tools\check_connectivity.py --bootstrap-servers <vm-ip>:9092
```

如果失败，优先检查：

- 虚拟机 IP。
- Kafka 端口 `9092`。
- 防火墙。
- Kafka `advertised.listeners` 是否对 Windows 可访问。

## 9. Spark 实施

### 9.1 Spark 职责

Spark 从 Kafka 消费标准事件，做计算并写 MySQL。

第一阶段只消费：

```text
video_stats_topic
```

第一阶段写入：

```text
spark_platform_metric_summaries
spark_video_follower_contributions
```

后续扩展写入：

```text
video_metric_snapshots
creator_metric_snapshots
snapshot_state
realtime_growth_stats
insights
```

### 9.2 现有 Streaming 入口

当前仓库已有：

```text
spark_jobs/kafka_streaming_to_mysql.py
```

dry-run：

```bash
python spark_jobs/kafka_streaming_to_mysql.py
```

真实执行：

```bash
export CREATORPULSE_RUN_FULL_PIPELINE_LIVE=1
spark-submit spark_jobs/kafka_streaming_to_mysql.py --execute
```

### 9.3 Spark JDBC 配置

如果 Spark 在虚拟机，MySQL 在 Windows，本机 MySQL JDBC URL 不能写 `127.0.0.1`，要写虚拟机能访问到的 Windows IP。

示例：

```env
SPARK_MYSQL_JDBC_URL=jdbc:mysql://192.168.x.x:3306/creatorpulse
SPARK_MYSQL_USER=your_user
SPARK_MYSQL_PASSWORD=your_password
SPARK_MYSQL_DRIVER=com.mysql.cj.jdbc.Driver
SPARK_MYSQL_WRITE_MODE=append
```

Windows 侧必须确认：

- MySQL 允许远程连接。
- MySQL 用户允许从虚拟机 IP 登录。
- Windows 防火墙放行 `3306`。
- 虚拟机可以访问 Windows IP 和 MySQL 端口。

## 10. MySQL 表边界

前端和 Flask 当前依赖的主表继续保留：

```text
creators
users
platform_accounts
videos
video_metric_snapshots
video_traffic_source_metrics
creator_metric_snapshots
audience_profile_snapshots
topic_trend_snapshots
insights
insight_evidence_metrics
recommended_actions
spark_platform_metric_summaries
spark_video_follower_contributions
```

为完整体现实时链路，后续建议补充：

```text
raw_events
snapshot_state
realtime_growth_stats
```

其中：

- `raw_events`：可选，保存 Kafka 原始事件，便于排错。
- `snapshot_state`：保存上一次快照，用于差分计算。
- `realtime_growth_stats`：保存 Spark 计算后的实时增长结果。

第一阶段可以先不补表，只写已有 Spark 结果表，证明 Flume -> Kafka -> Spark -> MySQL 能跑通。

## 11. 环境变量

Windows `.env` 继续供 Flask 和本机脚本使用。

虚拟机也需要一份 `.env` 或 shell profile：

```env
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TEST_TIMEOUT_SECONDS=5

SPARK_MYSQL_JDBC_URL=jdbc:mysql://<windows-ip>:3306/creatorpulse
SPARK_MYSQL_USER=your_user
SPARK_MYSQL_PASSWORD=your_password
SPARK_MYSQL_DRIVER=com.mysql.cj.jdbc.Driver
SPARK_MYSQL_WRITE_MODE=append

SPARK_STREAM_TRIGGER_SECONDS=30
SPARK_STREAM_CHECKPOINT_DIR=/opt/creatorpulse/data/spark_checkpoints/video_stats
SPARK_STREAM_OUTPUT_MODE=update
CREATORPULSE_RUN_FULL_PIPELINE_LIVE=1
```

不要提交真实 `.env`。

## 12. 实施阶段

### 阶段 1：本地 dry-run 闭环

目的：不连接真实 Kafka/Flume，先确认事件契约和 Spark 聚合逻辑。

命令：

```powershell
python kafka_tools\mock_producer.py
python kafka_tools\mock_consumer.py
python spark_jobs\kafka_events_to_mysql.py
python kafka_tools\run_closed_loop.py
```

验收：

- 能生成 NDJSON 标准事件。
- 事件通过 `message_contract` 校验。
- Spark-style 聚合能产出平台汇总和视频贡献行。

### 阶段 2：补 Flume 配置和 spooldir 生成器

目的：在虚拟机内用文件模拟平台采集。

交付：

```text
flume/creatorpulse-video-stats.conf
mock_generator/generate_events.py
mock_generator/README.md
```

验收：

- mock 生成器能持续写 `.json` 文件。
- Flume 能把文件内容发送到 `video_stats_topic`。
- Kafka console consumer 能读到 JSON 事件。

### 阶段 3：Kafka live 连通

目的：确认 Kafka 可用，并且 Windows/虚拟机配置正确。

命令：

```powershell
python scripts\preflight.py --target kafka --strict
python kafka_tools\check_connectivity.py --bootstrap-servers <vm-ip>:9092
```

虚拟机内：

```bash
kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic video_stats_topic --from-beginning --max-messages 5
```

验收：

- Kafka topic 存在。
- Flume 写入后 consumer 能消费。
- Windows 能访问虚拟机 Kafka。

### 阶段 4：Spark Streaming 写 MySQL

目的：Spark 从 Kafka 消费 `video_stats`，写入 MySQL Spark 结果表。

命令：

```bash
export CREATORPULSE_RUN_FULL_PIPELINE_LIVE=1
spark-submit spark_jobs/kafka_streaming_to_mysql.py --execute
```

验收：

- MySQL 中 `spark_platform_metric_summaries` 有新增 run/batch 数据。
- MySQL 中 `spark_video_follower_contributions` 有新增 run/batch 数据。
- Flask `/api/me/videos` 能读到 `sparkContributions`。
- Flask `/api/me/distribution` 能读到 `sparkPlatformSummaries`。
- Vue 页面刷新后仍正常展示。

### 阶段 5：扩展事件和实时表

目的：从单一 `video_stats` 扩展到业务文档中的完整事件流。

顺序：

```text
creator_stats
comment
topic_trend
danmaku
```

再补：

```text
snapshot_state
realtime_growth_stats
raw_events
```

## 13. 回退方案

当虚拟机、Kafka、Flume、Spark 任一组件不可用时，可以快速回退：

```text
database/import_mock_to_mysql.py --execute
database/seed_demo_users.py --execute
database/seed_additional_creator.py --execute
```

后端保持：

```env
CREATORPULSE_DATA_SOURCE=mysql
```

回退后：

```text
Mock/seed -> MySQL -> Flask -> Vue
```

该模式只用于本地调试和演示兜底，不作为最终大数据链路。

## 14. 不做事项

第一阶段不要做：

- 不让 Vue 直接读 Kafka。
- 不让 Flask 承担 Kafka consumer 职责。
- 不让 Flume 写 MySQL。
- 不让 mock 生成器直接生成 ViewModel。
- 不一开始同时跑 5 个 topic。
- 不把真实密码、Kafka 地址、MySQL 密码提交到仓库。

## 15. 成功标准

第一阶段成功标准：

- 虚拟机中 mock 生成器持续产生 `video_stats` 标准事件文件。
- Flume 采集文件并写入 `video_stats_topic`。
- Kafka consumer 能读到事件。
- Spark Streaming 能消费 `video_stats_topic`。
- Spark 通过 JDBC 写入 Windows MySQL。
- Flask API 不改接口即可读到 Spark 输出。
- Vue 页面不改结构即可展示数据。

最终成功标准：

- 五类事件 topic 均可运行。
- Spark Streaming/SparkSQL 输出能支撑增长总览、粉丝分析、视频分析、内容分布、机会建议、个人中心。
- `direct_mysql` 和 `flume_kafka_spark` 两种模式都能保留，方便调试和正式展示切换。
