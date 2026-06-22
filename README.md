# CreatorPulse

CreatorPulse 是面向内容创作者的达人粉丝增长分析与智能创作建议平台。当前项目已经形成可运行 MVP：Vue 前端、Flask API、mock/MySQL 双数据源、MySQL 表结构、Spark/Kafka dry-run、虚拟机侧 Flume/Kafka/Spark 启动脚本和一组真实服务接入前的预检脚本。

当前主线是：

```text
Vue -> Flask API -> mock JSON / MySQL
```

大数据演示链路是：

```text
VM mock_generator -> Flume -> Kafka -> Spark Streaming -> Windows MySQL -> Flask API -> Vue
```

Flask 和 Vue 不直接连接 Kafka/Spark。它们只读取 API 和 MySQL，因此大数据链路可以独立启动、停止和排查。

## 当前状态

- 已完成 6 个前端页面：增长总览、粉丝分析、视频分析、内容分布、机会建议、个人中心。
- 已完成登录、注册、模拟平台绑定、头像上传、个人中心配置、管理员模拟监控接口。
- 已完成 Flask API ViewModel 合同和 OpenAPI：`api/openapi.json`。
- 已完成 MySQL schema、mock 导入、MySQL Repository、mock Repository。
- 已完成 Kafka 风格事件生成、消费校验、闭环 dry-run。
- 已完成 Spark 静态聚合、Kafka streaming dry-run、离线日报/周报/月报脚本。
- 已提供 VM 内 Flume、mock_generator、Spark Streaming 一键脚本。
- 真实 Kafka/Spark/MySQL 写入仍建议按 strict preflight 分阶段执行。

## 本机端口和地址

| 服务 | 地址/端口 | 说明 |
|---|---|---|
| Flask API | `http://127.0.0.1:5000` | 后端 API，也可托管 build 后的前端 |
| Vite dev server | `http://127.0.0.1:5173` | 前端开发服务，代理 `/api` 和 `/uploads` 到 Flask |
| Vite preview | `http://127.0.0.1:4173` | 前端构建产物预览 |
| MySQL | `127.0.0.1:3306` | Windows 本机 MySQL，库名默认 `creatorpulse` |
| OpenAPI | `http://127.0.0.1:5000/api/openapi.json` | API 合同 |

## 虚拟机 IP 和端口

`.env.example` 中默认 VM Kafka 地址是：

```env
KAFKA_BOOTSTRAP_SERVERS=192.168.56.10:9092
```

如果虚拟机 IP 变化，以实际虚拟机 IP 为准，同时修改 `.env` 中的 `KAFKA_BOOTSTRAP_SERVERS`。

| VM 服务 | VM 内访问 | Windows 访问 | 说明 |
|---|---|---|---|
| Zookeeper | `localhost:2181` | 通常不需要从 Windows 访问 | `start_pipeline.sh` 会检查 2181 |
| Kafka | `localhost:9092` | `<vm-ip>:9092`，默认 `192.168.56.10:9092` | `advertised.listeners` 必须对 Windows 可访问 |
| Flume | 本机进程 | 不直接暴露 | 监听 `/opt/creatorpulse/data/flume_spool/video_stats` |
| Spark Streaming | 本机进程 | 不直接暴露 | 从 Kafka 消费，JDBC 写 Windows MySQL |
| Windows MySQL | `<windows-ip>:3306` | `127.0.0.1:3306` | VM 写 MySQL 时不能用 `127.0.0.1` 指向 Windows |

VM 脚本默认使用：

```bash
APP_HOME=/opt/creatorpulse/app
DATA_HOME=/opt/creatorpulse/data
JAVA_HOME=/usr/local/java/jdk1.8.0_201
SPARK_HOME=/usr/local/spark-local
KAFKA_HOME=/usr/local/kafka_2.13-3.3.1
FLUME_HOME=/usr/local/flume
MYSQL_HOST=192.168.88.1
MYSQL_PORT=3306
MYSQL_DATABASE=creatorpulse
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

其中 `MYSQL_HOST=192.168.88.1` 是 VM 访问 Windows MySQL 的默认示例，实际要改成 VM 能访问到的 Windows 主机 IP。

## 本机快速启动

首次准备：

```powershell
python -m pip install -r requirements.txt
cd frontend
npm install
cd ..
python scripts\init_env.py
```

启动后端：

```powershell
python api\app.py
```

启动前端开发服务：

```powershell
cd frontend
npm run dev
```

打开：

```text
http://127.0.0.1:5173
```

如果只想用 Flask 托管构建后的前端：

```powershell
cd frontend
npm run build
cd ..
python api\app.py
```

然后打开：

```text
http://127.0.0.1:5000
```

## 数据源切换

`.env` 中用 `CREATORPULSE_DATA_SOURCE` 控制 API 数据源：

```env
CREATORPULSE_DATA_SOURCE=mock
```

可选值：

- `mock`：读取 `mvp_mock/data/creatorpulse_mvp_mock.json`，适合快速演示。
- `mysql`：读取本机 MySQL，适合注册、多达人和真实链路演示。

本机 MySQL 初始化和导入：

```powershell
python scripts\preflight.py --target local-mysql --strict
python scripts\setup_local_mysql.py --execute
```

底层等价脚本：

```powershell
python database\apply_schema.py --execute
python database\import_mock_to_mysql.py --execute
```

## 虚拟机内部启动方式

本仓库中的 VM 脚本源文件在：

```text
scripts/vm_pipeline/start_pipeline.sh
scripts/vm_pipeline/status_pipeline.sh
scripts/vm_pipeline/stop_pipeline.sh
```

推荐部署到 VM 后放在：

```bash
/opt/creatorpulse/app/scripts/start_pipeline.sh
/opt/creatorpulse/app/scripts/status_pipeline.sh
/opt/creatorpulse/app/scripts/stop_pipeline.sh
```

如果按仓库目录原样复制，也可以从：

```bash
/opt/creatorpulse/app/scripts/vm_pipeline/start_pipeline.sh
/opt/creatorpulse/app/scripts/vm_pipeline/status_pipeline.sh
/opt/creatorpulse/app/scripts/vm_pipeline/stop_pipeline.sh
```

启动大数据链路：

```bash
cd /opt/creatorpulse/app
chmod +x scripts/start_pipeline.sh scripts/status_pipeline.sh scripts/stop_pipeline.sh
scripts/start_pipeline.sh
```

查看状态：

```bash
scripts/status_pipeline.sh
```

停止链路：

```bash
scripts/stop_pipeline.sh
```

启动脚本会依次启动：

1. Flume：读取 spooldir 中的 `video_stats` JSON 文件。
2. mock_generator：从 MySQL 读取达人/平台/视频基础数据并持续生成事件。
3. Spark Streaming：消费 Kafka 的 `video_stats_topic` 并写入 MySQL 聚合结果表。

日志位置：

```bash
/opt/creatorpulse/data/logs/flume-video-stats.log
/opt/creatorpulse/data/logs/mock-generator.log
/opt/creatorpulse/data/logs/spark-kafka-streaming.log
```

PID 位置：

```bash
/opt/creatorpulse/data/pids/
```

Flume 监听目录：

```bash
/opt/creatorpulse/data/flume_spool/video_stats
```

## VM 内手动检查 Kafka

创建 topic：

```bash
kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic video_stats_topic --partitions 3 --replication-factor 1
kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic creator_stats_topic --partitions 3 --replication-factor 1
kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic comment_topic --partitions 3 --replication-factor 1
kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic danmaku_topic --partitions 3 --replication-factor 1
kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic topic_trend_topic --partitions 3 --replication-factor 1
```

查看 topic：

```bash
kafka-topics.sh --bootstrap-server localhost:9092 --list
```

消费 `video_stats_topic`：

```bash
kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic video_stats_topic --from-beginning --max-messages 5
```

Windows 侧检查 VM Kafka 连通：

```powershell
python kafka_tools\check_connectivity.py --bootstrap-servers 192.168.56.10:9092
python scripts\preflight.py --target kafka --strict
```

## 真实服务接入顺序

建议按这个顺序接入，不要直接启动 full pipeline：

```text
MySQL strict preflight
-> MySQL schema/import
-> Spark JDBC strict preflight
-> Spark JDBC live write
-> Kafka strict preflight
-> Kafka live produce/consume
-> full-pipeline strict preflight
-> Kafka -> Spark -> MySQL streaming
```

查看推荐顺序：

```powershell
python scripts\run_real_service_sequence.py
python scripts\status_mvp.py
```

Spark JDBC live：

```powershell
python scripts\preflight.py --target spark-jdbc --strict
$env:CREATORPULSE_RUN_SPARK_JDBC_LIVE='1'
python spark_jobs\tests\test_static_mysql_jdbc_integration.py
```

Kafka live：

```powershell
python scripts\preflight.py --target kafka --strict
$env:CREATORPULSE_RUN_KAFKA_LIVE='1'
python kafka_tools\tests\test_kafka_live_integration.py
```

完整 streaming：

```powershell
python scripts\preflight.py --target full-pipeline --strict
$env:CREATORPULSE_RUN_FULL_PIPELINE_LIVE='1'
spark-submit spark_jobs\kafka_streaming_to_mysql.py --execute
```

## 脚本位置索引

### 后端和 API

| 路径 | 用途 |
|---|---|
| `api/app.py` | Flask API 入口，端口 `5000` |
| `api/auth.py` | 登录、注册、登出 |
| `api/repository.py` | mock/MySQL Repository 工厂 |
| `api/mock_repository.py` | mock JSON 数据源 |
| `api/mysql_repository.py` | MySQL 数据源 |
| `api/view_model_builder.py` | 页面 ViewModel 组装 |
| `api/view_model_contract.py` | API 响应合同校验 |
| `api/openapi_contract.py` | OpenAPI 生成 |
| `api/admin_simulation.py` | 模拟链路监控接口 |

### 前端

| 路径 | 用途 |
|---|---|
| `frontend/src/App.vue` | Vue 应用入口布局 |
| `frontend/src/pages/` | 六个业务页面和登录页 |
| `frontend/src/services/api.js` | 前端 API 调用 |
| `frontend/src/styles/` | 样式 |
| `frontend/vite.config.js` | Vite 代理 `/api`、`/uploads` 到 Flask |

### MySQL

| 路径 | 用途 |
|---|---|
| `database/schema.sql` | MySQL 表结构 |
| `database/apply_schema.py` | 应用 schema |
| `database/import_mock_to_mysql.py` | 导入 mock 数据 |
| `database/seed_demo_users.py` | 初始化 demo 用户 |
| `database/seed_additional_creator.py` | 追加模拟达人 |
| `database/migrate_users_creator_unique.py` | 用户/达人唯一关系迁移 |

### Kafka 工具

| 路径 | 用途 |
|---|---|
| `kafka_tools/message_contract.py` | Kafka 事件合同 |
| `kafka_tools/mock_event_builder.py` | 从 MVP 数据生成 Kafka 风格事件 |
| `kafka_tools/mock_producer.py` | 生成本地 NDJSON 或真实生产 Kafka |
| `kafka_tools/mock_consumer.py` | 校验本地 NDJSON 或真实消费 Kafka |
| `kafka_tools/check_connectivity.py` | 检查 Kafka host:port |
| `kafka_tools/run_closed_loop.py` | 本地/真实 Kafka 闭环 |

### Spark 和离线任务

| 路径 | 用途 |
|---|---|
| `spark_jobs/static_mock_to_mysql.py` | Spark 静态聚合写 MySQL |
| `spark_jobs/kafka_events_to_mysql.py` | Kafka 风格事件离线聚合 |
| `spark_jobs/kafka_streaming_to_mysql.py` | Kafka -> Spark Structured Streaming -> MySQL |
| `spark_jobs/kafka_streaming_to_mysql_py36.py` | VM Python 3.6 兼容版本 |
| `spark_jobs/offline_daily_metrics.py` | 离线日报指标 |
| `spark_jobs/offline_reports.py` | 周报/月报生成 |
| `spark_jobs/offline_recompute_worker.py` | 离线重算 worker |
| `spark_jobs/spark_mysql_jdbc_smoke.scala` | Spark JDBC smoke 示例 |

### Flume 和 VM 链路

| 路径 | 用途 |
|---|---|
| `flume/creatorpulse-video-stats.conf` | Flume spooldir -> Kafka 配置 |
| `mock_generator/generate_events.py` | VM 持续事件生成器 |
| `scripts/vm_pipeline/start_pipeline.sh` | VM 启动 Flume、mock_generator、Spark Streaming |
| `scripts/vm_pipeline/status_pipeline.sh` | VM 查看链路状态 |
| `scripts/vm_pipeline/stop_pipeline.sh` | VM 停止链路 |

### 本机验证和报告

| 路径 | 用途 |
|---|---|
| `scripts/verify_mvp.py` | 总体验证入口 |
| `scripts/status_mvp.py` | 当前能力和下一步建议 |
| `scripts/preflight.py` | 本机/真实服务预检 |
| `scripts/init_env.py` | 初始化 `.env` |
| `scripts/setup_local_mysql.py` | MySQL schema/import/API 合同一键流程 |
| `scripts/report_env_readiness.py` | `.env` 配置状态 |
| `scripts/run_real_service_sequence.py` | 真实服务接入顺序 |
| `scripts/report_real_service_plans.py` | 执行计划报告 |
| `scripts/report_execution_checklist.py` | 执行前检查清单 |
| `scripts/audit_data_contract.py` | schema/import/ViewModel/OpenAPI 合同审计 |
| `scripts/audit_data_quality.py` | mock 公式、Spark dry-run、Insight 证据审计 |
| `scripts/audit_object_coverage.py` | 数据对象覆盖审计 |
| `scripts/audit_real_service_readiness.py` | 真实服务门禁审计 |
| `scripts/export_openapi.py` | 导出/检查 OpenAPI |
| `scripts/export_real_service_report_bundle.py` | 导出真实服务报告包 |

### 离线作业脚本

| 路径 | 用途 |
|---|---|
| `scripts/run_offline_daily.sh` | 运行离线日报 |
| `scripts/run_offline_reports.sh` | 运行周期报表 |
| `scripts/run_offline_recompute_worker.sh` | 运行离线重算 worker |
| `scripts/status_offline_jobs.sh` | 查看离线任务状态 |

## 常用验证命令

完整验证：

```powershell
python scripts\verify_mvp.py
```

跳过浏览器的快速验证：

```powershell
python scripts\verify_mvp.py --skip-browser
```

单项验证：

```powershell
python mvp_mock\validate_mock.py
python api\tests\test_mock_api.py
python scripts\audit_data_contract.py
python scripts\audit_object_coverage.py
python scripts\audit_data_quality.py
python scripts\export_openapi.py --check
python kafka_tools\run_closed_loop.py
python spark_jobs\kafka_streaming_to_mysql.py
```

前端构建：

```powershell
cd frontend
npm run build
```

## 注意事项

- 不要提交真实 `.env`、MySQL 密码、Kafka 地址凭据或本机报告。
- VM 写 Windows MySQL 时，JDBC URL 不能写 `127.0.0.1`，必须写 VM 可访问的 Windows IP。
- 当前实时事件主线主要是 `video_stats_topic`，不是所有页面模块都已经实时化。
- 当前 VM 一键脚本不是 systemd 服务，虚拟机重启后需要重新执行启动脚本。
- 如果 Kafka/Spark 链路故障，可以回退到 `CREATORPULSE_DATA_SOURCE=mysql` 加本机 MySQL 数据。
