# 正式离线处理、历史归档、周期报表、批量重算、离线调度 SPEC

## 1. Summary

本 SPEC 用来补齐 CreatorPulse 的正式离线数据能力。

当前项目已经有实时链路：

```text
Mock 事件生成器
  -> Flume
  -> Kafka
  -> Spark Streaming
  -> MySQL 实时指标表
  -> Flask API
  -> Vue 前端
```

这条链路适合回答：

```text
你的账号现在怎么样？
当前哪个视频涨粉更快？
当前平台贡献如何？
```

但是日报、周报、月报、历史归档、批量重算、离线调度不能只靠实时表完成。原因是实时表更偏“最新状态”，而离线处理需要完整历史事件，才能按天、按周、按月重新计算。

因此本轮新增一条离线链路：

```text
Kafka / Spark Streaming 消费到的标准事件
  -> raw_video_stat_events 历史事件归档表
  -> Spark Batch 离线任务
  -> offline_*_daily_metrics 离线汇总表
  -> creator_reports 周期报表表
  -> Flask 报表 API
  -> 个人中心「数据报告」
```

核心原则：

```text
实时表：服务当前页面，回答“现在怎么样”
离线表：服务复盘报表，回答“过去某天/某周/某月怎么样”
原始事件表：服务历史归档和批量重算，保证结果可以重新计算
```

## 2. Goals

本 SPEC 的目标是增加 5 类能力：

1. 正式离线处理
   - 使用 Spark Batch 对历史事件做日级、周级、月级计算。

2. 历史归档
   - 保存每条标准事件，避免只保留最新指标。
   - 后续所有报表和重算都从归档事件或离线汇总表生成。

3. 周期报表
   - 生成个人日报、个人周报、个人月报。
   - 报表内容进入数据库，而不是前端写死文案。

4. 批量重算
   - 支持按达人、按日期范围重新计算历史指标和报表。
   - 用于修复规则、公式、历史数据异常。

5. 离线调度
   - 在虚拟机上定时执行离线任务。
   - 记录每次任务成功、失败、处理数量和错误原因。

## 3. Non-Goals

本轮不做：

- 不重做所有前端分析页。
- 不把日报、周报、月报塞进增长总览、粉丝分析、视频分析等实时页面。
- 不引入 Airflow、DolphinScheduler 等复杂调度平台。
- 不接真实平台 API。
- 不做 HDFS 集群。
- 不把报表做成复杂 CRM 系统。

MVP 阶段使用：

```text
Windows 本机：MySQL + Flask API + Vue 前端
虚拟机：Mock 事件生成器 + Flume + Kafka + Spark Streaming + Spark Batch + cron
```

## 4. Current State

当前已有实时链路：

```text
mock_generator
  -> Flume spooldir
  -> Kafka video_stats_topic
  -> Spark Streaming
  -> MySQL 指标表
  -> Flask ViewModel
  -> Vue 页面
```

当前实时链路主要写入：

```text
video_metric_snapshots
video_traffic_source_metrics
creator_metric_snapshots
spark_platform_metric_summaries
spark_video_follower_contributions
```

这些表适合页面实时展示，但不适合作为完整历史来源。

问题是：

1. 没有完整原始事件归档。
2. 报表文案目前主要由前端或 ViewModel 兜底生成，不是真正的离线结果。
3. 没有日报、周报、月报的持久化表。
4. 没有批量重算请求记录。
5. 没有离线任务运行记录。
6. 没有虚拟机定时调度规范。

## 5. Target Architecture

目标链路：

```text
实时链路：

Mock 事件生成器
  -> Flume
  -> Kafka
  -> Spark Streaming
  -> 实时指标表
  -> Flask 实时页面 API
  -> Vue 分析页面

离线链路：

标准事件
  -> raw_video_stat_events
  -> Spark Batch daily aggregation
  -> offline_*_daily_metrics
  -> Spark Batch report generation
  -> creator_reports
  -> Flask 报表 API
  -> 个人中心「数据报告」

管理链路：

管理员 / 后台请求
  -> offline_recompute_requests
  -> 离线重算 worker
  -> Spark Batch backfill
  -> offline_batch_runs
```

## 6. Data Model Changes

主要修改：

```text
database/schema.sql
```

### 6.1 raw_video_stat_events

用途：保存每条标准事件，是历史归档和重算的基础。

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| event_id | VARCHAR(96) PK | 事件唯一 ID |
| creator_id | VARCHAR(64) | 达人 ID |
| platform | VARCHAR(32) | 平台：douyin / bilibili / xiaohongshu 等 |
| video_id | VARCHAR(96) | 视频 ID |
| event_type | VARCHAR(32) | 事件类型，MVP 可统一为 video_stats |
| event_date | DATE | 事件日期 |
| fetch_time | DATETIME | 事件采集时间 |
| play_delta | INT | 播放增量 |
| like_delta | INT | 点赞增量 |
| comment_delta | INT | 评论增量 |
| share_delta | INT | 分享增量 |
| save_delta | INT | 收藏增量 |
| profile_visit_delta | INT | 主页访问增量 |
| new_follower_delta | INT | 新增粉丝增量 |
| lost_follower_delta | INT | 流失粉丝增量 |
| raw_payload_json | JSON | 原始事件内容 |
| ingested_at | DATETIME | 入库时间 |

必要索引：

```text
(creator_id, event_date)
(video_id, event_date)
(platform, event_date)
(fetch_time)
```

### 6.2 offline_creator_daily_metrics

用途：达人日级离线汇总。

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| creator_id | VARCHAR(64) | 达人 ID |
| metric_date | DATE | 指标日期 |
| total_views_delta | INT | 当日播放增量 |
| total_interactions_delta | INT | 当日互动增量 |
| profile_visits_delta | INT | 当日主页访问增量 |
| new_followers_delta | INT | 当日新增粉丝 |
| lost_followers_delta | INT | 当日流失粉丝 |
| net_followers_delta | INT | 当日净增粉丝 |
| view_to_follower_rate | DECIMAL | 播放转粉率 |
| engagement_rate | DECIMAL | 互动率 |
| stickiness_score | DECIMAL | 粘性指数 |
| growth_health_score | DECIMAL | 账号健康度 |
| batch_run_id | VARCHAR(96) | 本次离线任务 ID |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

唯一约束：

```text
UNIQUE (creator_id, metric_date)
```

### 6.3 offline_platform_daily_metrics

用途：平台日级离线汇总。

建议字段：

```text
creator_id
platform
metric_date
views_delta
interactions_delta
profile_visits_delta
new_followers_delta
lost_followers_delta
view_to_follower_rate
engagement_rate
contribution_score
batch_run_id
created_at
updated_at
```

唯一约束：

```text
UNIQUE (creator_id, platform, metric_date)
```

### 6.4 offline_video_daily_metrics

用途：视频日级离线汇总。

建议字段：

```text
creator_id
video_id
platform
metric_date
views_delta
likes_delta
comments_delta
shares_delta
saves_delta
profile_visits_delta
new_followers_delta
lost_followers_delta
view_to_follower_rate
engagement_rate
follower_contribution_score
batch_run_id
created_at
updated_at
```

唯一约束：

```text
UNIQUE (creator_id, video_id, metric_date)
```

### 6.5 offline_content_type_daily_metrics

用途：内容类型日级离线汇总。

建议字段：

```text
creator_id
content_type
metric_date
video_count
views_delta
interactions_delta
new_followers_delta
view_to_follower_rate
engagement_rate
efficiency_score
batch_run_id
created_at
updated_at
```

唯一约束：

```text
UNIQUE (creator_id, content_type, metric_date)
```

### 6.6 creator_reports

用途：保存日报、周报、月报。

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| report_id | VARCHAR(96) PK | 报告 ID |
| creator_id | VARCHAR(64) | 达人 ID |
| report_type | VARCHAR(16) | DAILY / WEEKLY / MONTHLY |
| period_start | DATE | 周期开始 |
| period_end | DATE | 周期结束 |
| status | VARCHAR(16) | GENERATED / EMPTY / FAILED |
| title | VARCHAR(128) | 报告标题 |
| summary | TEXT | 核心摘要 |
| highlights_json | JSON | 亮点列表 |
| risks_json | JSON | 风险列表 |
| actions_json | JSON | 建议动作 |
| metrics_json | JSON | 报告指标 |
| generated_at | DATETIME | 生成时间 |
| batch_run_id | VARCHAR(96) | 生成任务 ID |

唯一约束：

```text
UNIQUE (creator_id, report_type, period_start, period_end)
```

说明：

MVP 阶段 report 的 sections 使用 JSON 是合理的。因为日报、周报、月报的内容结构会变化，过早拆很多子表会增加复杂度。

### 6.7 offline_batch_runs

用途：记录每次离线任务运行情况。

建议字段：

```text
batch_run_id
job_name
job_type
period_start
period_end
status
triggered_by
input_event_count
output_row_count
error_message
started_at
finished_at
```

其中：

```text
job_type:
  DAILY_AGGREGATION
  REPORT_GENERATION
  BACKFILL

status:
  RUNNING
  SUCCESS
  FAILED

triggered_by:
  SCHEDULED
  MANUAL
```

### 6.8 offline_recompute_requests

用途：记录批量重算请求。

建议字段：

```text
request_id
creator_id
period_start
period_end
recompute_scope
status
requested_by
requested_at
started_at
finished_at
batch_run_id
error_message
```

其中：

```text
recompute_scope:
  CREATOR_DAILY
  PLATFORM_DAILY
  VIDEO_DAILY
  CONTENT_TYPE_DAILY
  REPORTS
  ALL

status:
  PENDING
  RUNNING
  SUCCESS
  FAILED
```

## 7. Spark Job Changes

主要新增目录和文件：

```text
spark_jobs/offline_daily_metrics.py
spark_jobs/offline_reports.py
spark_jobs/offline_backfill.py
```

### 7.1 kafka_streaming_to_mysql_py36.py

现有实时 Spark Streaming 作业需要增加一件事：

```text
消费 Kafka 事件后，除了写实时指标表，还要写 raw_video_stat_events。
```

注意：

- 不改变现有前端实时页面接口。
- 不改变现有实时表含义。
- raw 表只负责历史归档。

### 7.2 offline_daily_metrics.py

用途：按日期范围从 `raw_video_stat_events` 汇总日级指标。

输入：

```text
--start-date 2026-06-21
--end-date 2026-06-21
--creator-id optional
```

输出：

```text
offline_creator_daily_metrics
offline_platform_daily_metrics
offline_video_daily_metrics
offline_content_type_daily_metrics
offline_batch_runs
```

核心计算：

```text
播放增量 = sum(play_delta)
互动增量 = sum(like_delta + comment_delta + share_delta + save_delta)
净增粉丝 = sum(new_follower_delta - lost_follower_delta)
播放转粉率 = new_followers_delta / max(views_delta, 1)
互动率 = interactions_delta / max(views_delta, 1)
粘性指数 = 收藏、评论、分享、复访类指标的加权结果
健康度 = 增长趋势、转粉效率、互动质量、内容效率的加权结果
```

### 7.3 offline_reports.py

用途：从离线汇总表生成日报、周报、月报。

输入：

```text
--report-type DAILY|WEEKLY|MONTHLY
--period-start 2026-06-21
--period-end 2026-06-21
--creator-id optional
```

输出：

```text
creator_reports
offline_batch_runs
```

报表内容来源：

```text
offline_creator_daily_metrics
offline_platform_daily_metrics
offline_video_daily_metrics
offline_content_type_daily_metrics
videos
platform_accounts
creators
```

报表内容包含：

```text
核心结论 summary
关键亮点 highlights_json
风险提醒 risks_json
行动建议 actions_json
关键指标 metrics_json
```

### 7.4 offline_backfill.py

用途：批量重算历史日期范围。

输入：

```text
--start-date 2026-06-01
--end-date 2026-06-21
--creator-id creator_001
--scope ALL
```

处理顺序：

```text
1. 创建 offline_batch_runs
2. 重新计算 offline_*_daily_metrics
3. 重新生成 creator_reports
4. 更新 offline_recompute_requests 状态
```

## 8. Flask API Changes

主要修改：

```text
api/app.py
api/mysql_repository.py
api/view_model_builder.py
api/view_model_contract.py
```

### 8.1 User Report APIs

新增：

```text
GET /api/me/reports
GET /api/me/reports/<report_id>
```

列表接口参数：

```text
type=DAILY|WEEKLY|MONTHLY
page=1
pageSize=10
```

返回示例：

```json
{
  "items": [
    {
      "reportId": "report_creator_001_daily_2026_06_21",
      "creatorId": "creator_001",
      "reportType": "DAILY",
      "periodStart": "2026-06-21",
      "periodEnd": "2026-06-21",
      "status": "GENERATED",
      "title": "6月21日增长日报",
      "summary": "你的账号今日净增粉丝稳定，B站教程内容贡献最高。",
      "highlights": [],
      "risks": [],
      "actions": [],
      "metrics": {},
      "generatedAt": "2026-06-21T00:20:00"
    }
  ],
  "page": 1,
  "pageSize": 10,
  "total": 1
}
```

### 8.2 Admin Offline APIs

新增：

```text
GET /api/admin/offline/status
POST /api/admin/offline/recompute
```

`POST /api/admin/offline/recompute` 不直接启动 Spark。

它只负责写入：

```text
offline_recompute_requests
```

然后虚拟机上的离线 worker 扫描这张表并执行重算。

这样 Windows 本机的 Flask API 和虚拟机 Spark 执行环境保持解耦。

## 9. Frontend Changes

前端不需要全站重做。

主要修改：

```text
frontend/src/pages/CreatorProfile.vue
frontend/src/services/api.js
```

### 9.1 保持不变的页面

以下页面继续作为实时分析页：

```text
增长总览
粉丝分析
视频分析
内容分布
机会建议
```

它们继续读取现有 ViewModel，不因为离线处理而大改。

### 9.2 需要修改的页面

修改：

```text
个人中心 -> 数据报告
```

展示内容从静态文案改成真实报表数据：

```text
最新日报
最新周报
最新月报
历史报告列表
报告生成状态
报告周期
核心结论
关键指标
风险提醒
下步建议
```

空状态：

```text
暂无日报：等待离线任务生成
暂无周报：等待累计足够周期数据
暂无月报：月初离线任务生成后展示
```

### 9.3 可选管理页面

后续可以扩展：

```text
/admin/simulation
```

或者新增：

```text
/admin/offline
```

展示：

```text
最近一次离线任务状态
处理事件数量
生成报表数量
失败原因
手动提交重算请求
```

MVP 阶段优先放在现有 AdminSimulation 页面中，不新增复杂后台。

## 10. VM Scheduling

新增脚本：

```text
scripts/run_offline_daily.sh
scripts/run_offline_reports.sh
scripts/run_offline_recompute_worker.sh
scripts/status_offline_jobs.sh
```

上传到虚拟机：

```text
/opt/creatorpulse/app/scripts/
```

建议 cron：

```text
10 0 * * * /opt/creatorpulse/app/scripts/run_offline_daily.sh
20 0 * * * /opt/creatorpulse/app/scripts/run_offline_reports.sh DAILY
30 0 * * 1 /opt/creatorpulse/app/scripts/run_offline_reports.sh WEEKLY
40 0 1 * * /opt/creatorpulse/app/scripts/run_offline_reports.sh MONTHLY
* * * * * /opt/creatorpulse/app/scripts/run_offline_recompute_worker.sh
```

解释：

- 每天 00:10 计算昨天的日级离线指标。
- 每天 00:20 生成昨天的日报。
- 每周一 00:30 生成上周周报。
- 每月 1 日 00:40 生成上月月报。
- 每分钟扫描一次待重算请求。

## 11. Implementation Plan

### Phase 1：离线表结构

修改：

```text
database/schema.sql
database/tests/
```

完成：

- 新增 raw 事件表。
- 新增离线日汇总表。
- 新增报表表。
- 新增批处理运行记录表。
- 新增重算请求表。

测试：

```powershell
python -m unittest discover -s database\tests -v
git diff --check
```

### Phase 2：实时链路补历史归档

修改：

```text
spark_jobs/kafka_streaming_to_mysql.py
spark_jobs/kafka_streaming_to_mysql_py36.py
spark_jobs/tests/
```

完成：

- Spark Streaming 每消费一条标准事件，同时写入 `raw_video_stat_events`。
- 多达人、多平台、多视频事件可以正确区分。

测试：

```powershell
python -m unittest discover -s spark_jobs\tests -v
```

虚拟机验证：

```text
生成事件 -> Flume -> Kafka -> Spark Streaming -> raw_video_stat_events 有新增行
```

### Phase 3：Spark Batch 日级汇总

新增：

```text
spark_jobs/offline_daily_metrics.py
```

完成：

- 按天聚合 raw 事件。
- 写入 `offline_creator_daily_metrics`。
- 写入 `offline_platform_daily_metrics`。
- 写入 `offline_video_daily_metrics`。
- 写入 `offline_content_type_daily_metrics`。
- 写入 `offline_batch_runs`。

测试：

```powershell
python -m unittest discover -s spark_jobs\tests -v
```

手动验证：

```text
给定一天 raw 事件 -> 执行 batch -> 离线汇总表数值正确
```

### Phase 4：周期报表生成

新增：

```text
spark_jobs/offline_reports.py
```

完成：

- 生成日报。
- 生成周报。
- 生成月报。
- 写入 `creator_reports`。

测试：

```text
有离线日汇总 -> 执行 report job -> creator_reports 有 GENERATED 记录
```

### Phase 5：Flask API + 个人中心 UI

修改：

```text
api/app.py
api/mysql_repository.py
api/view_model_builder.py
api/view_model_contract.py
frontend/src/services/api.js
frontend/src/pages/CreatorProfile.vue
```

完成：

- 增加报表列表 API。
- 增加报表详情 API。
- 个人中心「数据报告」读取真实报表。
- 没有报表时显示等待离线任务生成。

测试：

```powershell
python -m unittest discover -s api\tests -v
cd frontend
npm run build
```

浏览器验证：

```text
登录 -> 个人中心 -> 数据报告
能看到日报/周报/月报或合理空状态
```

### Phase 6：离线调度与批量重算

新增：

```text
scripts/run_offline_daily.sh
scripts/run_offline_reports.sh
scripts/run_offline_recompute_worker.sh
scripts/status_offline_jobs.sh
```

完成：

- 虚拟机 cron 定时运行离线任务。
- API 可以提交重算请求。
- worker 扫描 `offline_recompute_requests` 并执行重算。
- 任务结果写入 `offline_batch_runs`。

测试：

```text
手动插入一条 PENDING 重算请求
worker 执行
请求状态变为 SUCCESS 或 FAILED
offline_batch_runs 有运行记录
报表被重新生成
```

## 12. Success Criteria

完成后系统应满足：

- 实时页面仍然正常显示。
- Kafka / Spark Streaming 事件可以归档到 `raw_video_stat_events`。
- 离线任务可以按日期范围生成日级汇总。
- 系统可以生成日报、周报、月报。
- 个人中心「数据报告」展示真实报表，而不是静态 mock 文案。
- 批量重算不会直接耦合前端和 Spark，而是通过数据库请求表解耦。
- 每次离线任务都有 `offline_batch_runs` 可追踪。
- 多达人数据通过 `creator_id` 完整隔离。

## 13. Risks

### 13.1 数据量增长

`raw_video_stat_events` 会持续变大。

MVP 先保留在 MySQL，后续如果数据量变大，可以迁移到：

```text
HDFS
对象存储
分区文件
ClickHouse
```

但当前阶段不要过早引入。

### 13.2 指标口径不统一

离线汇总公式必须和实时指标公式保持一致，否则用户会看到：

```text
实时页显示健康度 80
日报显示健康度 65
```

解决方式：

- 把健康度、粘性指数、转粉率公式写成公共函数。
- Spark Streaming 和 Spark Batch 使用同一套公式。

### 13.3 重算覆盖历史结果

重算时不能无记录覆盖。

解决方式：

- 每次重算生成新的 `batch_run_id`。
- 离线结果表保留 `batch_run_id`。
- `creator_reports` 使用 upsert，但保留 `generated_at` 和 `batch_run_id`。

### 13.4 前端展示过早开发

如果先做前端报告卡片，而后端没有真实报表，容易重新变成 mock。

解决方式：

开发顺序必须是：

```text
schema -> raw 归档 -> batch 汇总 -> report 表 -> API -> UI
```

## 14. Open Questions

1. 日报生成时间是否固定为每天 00:20，还是允许用户配置？
2. 周报周期是否固定为周一到周日？
3. 月报是自然月，还是按注册日起每 30 天？
4. 报表是否需要导出 PDF？
5. 管理端离线状态是放在 `/admin/simulation`，还是新建 `/admin/offline`？

MVP 默认：

```text
日报：自然日
周报：周一到周日
月报：自然月
报表导出：暂不做
管理端状态：先放入 /admin/simulation 或后端 API，不新增复杂页面
```
