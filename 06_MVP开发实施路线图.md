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

状态：已完成 Vue/Vite 前两条纵切面，代码位于 `frontend/`，当前已迁移增长总览和粉丝分析，并接入 Flask mock API。

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
cd frontend
npm run build
npm run test:smoke
```

当前剩余：

1. 迁移视频分析、内容分布、机会建议、个人中心。
2. 增加正式路由。
3. 将公共 UI 抽成组件。

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

下一步最应该开始的任务是：

```text
MySQL 表结构 + .env.example + mock 数据导入脚本
```

建议拆成 5 个小任务：

### Task 1：整理 MySQL 建表 SQL

产出：

```text
database/schema.sql
```

验收：

1. 表结构覆盖 MVP 数据对象。
2. 主键、外键、时间字段、平台字段清晰。
3. 不按 UI 卡片建表。

### Task 2：增加本地配置模板

产出：

```text
.env.example
```

验收：

1. 包含 MySQL 连接配置。
2. 包含数据源切换配置 `CREATORPULSE_DATA_SOURCE`。
3. 不包含真实用户名和密码。

### Task 3：编写 mock 数据导入脚本

产出：

```text
database/import_mock_to_mysql.py
```

验收：

1. 能读取 `mvp_mock/data/creatorpulse_mvp_mock.json`。
2. 能按正确顺序写入 MySQL。
3. 重复执行时不会造成不可控重复数据。

### Task 4：增加 MySQL Repository

产出：

```text
api/mysql_repository.py
api/config.py
```

验收：

1. `mock` 模式继续读取 JSON。
2. `mysql` 模式读取 MySQL。
3. API 响应结构不变。

### Task 5：补充双数据源测试

产出：

```text
api/tests/test_mock_api.py
api/tests/test_mysql_repository.py
```

验收：

1. mock API 测试继续通过。
2. MySQL 相关测试可以在有本地数据库时运行。
3. 没有配置数据库时，测试能明确跳过或给出清晰提示。

---

## 13. 阶段性结论

CreatorPulse 现在已经过了“UI 是否成立”和“mock API 是否能驱动页面”的阶段，下一阶段的核心问题是：

```text
这套 MVP 数据能不能稳定落到 MySQL，并且让 API 在 mock / MySQL 之间平滑切换？
```

近期主线应该是：

```text
Vue 只调用 Flask API
Flask API 只读 mock JSON 或 MySQL
Spark 通过 JDBC 写 MySQL
Kafka 只作为后续数据流输入，不阻塞 MySQL / Flask / Vue 主线
```

这样做的好处是：页面、API、数据库、Spark、Kafka 每一层都能独立验收。后面某一层出问题时，可以快速判断是数据模型、数据库连接、虚拟机网络，还是流式计算本身的问题。
