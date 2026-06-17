# CreatorPulse MVP 开发实施路线图

> 适用阶段：UI 设计完成后到第一版可运行 MVP  
> 依据文档：`01_业务需求文档.md`、`04_数据字段与页面映射SPEC.md`、`04A_MVP数据Mock与Insight实现SPEC.md`、`05_UI设计/最终版`  
> 核心目标：把当前静态 UI 原型推进为“统一 mock 数据驱动 + 可解释 Insight + API ViewModel”的可运行 MVP，再逐步接入 MySQL、Kafka、Spark。

---

## 1. 当前状态判断

当前已经完成：

1. 6 个一级页面的 UI 原型：
   - 增长总览
   - 粉丝分析
   - 视频分析
   - 内容分布
   - 机会建议
   - 个人中心
2. 顶部 Tab 已经从“首页模块拆解”调整为独立工作台。
3. 页面信息密度已经初步收敛为“诊断 + 证据 + 行动”。
4. 已有数据字段与页面映射 SPEC。
5. 已有 MVP 数据 Mock 与 Insight 实现 SPEC。

当前还没有完成或还需要继续推进：

1. Vue 前端工程化迁移剩余 4 个页面。
2. MySQL 表结构、迁移 SQL 和 mock 数据导入。
3. Flask API 从 mock JSON 数据源切换到 MySQL 数据源的能力。
4. Spark 通过 JDBC 写入 MySQL 的最小验证。
5. Kafka 虚拟机连通性测试。
6. Kafka -> Spark -> MySQL 的完整数据链路。

因此，接下来不建议直接做 Kafka / Spark。现在最重要的是先把静态 UI 变成统一数据驱动的 MVP。

---

## 2. 总体开发顺序

推荐顺序：

```text
统一 mock 数据
  -> 指标计算
    -> Insight 规则引擎
      -> API ViewModel
        -> Flask mock API
          -> Vue 前端接入
            -> 本机 MySQL 落库准备
              -> Flask API 支持 MySQL 数据源
                -> Spark JDBC 写 MySQL 最小验证
                  -> Kafka 虚拟机连通性测试
                    -> Kafka -> Spark -> MySQL 数据流
                      -> SparkSQL / MLlib 推荐增强
```

原因：

1. UI 已经基本完成，现在最大风险是数据不一致。
2. 如果先做 Kafka / Spark，会很容易产出一堆数据，但页面不知道怎么消费。
3. 先做 ViewModel 和 Insight，可以明确后端到底要返回什么。
4. 后续从 mock JSON 替换成 MySQL / Spark 结果时，前端结构不用推倒重来。
5. Kafka / Spark 运行在虚拟机里，网络连通和 `advertised.listeners` 风险较高，应该解耦到后面单独验证。

---

## 3. 阶段一：统一 Mock 数据与 Insight MVP

状态：已完成第一版可运行纵切面，代码位于 `mvp_mock/`。

### 目标

实现 `04A_MVP数据Mock与Insight实现SPEC.md` 中定义的 MVP 数据层。

### 交付物

1. mock 数据生成器。
2. 统一 mock 数据 JSON。
3. 指标计算函数。
4. 第一版 Insight 规则引擎。
5. 页面 ViewModel 数据结构。

### Mock 数据范围

第一版生成：

| 数据类型 | 数量 |
|---|---:|
| 达人 | 1 个 |
| 平台 | 3 个：抖音、B站、小红书 |
| 视频 | 每个平台 8-10 条 |
| 视频快照 | 每条视频 1 条最新快照 |
| 账号趋势 | 整体 7 天趋势 |
| 粉丝画像 | 1 份 |
| 热点话题 | 10 条 |
| Insight | 20-30 条 |

### Insight 实现范围

MVP 只实现第一阶段：

```text
规则 + 文案模板
```

暂不实现 AI 自动分析。

第一阶段规则包括：

1. 高转粉视频机会。
2. 高播放低转粉风险。
3. 教程内容加码。
4. 测评内容评论机会。
5. 低粘性风险。
6. 平台投入调整。
7. 发布时间机会。
8. 热点机会。
9. 授权风险。

### 验收标准

1. 同一条视频在不同页面出现时，播放、新粉、转粉率一致。
2. 百分比指标由公式计算，不手写。
3. 每条 Insight 至少有 2 个证据指标。
4. 每条 Insight 至少有 1 个行动建议。
5. 页面诊断条可以从 Insight 中选取，而不是写死文案。

当前验证命令：

```powershell
python mvp_mock\generate_mock.py
python mvp_mock\validate_mock.py
```

---

## 4. 阶段二：页面 ViewModel 与 Flask Mock API

状态：已完成 Flask mock API 第一版，代码位于 `api/`。

### 目标

先不接数据库，使用 mock JSON 提供后端 API，让前端页面可以通过接口获取数据。

### 推荐 API

```text
GET /api/creators/demo/dashboard/growth
GET /api/creators/demo/fans
GET /api/creators/demo/videos
GET /api/creators/demo/distribution
GET /api/creators/demo/opportunities
GET /api/creators/demo/profile
```

### ViewModel 原则

API 返回页面可直接消费的数据，但不能发明新指标。

例如增长总览：

```ts
interface GrowthDashboardViewModel {
  creator: Creator;
  currentSnapshot: CreatorMetricSnapshot;
  platformSnapshots: CreatorMetricSnapshot[];
  topVideos: VideoMetricSnapshot[];
  insights: Insight[];
  sections: {
    overview: PageSection;
    conversion: PageSection;
    stickiness: PageSection;
    distribution: PageSection;
  };
}
```

### 验收标准

1. 每个一级页面都有对应 API。
2. API 返回数据能覆盖当前 UI 的主要模块。
3. Insight 能按页面和 Tab 分发。
4. 前端不需要自己计算复杂业务结论。

当前已补充的接口合同：

1. `api/openapi_contract.py` 生成 MVP OpenAPI 3.0.3 schema。
2. Flask 暴露 `GET /api/openapi.json`，用于查看健康检查和 6 个页面 ViewModel 接口。
3. `api/tests/test_openapi_contract.py` 校验 OpenAPI 路径和关键 schema。

当前验证命令：

```powershell
python api\tests\test_mock_api.py
```

本地启动命令：

```powershell
python api\app.py
```

---

## 5. 阶段三：前端工程化迁移

状态：已完成 Vue/Vite 第一版，代码位于 `frontend/`。当前 6 个一级页面均已迁移，并接入 Flask mock API。

### 目标

把当前静态 HTML 原型迁移为 Vue.js 页面，并接入 Flask mock API。

### 推荐策略

不要重做视觉设计。保留当前：

1. 侧边栏结构。
2. 顶部 Tab 结构。
3. 深色玻璃拟态风格。
4. 诊断条、卡片、表格、行动清单等组件样式。

迁移顺序：

1. 搭建 Vue 工程。
2. 抽取 Layout：侧边栏、页面容器、顶部 Tab。
3. 抽取公共组件：
   - DiagnosisStrip
   - DiagnosisCard
   - MetricCard
   - ActionList
   - DataTable
   - BarStack
   - HeatGrid
4. 先迁移增长总览。
5. 再迁移粉丝分析。
6. 最后迁移剩余页面。

### 验收标准

1. Vue 版本视觉上与当前静态 HTML 基本一致。
2. 6 个一级页面都能通过路由访问。
3. 顶部 Tab 能正常切换。
4. 数据来自 API，而不是写死在模板里。
5. 窄屏布局不溢出、不重叠。

当前已验证：

```powershell
python scripts\verify_mvp.py
```

当前剩余：

1. 后续如需要真实多路由，可从当前 `?page=` 轻量路由迁移到 Vue Router。
2. 公共 UI 组件仍可继续抽取，但当前第一版已通过烟测。
3. 后续页面数据源切换到 MySQL 时，前端接口不需要改响应结构。

---

## 6. 阶段四：本机 MySQL 落库准备

### 目标

把已经跑通的 mock JSON 数据结构落到你本机的 MySQL。这个阶段只解决“表怎么建、mock 数据怎么导入、配置怎么填”，不要求 Kafka / Spark 参与。

### 关键澄清

1. Flask / Python 访问 MySQL 不叫 JDBC，推荐使用 SQLAlchemy + PyMySQL。
2. JDBC 主要留给 Spark 写 MySQL 时使用。
3. 数据库地址、端口、用户名、密码不能写死进代码，使用 `.env` 或本地环境变量。
4. 仓库只提交 `.env.example`，真实 `.env` 由你在本机填写，并加入 `.gitignore`。

### MVP 推荐表

```text
creators
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
```

### 实施内容

1. 编写 MySQL 建表 SQL 或迁移脚本。
2. 编写 `.env.example`，包含数据库连接模板。
3. 编写 mock JSON 导入 MySQL 的一次性脚本。
4. 保留 mock JSON 作为可回退数据源。
5. 建表继续按数据对象和业务事实建，不按 UI 卡片建。

### 推荐配置示例

```env
CREATORPULSE_DATA_SOURCE=mock
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=creatorpulse
MYSQL_USER=your_user
MYSQL_PASSWORD=your_password
```

### 验收标准

1. 本机 MySQL 能建出 MVP 所需表结构。
2. mock JSON 可以导入 MySQL。
3. 导入后核心数量对得上：达人、平台账号、视频、快照、画像、热点、Insight。
4. 仓库中没有真实数据库密码。

---

## 7. 阶段五：Flask API 切换到 MySQL 数据源

### 目标

让 Flask API 支持两种数据源：mock JSON 和 MySQL。页面接口返回结构保持不变，前端不需要知道数据来自哪里。

### 数据源策略

```text
CREATORPULSE_DATA_SOURCE=mock   -> 读取 mvp_mock/data/creatorpulse_mvp_mock.json
CREATORPULSE_DATA_SOURCE=mysql  -> 读取本机 MySQL
```

### 实施内容

1. 增加数据库连接配置读取。
2. 增加 MySQL Repository。
3. 保留现有 Mock Repository。
4. 增加 Repository 工厂，根据环境变量选择数据源。
5. 复用现有 ViewModel 结构，不因为换数据库改 API 响应。

### 验收标准

1. `mock` 模式下现有 API 测试继续通过。
2. `mysql` 模式下同一批 API 返回同样结构的 ViewModel。
3. Vue 页面不需要修改即可从 MySQL 数据源读取数据。
4. 数据库连接失败时有清晰错误，不静默返回假数据。

当前已补充的合同保护：

1. `api/view_model_contract.py` 定义 6 个页面 ViewModel 必须包含的关键字段。
2. `api/tests/test_view_model_contract.py` 同时校验 mock API 响应和 MySQL 映射后的 ViewModel。
3. `api/tests/test_mock_api.py` 已复用合同校验，避免后续字段漂移导致前端运行时才报错。

---

## 8. 阶段六：Spark JDBC 写 MySQL 最小验证

### 目标

先验证 Spark 能通过 JDBC 写入你本机 MySQL。这个阶段不接 Kafka，只使用静态 mock JSON / CSV 做输入。

### 为什么先不接 Kafka

Kafka 在虚拟机里，涉及 Windows 主机到虚拟机的网络、端口、监听地址和防火墙。把它提前接进来，会让问题来源变复杂。先验证 Spark -> MySQL，可以单独确认计算结果能进入后端 API 依赖的数据表。

### 实施内容

1. 准备 Spark 可读取的静态 mock JSON / CSV。
2. 用 Spark 计算 1-2 个最小指标，例如平台播放汇总、视频涨粉贡献。
3. 通过 JDBC 写入 MySQL 的临时结果表或快照表。
4. 提供 JDBC 配置模板，真实用户名和密码由你本机填写。

### 推荐 JDBC 配置项

```env
SPARK_MYSQL_JDBC_URL=jdbc:mysql://host.docker.internal:3306/creatorpulse
SPARK_MYSQL_USER=your_user
SPARK_MYSQL_PASSWORD=your_password
SPARK_MYSQL_DRIVER=com.mysql.cj.jdbc.Driver
```

具体 host 写法要看 Spark 运行位置：

1. Spark 在 Windows 本机运行：通常用 `127.0.0.1`。
2. Spark 在虚拟机运行，MySQL 在 Windows 本机：通常需要填写 Windows 主机在虚拟机可访问的 IP。
3. Spark 在 Docker 中运行：可能需要 `host.docker.internal` 或网桥地址。

### 验收标准

1. Spark 能读取静态 mock 数据。
2. Spark 能通过 JDBC 成功写入 MySQL。
3. MySQL 中能查询到 Spark 计算结果。
4. Flask API 后续可以读取这些结果，但本阶段不强制打通页面。

当前已完成的 dry-run 闭环：

1. `spark_jobs/static_mock_to_mysql.py` 可以从静态 mock 数据计算平台播放汇总和视频涨粉贡献。
2. `database/import_mock_to_mysql.py` dry-run 和真实导入都会包含两张 Spark 结果表：
   - `spark_platform_metric_summaries`
   - `spark_video_follower_contributions`
3. Flask 的 mock / MySQL Repository 已统一暴露 Spark 输出字段：
   - `videoAnalysis.sparkContributions`
   - `contentDistribution.sparkPlatformSummaries`
4. Vue 的视频分析、内容分布页面已优先消费这些 Spark 输出字段，字段为空时回退到前端聚合。

`python spark_jobs\static_mock_to_mysql.py` 不带 `--execute` 时是 dry-run，会输出 `executionPlan`，展示两张 Spark 结果表、JDBC 写入模式和预计写入行数，不会触发 JDBC 写入。

真实 JDBC 写入仍需要你在 `.env` 中填写 `SPARK_MYSQL_JDBC_URL`、`SPARK_MYSQL_USER`、`SPARK_MYSQL_PASSWORD`、`SPARK_MYSQL_DRIVER` 后执行：

```powershell
spark-submit spark_jobs\static_mock_to_mysql.py --execute
```

---

## 9. 阶段七：Kafka 虚拟机连通性测试

### 目标

单独验证 Windows 本机、虚拟机 Kafka、后续 Spark 程序之间的网络连通。这个阶段不改 Flask，不改 Vue，也不影响 MySQL 主线。

### 测试重点

1. Windows 能访问虚拟机 IP。
2. Windows 能访问 Kafka 端口，例如 `9092`。
3. Kafka 的 `advertised.listeners` 对 Windows 主机可用。
4. 最小 producer / consumer 能发送和消费消息。
5. Spark 所在环境也能访问同一个 Kafka 地址。

### 推荐检查命令

```powershell
ping <vm-ip>
Test-NetConnection <vm-ip> -Port 9092
```

### 推荐 Topic

```text
video_stats_topic
creator_stats_topic
comment_topic
danmaku_topic
topic_trend_topic
```

### 验收标准

1. Windows 本机可以生产和消费 Kafka 消息。
2. Spark 运行环境可以消费 Kafka 消息。
3. Kafka 消息字段能映射到 MVP 数据契约。
4. Kafka 连接配置独立于 Flask / Vue，不阻塞页面开发。

当前已完成的 dry-run / opt-in 能力：

1. `kafka_tools/check_connectivity.py` 可以检查 VM Kafka host:port。
2. `kafka_tools/mock_producer.py` 默认生成本地 NDJSON，`--execute-kafka` 才真实生产消息。
3. `kafka_tools/mock_consumer.py` 默认校验本地 NDJSON，`--execute-kafka` 才真实消费 Kafka。
4. `kafka_tools/run_closed_loop.py` 已提供一键闭环：

```text
mock data -> NDJSON producer -> NDJSON consumer validation -> offline Spark-style aggregation
```

`python kafka_tools\run_closed_loop.py` 不带 `--execute-kafka` 时会输出 `executionPlan`，展示本地闭环步骤、计划事件数、事件类型覆盖和离线 Spark 聚合行数，不会连接 Kafka。

真实 Kafka 闭环仍需要你填写 `.env` 中的 `KAFKA_BOOTSTRAP_SERVERS` 并确认虚拟机网络后执行：

```powershell
python kafka_tools\run_closed_loop.py --execute-kafka
```

---

## 10. 阶段八：Kafka -> Spark -> MySQL 完整数据流

### 目标

在 MySQL、Flask API、Spark JDBC、Kafka 连通性都已验证后，再把它们串成完整链路。

### 推荐链路

```text
模拟平台数据生产者
  -> Kafka Topic
    -> Spark Streaming
      -> MySQL 快照表 / 聚合表
        -> Flask API
          -> Vue 页面
```

### Spark Streaming 优先项

1. 实时总播放量。
2. 实时粉丝增长。
3. 实时播放转粉率。
4. 新视频涨粉表现。
5. 异常流量与掉粉检测。

### SparkSQL 优先项

1. 全平台日报。
2. 内容类型效率。
3. 发布时间效率。
4. 流量来源质量。
5. 单视频涨粉贡献。
6. 粉丝粘性分析。

### MLlib / 推荐增强优先项

1. 选题推荐。
2. 发布时间推荐。
3. 标题关键词建议。
4. 平台侧重建议。
5. 热点适配评分。

### 验收标准

1. Kafka 数据可以经过 Spark 写入 MySQL。
2. Spark 输出结果能进入现有 ViewModel。
3. Insight 可以从 SparkSQL 结果生成。
4. 推荐建议必须包含证据指标，不能只输出结论。

当前已完成的离线 dry-run 能力：

1. `kafka_tools/mock_producer.py` 可以生成 Kafka 风格 NDJSON 事件。
2. `spark_jobs/kafka_events_to_mysql.py` 可以离线聚合这些事件，产出与 Spark JDBC 表一致的结果行。
3. `kafka_tools/run_closed_loop.py` 可以把事件生成、消费校验、离线 Spark 聚合串成一个本地闭环。
4. `api/spark_insights.py` 已基于 Spark 聚合输出生成 `SPARK_RULE_ENGINE` Insight。
5. 这些 Insight 带有证据指标和行动建议，并进入 `video.contribution`、`content.platform`、`growth.distribution`、`opportunities.reference` 等页面目标。

`python spark_jobs\kafka_streaming_to_mysql.py` 不带 `--execute` 时会输出 `executionPlan`，展示源 topic、触发间隔、checkpoint、output mode、MySQL 写入模式、目标结果表，以及 `--execute` 和 `CREATORPULSE_RUN_FULL_PIPELINE_LIVE=1` 两层门禁，不会启动 Spark Streaming。

真实 Kafka -> Spark -> MySQL 链路仍等待虚拟机 Kafka 连通性和本机 `.env` 配置确认后执行。

---

## 11. 不建议现在做的事情

当前阶段不建议优先做：

1. 直接接真实平台 API。
2. 一开始就做 6 个平台全量模拟。
3. 一开始就生成每个平台 1 万条数据。
4. 让 Flask / Vue 直接依赖 Kafka 或 Spark。
5. 在代码里写死数据库用户名、密码、JDBC URL。
6. 跳过 MySQL，直接把 Kafka / Spark 做成页面数据源。
7. 用 AI 直接生成所有建议文案。
8. 按 UI 卡片设计数据库表。

这些事情不是不做，而是应该放在数据契约、mock API、MySQL 数据源切换和 Spark JDBC 最小验证之后。

---

## 12. 推荐下一步任务

当前 MySQL 表结构、`.env.example`、mock 导入脚本、MySQL Repository、双数据源合同测试、Spark dry-run、Kafka 风格 dry-run 都已经完成。下一步不应该继续扩大功能面，而是进入“真实服务接入前的门禁验证”：

```text
数据契约与质量审计
  -> 本机 MySQL 真实导入
    -> Spark JDBC 真实写入 MySQL
      -> Kafka 虚拟机真实连通
```

### Task 1：数据契约与质量审计

产出：

```text
scripts/audit_data_contract.py
scripts/tests/test_audit_data_contract.py
scripts/audit_data_quality.py
scripts/tests/test_audit_data_quality.py
```

作用：

1. 比对 `database/schema.sql` 中的表字段和 `database/import_mock_to_mysql.py` 实际写入字段。
2. 校验 mock 行能还原 MySQL Repository 数据契约。
3. 校验 6 个页面 ViewModel 满足 `api/view_model_contract.py`。
4. 校验 OpenAPI 页面路径和关键字段没有漂移。
5. 在真实 MySQL / Spark / Kafka 接入前，先发现字段缺失和命名不一致。
6. 输出对象覆盖报告，说明每个 MVP 数据对象是否已经入库、是否进入页面 ViewModel，或是否只是当前阶段的 stored-only 数据。
7. 校验 mock 数据公式、流量来源汇总、账号趋势、Spark dry-run 聚合结果和 Insight 证据链是否自洽。

当前已完成并纳入总验证：

```powershell
python scripts\audit_data_contract.py
python scripts\tests\test_audit_data_contract.py
python scripts\audit_object_coverage.py
python scripts\tests\test_audit_data_quality.py
python scripts\audit_data_quality.py
python scripts\export_openapi.py --check
python scripts\report_env_readiness.py
python scripts\verify_mvp.py --skip-browser
```

### Task 2：本机 MySQL 真实导入

产出：

```text
database/schema.sql
database/apply_schema.py
database/import_mock_to_mysql.py
scripts/init_env.py
scripts/setup_local_mysql.py
```

验收：

1. `python scripts\init_env.py` 能从 `.env.example` 安全初始化 `.env`，默认不覆盖已有本地配置。
2. 由你在 `.env` 填写本机 MySQL 用户、密码、端口和库名。
3. `python scripts\preflight.py --target local-mysql --strict` 通过；该检查会验证 TCP、占位值和 MySQL 登录，但不会建库或写入数据。
4. `python scripts\setup_local_mysql.py` 不带 `--execute` 时会输出 `executionPlan`，展示 strict preflight、建表、导入、行数校验和 API 合同验证的计划步骤，以及预计写入的表和行数。
5. `python scripts\setup_local_mysql.py --execute` 会自动启用 strict preflight，只有无 warning 时才建表、导入 mock 数据、逐表校验 MySQL 实际行数，并用 MySQL 模式验证 API 合同。
6. `python api\tests\test_mysql_api_integration.py` 在真实数据库存在时通过；没有 `.env` 时跳过。
7. 仓库不提交真实 `.env` 和密码。

### Task 3：Spark JDBC 真实写入 MySQL

产出：

```text
spark_jobs/static_mock_to_mysql.py
spark_jobs/tests/test_static_mock_to_mysql.py
```

验收：

1. 由你在 `.env` 填写 `SPARK_MYSQL_JDBC_URL`、`SPARK_MYSQL_USER`、`SPARK_MYSQL_PASSWORD`、`SPARK_MYSQL_DRIVER`。
2. `python scripts\preflight.py --target spark-jdbc --strict` 通过；该检查会验证 `spark-submit`、MySQL TCP、JDBC URL 格式、MySQL Connector/J driver、`SPARK_MYSQL_WRITE_MODE=append` 和 MySQL 登录状态。
3. 设置 `CREATORPULSE_RUN_SPARK_JDBC_LIVE=1` 后，`python spark_jobs\tests\test_static_mysql_jdbc_integration.py` 能通过。
4. `python spark_jobs\static_mock_to_mysql.py` dry-run 会输出 `executionPlan`，说明目标表、写入模式和计划行数。
5. `spark-submit spark_jobs\static_mock_to_mysql.py --execute` 自身会拒绝占位凭据、非 MySQL JDBC URL、非 MySQL driver 和非 `append` 写入模式；通过后能把平台汇总和视频涨粉贡献写入 MySQL。
6. Flask API 读取 MySQL 后，`videoAnalysis.sparkContributions` 和 `contentDistribution.sparkPlatformSummaries` 仍然有数据。

### Task 4：Kafka 虚拟机真实连通

产出：

```text
kafka_tools/check_connectivity.py
kafka_tools/run_closed_loop.py
```

验收：

1. 由你确认虚拟机 IP、Kafka 端口、防火墙和 `advertised.listeners`。
2. 由你在 `.env` 填写 `KAFKA_BOOTSTRAP_SERVERS`。
3. `python scripts\preflight.py --target kafka --strict` 通过；该检查会验证 bootstrap server 格式，并拒绝 `.env.example` 中的模板值 `192.168.56.10:9092`。
4. 设置 `CREATORPULSE_RUN_KAFKA_LIVE=1` 后，`python kafka_tools\tests\test_kafka_live_integration.py` 能通过。
5. `python kafka_tools\run_closed_loop.py` dry-run 会输出 `executionPlan`，说明本地事件闭环、计划事件数和离线聚合行数。
6. `python kafka_tools\run_closed_loop.py --execute-kafka` 会先拒绝占位或格式错误的 Kafka bootstrap 配置；通过后能真实生产和消费 MVP 事件。
7. Kafka 测试继续与 Flask / Vue 解耦，不阻塞页面和 MySQL 主线。

### Task 5：Kafka -> Spark -> MySQL 完整链路

产出：

```text
spark_jobs/kafka_streaming_to_mysql.py
spark_jobs/tests/test_kafka_streaming_to_mysql.py
scripts/preflight.py --target full-pipeline
scripts/tests/test_verify_mvp.py
scripts/report_env_readiness.py
scripts/tests/test_report_env_readiness.py
scripts/run_real_service_sequence.py
scripts/tests/test_run_real_service_sequence.py
scripts/report_real_service_plans.py
scripts/tests/test_report_real_service_plans.py
scripts/report_execution_checklist.py
scripts/tests/test_report_execution_checklist.py
scripts/audit_real_service_readiness.py
scripts/tests/test_audit_real_service_readiness.py
scripts/export_real_service_report_bundle.py
scripts/tests/test_export_real_service_report_bundle.py
```

验收：

1. Kafka 真实连通已经验证。
2. Spark JDBC 真实写 MySQL 已经验证。
3. `python spark_jobs\kafka_streaming_to_mysql.py` dry-run 会输出 `executionPlan`，确认源 topic、checkpoint、输出模式、目标表和双重执行门禁。
4. `spark_jobs/kafka_streaming_to_mysql.py --execute` 能把 Kafka 事件聚合后写入 MySQL 结果表。
5. 结果表进入现有 Flask ViewModel，不要求前端改接口。
6. 新增 Insight 必须继续包含证据指标和行动建议。

当前已完成的本地 dry-run 验证入口：

```powershell
python scripts\status_mvp.py
python scripts\report_env_readiness.py
python scripts\run_real_service_sequence.py
python scripts\report_real_service_plans.py
python scripts\report_real_service_plans.py --stage mysql
python scripts\report_real_service_plans.py --stage spark-jdbc
python scripts\report_real_service_plans.py --stage kafka
python scripts\report_real_service_plans.py --stage full-pipeline
python scripts\report_execution_checklist.py
python scripts\report_execution_checklist.py --stage mysql
python scripts\report_execution_checklist.py --stage spark-jdbc
python scripts\report_execution_checklist.py --stage kafka
python scripts\report_execution_checklist.py --stage full-pipeline
python scripts\audit_real_service_readiness.py
python scripts\export_real_service_report_bundle.py
python scripts\preflight.py --target full-pipeline
python scripts\audit_data_contract.py
python scripts\audit_data_quality.py
python scripts\verify_mvp.py --skip-browser
```

`python scripts\status_mvp.py` 会输出 `nextRecommendedStep`。当前没有 `.env` 时，它会先推荐 `python scripts\init_env.py`；当 `.env` 已配置但某个真实服务还不可达时，它会推荐对应的 strict preflight；当 MySQL、Spark JDBC、Kafka 单项都通过后，会先推荐 `python scripts\preflight.py --target full-pipeline --strict`，只有全部 preflight 无 warning 时，才推荐进入真实 streaming 执行命令。状态报告也会输出 `nextRolloutStage` 和 `nextRolloutPlan`，直接给出下一阶段的 dry-run 前置条件与命令列表。

`python scripts\status_mvp.py` 现在也内嵌 `envReadiness`，因此主状态报告会同时显示下一阶段、`.env` 阻塞字段、preflight 结果和 rollout plan。它还会输出 `realServiceReadinessSummary`，用于快速查看哪些 rollout 阶段仍被阻塞、哪些阶段已经可以进入 strict preflight、哪些阶段已经满足 guarded execute 前置条件，以及下一批最应该补齐的 `.env` key。这个摘要仍然只是只读状态报告，不会写 MySQL、不会连接 Kafka、不会启动 Spark Streaming。你可以继续单独运行 `python scripts\report_env_readiness.py`，只查看脱敏后的 `.env` 字段状态。

`python scripts\report_env_readiness.py` 会按 `localMysql`、`sparkJdbc`、`kafka`、`fullPipeline` 四个阶段列出 `.env` 字段状态，明确哪些字段仍是 missing / placeholder。密码、token、secret、key 类字段只输出 `***`，不会做网络检查，也不会写任何外部服务。

`python scripts\run_real_service_sequence.py` 会以 JSON 输出真实服务接入顺序：本机 MySQL 预检、MySQL 导入、Spark JDBC 预检、Spark JDBC live test、Kafka 预检、Kafka live test、full-pipeline 预检、最后才是 streaming 执行。也可以用 `--stage mysql`、`--stage spark-jdbc`、`--stage kafka`、`--stage full-pipeline` 只查看单个阶段的前置条件和命令。当前 MVP 中它只做 dry-run 展示，所有步骤的 `willExecute` 都是 `false`，不会建表、不会连 Kafka、不会启动 Spark Streaming。

`python scripts\report_real_service_plans.py` 会把本机 MySQL、Spark JDBC 静态写入、Kafka 本地闭环、Kafka -> Spark -> MySQL Streaming 四个阶段的 `executionPlan` 汇总到一份 JSON 中，便于在填真实 `.env` 前一次性检查计划写入表、预计行数、事件数、topic、checkpoint 和执行门禁。它支持 `--stage mysql|spark-jdbc|kafka|full-pipeline` 聚焦单个阶段。它也是只读 dry-run：不会写 MySQL、不会连接 Kafka、不会启动 Spark Streaming。

`python scripts\report_execution_checklist.py` 会把脱敏 `.env` 状态、preflight summary、人工门禁和 rollout steps 合并成真实执行前清单，明确每个阶段是否 `readyForStrictPreflight` / `readyForExecute`，以及被哪些字段或 warning 阻塞。它支持 `--stage mysql|spark-jdbc|kafka|full-pipeline` 聚焦单个阶段。它同样只读，不会执行任何 `--execute` 命令。

`python scripts\audit_real_service_readiness.py` 会交叉检查真实服务顺序、执行计划报告和执行前清单，确保三者使用同一套 rollout 阶段名、`--stage` 过滤结果一致，并且 dry-run 安全门禁保持关闭。它用于防止后续修改某一个脚本时，另一个脚本还停留在旧阶段名或错误的执行标志上。

`python scripts\export_real_service_report_bundle.py` 会把当前状态、`.env` readiness、真实服务顺序、执行计划、执行前清单和 readiness 审计一次性导出到本地目录，并生成 `manifest.json`。它同样只读，不会写 MySQL、不会连接 Kafka、不会启动 Spark Streaming，适合在你填 `.env` 前后各导出一份报告做对比。

这些只读报告命令也支持可选 `--output` 导出 JSON 文件，例如：

```powershell
python scripts\report_execution_checklist.py --stage mysql --output reports\mysql-checklist.json
python scripts\audit_real_service_readiness.py --output reports\real-service-readiness-audit.json
python scripts\export_real_service_report_bundle.py --stage mysql --output-dir reports\mysql-readiness-bundle
```

单个报告命令默认不写文件，只有显式传入 `--output` 才会落盘；报告包导出命令会写入 `--output-dir`，默认位于 `reports/` 下。`reports/` 作为本地执行留档目录，已加入 `.gitignore`，避免把本地报告和潜在环境路径信息提交进仓库。

`full-pipeline` 预检会额外校验 `MYSQL_DATABASE` 和 `SPARK_MYSQL_JDBC_URL` 中的数据库名一致，避免 Spark 写入一个库、Flask API 读取另一个库。它不会强制 MySQL host 和 JDBC host 一致，因为 Spark 在虚拟机运行时可能需要通过不同主机地址访问同一个本机 MySQL。

`python scripts\verify_mvp.py --skip-browser` 已经纳入 `full-pipeline` dry-run 预检、真实服务顺序 dry-run 和真实服务 readiness 审计，确保后续修改不会绕过完整链路执行前的组合门禁。真实 `spark-submit spark_jobs\kafka_streaming_to_mysql.py --execute` 仍然等待 `.env`、本机 MySQL、Spark JDBC 和虚拟机 Kafka 都通过 strict preflight 后执行，并且还需要显式设置 `CREATORPULSE_RUN_FULL_PIPELINE_LIVE=1`，避免误启动长时间 streaming 写入任务。

---

## 13. 阶段性结论

CreatorPulse 现在已经过了“UI 是否成立”“mock API 是否能驱动页面”“MVP 数据能否落到 MySQL 结构”“Spark/Kafka dry-run 是否能闭环”的阶段。下一阶段的核心问题是：

```text
在不破坏现有 API/ViewModel 合同的前提下，真实 MySQL、真实 Spark JDBC、虚拟机 Kafka 能不能逐层接入？
```

近期主线应该是：

```text
Vue 只调用 Flask API
Flask API 只读 mock JSON 或 MySQL
Spark 通过 JDBC 写 MySQL
Kafka 只作为后续数据流输入，不阻塞 MySQL / Flask / Vue 主线
每完成一个阶段都跑对应测试，再跑 scripts\verify_mvp.py --skip-browser
```

这样做的好处是：页面、API、数据库、Spark、Kafka 每一层都能独立验收。后面某一层出问题时，可以快速判断是数据模型、数据库连接、虚拟机网络，还是流式计算本身的问题。
