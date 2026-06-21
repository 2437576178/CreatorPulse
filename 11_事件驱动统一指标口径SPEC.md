# 事件驱动统一指标口径 SPEC

## 1. 背景

当前前端页面已经通过 Flask API 读取 MySQL 数据，但 MySQL 中的数据来源还没有完全统一。

现在的数据实际分为三类：

1. 早期静态 Mock 数据导入 MySQL。
2. Kafka / Spark 链路实时生成的部分聚合数据。
3. Flask API 把多张表组装成页面 ViewModel 后返回给 Vue。

这会导致一个问题：页面虽然不是前端硬编码，但不同模块的数据口径可能不一致。例如：

- 账号健康度来自 `creator_metric_snapshots.growth_health_score`，目前主要由静态 Mock 导入。
- Spark 当前只写入平台汇总和视频涨粉贡献相关表。
- 粉丝画像、热点、insight 文案、部分趋势数据仍然来自静态生成结果。

因此下一阶段的重点不是继续扩 UI，而是把数据链路统一成：

```text
标准事件
  ↓
Flume
  ↓
Kafka
  ↓
Spark Streaming / Spark 批处理
  ↓
MySQL 指标表
  ↓
Insight 规则
  ↓
Flask ViewModel
  ↓
Vue 页面展示
```

## 2. 目标

本 SPEC 的目标是固定一条统一原则：

**达人基础档案可以一次性 Mock / 注册生成；后续所有运营指标必须来自标准事件经过 Spark / 后端统一聚合后的数据库结果。**

换句话说：

```text
档案类数据：一次性建档
指标类数据：事件持续流入，Spark / 后端统一计算
页面数据：只读 Flask API ViewModel
```

静态 Mock 的职责必须收窄为“建档”，不能再直接生成核心指标。页面上的核心指标不能由不同模块各自 mock、各自写死、各自推导。

具体目标：

- 明确哪些数据属于一次性档案 Mock。
- 明确哪些数据必须来自原始事件。
- 明确哪些数据必须由 Spark / 后端聚合。
- 明确账号健康度、粘性指数、转粉率等核心指标的统一口径。
- 明确前端只消费 ViewModel，不在页面里重新发明业务公式。

## 3. 当前问题

### 3.1 数据来源混合

当前 MySQL 数据不是全部由事件流生成：

| 数据类型 | 当前来源 | 问题 |
|---|---|---|
| 视频基础信息 | 静态 Mock 导入 | 属于档案类数据，可以一次性建档 |
| 视频播放、点赞、评论、收藏、分享 | 静态 Mock + 部分事件流 | 口径可能不一致 |
| 账号 7 天趋势 | 静态 Mock | 没有由视频事件汇总生成 |
| 账号健康度 | 静态 Mock 简化公式 | 没有按正式公式计算 |
| 粉丝画像 | 静态 Mock | 可作为初始档案快照，后续由画像事件更新 |
| 热点话题 | 静态 Mock | 可作为初始外部参考快照，后续由话题事件更新 |
| Insight | 静态规则生成 + 部分 Spark 合并 | 证据指标来源不完全统一 |
| Spark 平台汇总 | Kafka 事件消费生成 | 已接入链路 |
| Spark 视频涨粉贡献 | Kafka 事件消费生成 | 已接入链路 |

### 3.2 页面看起来散乱的原因

页面不是简单“假数据写死”，而是：

```text
旧 Mock 指标数据 + 新 Spark 聚合数据 + 页面 ViewModel 组装
```

同时存在，导致：

- 有些卡片像实时数据。
- 有些卡片像静态样例。
- 有些指标之间无法完全互相解释。
- 同一个账号的增长、粘性、视频贡献没有完全来自同一批事件。

## 4. 统一数据分层

### 4.0 一次性档案层

一次性档案层只描述“这个达人是谁、绑定了哪些平台、有哪些内容对象”，不直接描述运营表现。

允许一次性 Mock / 注册生成的数据：

| 数据 | 表 | 说明 |
|---|---|---|
| 达人基础信息 | `creators` | 昵称、头像、领域标签、时区 |
| 登录账号 | `users` | 邮箱、密码哈希、账号与 `creator_id` 映射 |
| 平台绑定关系 | `platform_accounts` | 绑定了哪些平台、授权状态、采集权限 |
| 视频基础信息 | `videos` | 视频 ID、标题、平台、内容类型、发布时间 |
| 初始粉丝画像 | `audience_profile_snapshots` | MVP 可用一次性快照，后续可由画像事件替换 |
| 初始热点话题 | `topic_trend_snapshots` | MVP 可用一次性快照，后续可由外部话题事件替换 |

档案层禁止直接生成：

- 播放数。
- 点赞数。
- 评论数。
- 分享数。
- 收藏数。
- 主页访问数。
- 新增粉丝。
- 掉粉。
- 转粉率。
- 粘性指数。
- 账号健康度。
- 视频贡献排行。
- 平台贡献排行。

这些都是指标类数据，必须由事件和聚合产生。

### 4.1 原始事件层

原始事件只负责描述“平台发生了什么”，不直接服务页面。

第一阶段标准事件使用 `video_stats`：

```json
{
  "event_id": "evt_20260620_000001",
  "event_type": "video_stats",
  "platform": "DOUYIN",
  "fetch_time": "2026-06-20T10:00:00+08:00",
  "creator_id": "creator_001",
  "content_id": "video_001",
  "title": "3分钟讲清内容定位",
  "stats": {
    "play_count": 120000,
    "like_count": 8200,
    "comment_count": 460,
    "share_count": 380,
    "save_count": 1200
  },
  "growth": {
    "new_followers": 680,
    "profile_visits": 3200
  }
}
```

后续可扩展事件：

| 事件类型 | 用途 | MVP 阶段 |
|---|---|---|
| `video_stats` | 视频播放、互动、涨粉 | 第一阶段必须实现 |
| `creator_stats` | 账号总粉丝、掉粉、主页访问 | 第一阶段建议实现；没有时必须由视频事件近似 |
| `audience_profile` | 粉丝画像快照 | 第二阶段；第一阶段允许使用初始档案快照 |
| `traffic_source_stats` | 推荐、搜索、关注、分享来源 | 第二阶段 |
| `comment_stats` | 评论情感、问题评论、负面信号 | 第三阶段 |
| `topic_trend` | 热点话题 | 第二阶段或第三阶段；第一阶段允许使用初始外部参考快照 |

### 4.2 指标快照层

指标快照是页面真正应该消费的数据。

原则：

- 快照表可以由 Spark 写入。
- 也可以由后端定时任务写入。
- 但同一张表必须只有一个主口径。
- 页面不能绕过快照表直接拼原始事件。

核心快照表：

| 表 | 职责 | 第一阶段要求 |
|---|---|---|
| `video_metric_snapshots` | 每条视频最新指标 | 应由 `video_stats` 事件聚合写入 |
| `creator_metric_snapshots` | 账号每日趋势和健康度 | 应由视频快照 + 账号快照聚合写入 |
| `video_traffic_source_metrics` | 视频流量来源质量 | 第二阶段 |
| `spark_platform_metric_summaries` | 平台播放、涨粉、转粉效率 | 已接入，需统一口径 |
| `spark_video_follower_contributions` | 视频涨粉贡献排行 | 已接入，需统一口径 |
| `audience_profile_snapshots` | 粉丝画像 | 第一阶段可来自档案快照，不能混入指标判断 |
| `topic_trend_snapshots` | 热点话题 | 第一阶段可来自外部参考快照，不能混入账号健康度 |

### 4.3 Insight 层

Insight 不是随便写的文案，而是“规则判断 + 证据指标 + 动作建议”。

一个 insight 至少包含：

- `title`：结论标题。
- `summary`：给用户看的解释。
- `evidenceMetrics`：支持这个判断的指标证据。
- `recommendedActions`：下一步动作。
- `pageTargets`：应该展示在哪些页面或 Tab。

第一阶段 insight 的文案模板可以先固定，但触发条件和证据指标必须来自统一指标表。

错误方式：

```text
为了让页面好看，直接写一句“B站教程转粉强”
```

正确方式：

```text
读取 spark_platform_metric_summaries
发现 B站 conversion_rate 最高
生成 insight：“B站教程转粉效率最高”
证据：B站转粉率、涨粉数、播放数
动作：下周增加 B站教程占比
```

## 5. 核心指标统一公式

### 5.1 基础公式

| 指标 | 公式 | 说明 |
|---|---|---|
| 互动总数 | `likes + comments + shares + saves` | B站后续可加入弹幕 |
| 互动率 | `互动总数 / views` | 分母为 0 时返回 0 |
| 播放转粉率 | `new_followers / views` | 内容把流量变成粉丝的能力 |
| 主页访问转粉率 | `new_followers / profile_visits` | 主页承接能力 |
| 评论率 | `comments / views` | 高价值互动 |
| 收藏率 | `saves / views` | 复访和教程价值 |
| 分享率 | `shares / views` | 外扩传播 |
| 净增粉丝 | `new_followers - lost_followers` | 没有掉粉事件时暂用 0 |

### 5.2 粘性指数

文档口径：

```text
stickinessScore =
  commentRateScore * 0.30
  + saveRateScore * 0.35
  + shareRateScore * 0.20
  + repeatInteractionScore * 0.15
```

MVP 第一阶段没有真实用户级复访事件，因此：

```text
repeatInteractionScore 暂时由收藏率和评论率共同近似
```

后续接入用户级互动或连续互动事件后，再替换为真实复访指标。

### 5.3 账号增长健康度

正式口径：

```text
growthHealthScore =
  followerTrendScore * 0.30
  + conversionScore * 0.25
  + stickinessScore * 0.25
  + contentEfficiencyScore * 0.20
```

四个子分数含义：

| 子分数 | 来源 | 说明 |
|---|---|---|
| `followerTrendScore` | `creator_metric_snapshots` | 新增粉丝、掉粉、净增趋势 |
| `conversionScore` | `video_metric_snapshots` / 平台汇总 | 播放转粉率、主页访问转粉率 |
| `stickinessScore` | 视频互动指标 | 评论、收藏、分享、复访近似 |
| `contentEfficiencyScore` | 视频数、播放、涨粉 | 单位内容带来的增长效率 |

第一阶段可以先用简化归一化方式，但必须保留四个子分数，不能只写一个最终分。

建议新增或扩展字段：

```text
creator_metric_snapshots
  follower_trend_score
  conversion_score
  stickiness_score
  content_efficiency_score
  growth_health_score
```

如果暂时不改表，也必须在后端计算 ViewModel 时保留这四个拆解值。

## 6. 表责任边界

### 6.1 允许一次性 Mock / 注册生成的数据

MVP 阶段只允许以下档案类数据一次性 Mock / 注册生成：

- 达人基础信息。
- 登录账号。
- `user_id` 与 `creator_id` 映射。
- 平台绑定状态。
- 视频基础信息。
- 初始粉丝画像。
- 初始热点话题。
- 部分权限配置。

这些数据必须明确标记为档案或初始快照，不能伪装成实时事件结果。

### 6.2 禁止静态 Mock 直接写入的指标数据

以下指标数据禁止再由静态 Mock 直接写入业务结果表，必须来自事件或聚合：

- 视频播放数。
- 点赞数。
- 评论数。
- 分享数。
- 收藏数。
- 主页访问数。
- 新增粉丝数。
- 视频转粉率。
- 互动率。
- 平台转粉贡献。
- 视频涨粉贡献。
- 账号 7 天趋势。
- 粘性指数。
- 账号健康度。
- 内容效率。
- Insight 证据指标。

允许保留“开发兜底数据”的唯一条件：

```text
只用于本地开发兜底；
必须通过 dataSource / generatedBy 标记来源；
不得作为正式链路验收结果。
```

### 6.3 前端禁止承担的职责

前端可以做：

- 格式化数字。
- 排序展示 Top 3 / Top 5。
- 控制图表动画。
- 组合展示 UI 卡片。

前端不应该做：

- 自己计算账号健康度。
- 自己生成 insight 文案。
- 自己拼不同来源的数据口径。
- 自己决定哪个平台“值得投入”。

这些判断应该来自后端 ViewModel 或 insight 规则。

## 7. 第一阶段实施范围

第一阶段目标不是一次做完整真实平台系统，而是把当前 MVP 改成：

```text
达人基础档案一次性 Mock / 注册生成
后续所有核心指标由 Mock 事件 → Flume → Kafka → Spark → MySQL 聚合生成
```

增长总览、粉丝分析、视频分析的核心数字必须来自统一事件聚合。

### 7.1 输入

继续使用虚拟机 Mock 生成器生成 `video_stats` 标准事件。

同时保留一次性档案生成脚本，用来创建：

- 达人。
- 登录账号。
- 平台绑定。
- 视频基础信息。
- 初始粉丝画像。
- 初始热点话题。

档案生成脚本不得再直接生成视频指标、账号趋势、健康度和 insight 证据指标。

事件写入路径：

```text
Mock Generator
  → Flume spooldir
  → Kafka video_stats_topic
  → Spark Streaming
```

### 7.2 Spark 输出

第一阶段 Spark 应输出或更新：

| 表 | 写入方式 |
|---|---|
| `video_metric_snapshots` | 按 `creator_id + content_id` upsert 最新快照 |
| `spark_platform_metric_summaries` | 按批次追加或保留最新 run |
| `spark_video_follower_contributions` | 按批次生成 Top 10 |
| `creator_metric_snapshots` | 按天 upsert 账号聚合指标 |

第一阶段 Spark 至少要覆盖以下指标：

- 每条视频最新播放、点赞、评论、分享、收藏、主页访问、新增粉丝。
- 每条视频互动率、评论率、收藏率、分享率、播放转粉率。
- 每个平台总播放、总涨粉、平台转粉率。
- 视频涨粉贡献 Top 10。
- 账号当日总播放、总互动、新增粉丝、趋势快照。
- 粘性指数。
- 账号健康度及其四个子分数。

### 7.3 后端输出

Flask API 继续输出当前 ViewModel 结构，但数据来源要统一：

```text
ViewModel = MySQL 指标表 + Insight 规则结果
```

不直接读取旧 mock JSON。

API 可以继续保持当前前端需要的字段结构，但字段值必须优先来自统一指标表。

### 7.4 页面影响

前端页面结构暂时不改。

只要求：

- 页面上的核心数字来自 API。
- API 的核心数字来自统一指标表。
- 指标表的核心数字来自事件聚合。
- 前端 UI 不需要因为后端数据链路重构而重写。

## 8. 第二阶段实施范围

第二阶段补齐数据丰富度：

- 增加 `traffic_source_stats` 事件。
- 生成 `video_traffic_source_metrics`。
- 增加 `creator_stats` 事件。
- 让掉粉、总粉丝、账号增长率更真实。
- Insight 规则全部基于指标表生成。
- 页面展示每个核心判断的证据指标。

## 9. 第三阶段实施范围

第三阶段补齐质量判断：

- 增加评论事件或评论统计事件。
- 增加弹幕事件。
- 增加负面评论比例。
- 增加连续互动 / 复访近似或真实用户级统计。
- 粘性指数从近似公式升级为真实复访口径。

## 10. 验收标准

### 10.1 数据一致性

- 同一视频在不同页面出现时，播放、涨粉、转粉率一致。
- 同一平台在增长总览、内容分布、视频分析中的播放和涨粉口径一致。
- 账号健康度能拆出四个子分数。
- 粘性指数能解释由哪些互动指标组成。

### 10.2 链路一致性

- 新生成一批 `video_stats` 事件后，Kafka 能消费到。
- Spark 能写入 MySQL 指标表。
- Flask API 能读到更新后的指标。
- 前端刷新后能看到核心指标变化。

### 10.3 页面一致性

- 页面不出现“一个模块实时、另一个模块静态但没有说明”的割裂感。
- Insight 的证据指标和页面数字能对得上。
- 健康度、转粉率、粘性、内容效率不再各自为政。

## 11. 非目标

本 SPEC 不要求当前阶段完成：

- 接入真实抖音、B站、小红书等平台 API。
- 实现完整用户级粉丝行为追踪。
- 实现复杂机器学习推荐。
- 重构前端 UI。
- 改变登录注册逻辑。

## 12. 推荐下一步任务

建议按以下顺序实施：

1. 拆分数据生成脚本：档案生成脚本只建档，事件生成脚本只生成标准事件。
2. 扩展标准 `video_stats` 事件字段，确保能覆盖 `video_metric_snapshots`。
3. 修改 Spark Streaming，写入或 upsert `video_metric_snapshots`。
4. 增加 `creator_metric_snapshots` 聚合计算。
5. 按正式公式计算 `stickinessScore` 和 `growthHealthScore`。
6. 修改 Flask API，优先读取事件聚合后的指标。
7. 修改 Insight 规则，让文案来自统一指标证据。
8. 做端到端测试：生成事件 → Kafka → Spark → MySQL → API → 前端。
