# CreatorPulse 数据字段与页面映射 SPEC

> 适用范围：CreatorPulse Phase 1 达人个人增长分析网站  
> 配套文档：`01_业务需求文档.md`、`02_C4架构视图.md`、`03_数据模拟与业务流程详解.md`、`05_UI设计/CreatorPulse网站页面布局SPEC.md`  
> 目标：定义稳定的数据实体、字段口径、派生指标和页面映射，避免 UI 模块各自写死 mock 数据。

---

## 1. 设计目标

当前 UI 已经从“数据大屏”升级为“达人增长诊断工具”。页面里出现了大量结论、诊断、风险、建议和行动清单。如果这些内容直接写死在 HTML 或单个 mock 对象中，后续接入 Flask API、MySQL、Spark Streaming / SparkSQL / MLlib 时会出现三类问题：

1. 同一个指标在不同页面口径不一致。
2. 一个模块需要一份 mock，无法复用真实数据。
3. 推荐结论无法解释，因为缺少证据字段和生成依据。

因此本 SPEC 采用“实体数据 + 聚合指标 + 洞察建议”的三层结构：

```text
标准事件 / 快照数据
  -> 聚合指标 / 派生指标
    -> 页面诊断 / 推荐洞察 / 行动建议
```

页面只消费统一实体和统一指标，不直接依赖某个卡片专用字段。

---

## 2. 数据分层

| 层级 | 数据类型 | 来源 | 用途 |
|---|---|---|---|
| L1 原始标准事件 | `VideoStatsEvent`、`CreatorStatsEvent`、`CommentEvent`、`TopicTrendEvent` | Flume / API / mock generator | Kafka Topic 输入，保留平台原始行为 |
| L2 指标快照 | `VideoMetricSnapshot`、`CreatorMetricSnapshot`、`AudienceProfileSnapshot` | Spark Streaming / SparkSQL | 页面 KPI、趋势、排行、漏斗 |
| L3 分析结果 | `ContentDistributionSummary`、`FollowerAnalysisSummary`、`OpportunityInsight` | SparkSQL / MLlib / rule engine | 页面诊断、推荐、风险提示 |
| L4 页面视图模型 | `DashboardViewModel` 等 | Flask API 聚合 | 前端直接渲染，但不得发明新口径 |

原则：

- L1 允许保留平台差异。
- L2 必须完成跨平台字段归一。
- L3 可以生成文案，但必须带证据字段。
- L4 只做组合和排序，不重新定义指标。

---

## 3. 枚举口径

### 3.1 平台枚举

```ts
type Platform =
  | "DOUYIN"
  | "BILIBILI"
  | "XIAOHONGSHU"
  | "WECHAT_CHANNELS"
  | "YOUTUBE"
  | "WEIBO";
```

### 3.2 内容类型

```ts
type ContentType =
  | "TUTORIAL"      // 教程
  | "REVIEW"        // 测评
  | "SEEDING"       // 种草
  | "VLOG"
  | "LIVE_CLIP"     // 直播切片
  | "NEWS_REACTION" // 热点反应
  | "OTHER";
```

### 3.3 流量来源

```ts
type TrafficSource =
  | "RECOMMENDATION" // 推荐流
  | "SEARCH"
  | "FOLLOWING"
  | "SHARE"
  | "PROFILE"
  | "HASHTAG"
  | "EXTERNAL"
  | "UNKNOWN";
```

### 3.4 视频生命周期

```ts
type VideoLifecycleStage =
  | "BURST"              // 爆发期
  | "STABLE"             // 稳定期
  | "LONG_TAIL"          // 长尾期
  | "SECONDARY_BOOST"    // 二次推荐
  | "DECLINING";         // 衰退期
```

### 3.5 洞察类型

```ts
type InsightType =
  | "DIAGNOSIS"
  | "OPPORTUNITY"
  | "RISK"
  | "ACTION"
  | "REPORT";
```

---

## 4. 核心实体字段

### 4.1 `CreatorProfile`

达人基础信息。用于个人中心、全局筛选、报告归属。

```ts
interface CreatorProfile {
  creatorId: string;
  displayName: string;
  avatarUrl?: string;
  nicheTags: string[];
  primaryPlatforms: Platform[];
  timezone: string;
  createdAt: string;
  updatedAt: string;
}
```

必填字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `creatorId` | string | 达人唯一 ID |
| `displayName` | string | 页面展示名称 |
| `nicheTags` | string[] | 内容领域标签，如通勤妆、平价测评 |
| `primaryPlatforms` | Platform[] | 已绑定或重点运营平台 |
| `timezone` | string | 发布时间分析必须使用达人时区 |

### 4.2 `PlatformAccount`

平台授权和采集状态。用于个人中心 - 平台绑定、采集设置。

```ts
interface PlatformAccount {
  accountId: string;
  creatorId: string;
  platform: Platform;
  platformUserId: string;
  platformDisplayName: string;
  bindingStatus: "BOUND" | "EXPIRED" | "ERROR" | "UNBOUND";
  authExpiresAt?: string;
  lastSyncedAt?: string;
  syncLatencySeconds?: number;
  collectionIntervalSeconds: number;
  dataScopes: string[];
}
```

页面依赖：

- `bindingStatus` 生成“已绑定 / 需刷新授权 / 异常”。
- `syncLatencySeconds` 生成同步延迟。
- `collectionIntervalSeconds` 支撑采集频率配置。
- `dataScopes` 判断是否能采集视频、粉丝、评论、话题等数据。

### 4.3 `VideoMetricSnapshot`

最核心实体。一条视频在某个时间点的统一指标快照。多数页面都应从它聚合，而不是重复造 mock。

```ts
interface VideoMetricSnapshot {
  snapshotId: string;
  videoId: string;
  creatorId: string;
  platform: Platform;

  title: string;
  coverUrl?: string;
  publishTime: string;
  contentType: ContentType;
  topicTags: string[];
  lifecycleStage: VideoLifecycleStage;

  views: number;
  impressions?: number;
  likes: number;
  comments: number;
  shares: number;
  saves: number;
  danmakuCount?: number;

  profileVisits: number;
  newFollowers: number;
  lostFollowers?: number;

  completionRate?: number;
  averageWatchSeconds?: number;
  engagementRate: number;
  conversionRate: number;
  commentRate: number;
  saveRate: number;
  shareRate: number;

  trafficSourceBreakdown: TrafficSourceMetric[];
  audienceBreakdown?: AudienceBreakdown;
  sentimentSummary?: SentimentSummary;

  previousSnapshotId?: string;
  collectedAt: string;
}
```

配套类型：

```ts
interface TrafficSourceMetric {
  source: TrafficSource;
  views: number;
  newFollowers: number;
  conversionRate: number;
  saveRate?: number;
  commentRate?: number;
}

interface AudienceBreakdown {
  gender: Record<string, number>;
  ageGroups: Record<string, number>;
  regions: Record<string, number>;
  activeHours: Record<string, number>;
}

interface SentimentSummary {
  positiveRate: number;
  neutralRate: number;
  negativeRate: number;
  topNegativeKeywords: string[];
}
```

字段要求：

| 字段组 | 必须有 | 原因 |
|---|---|---|
| 身份字段 | `videoId`、`creatorId`、`platform` | 关联平台、达人和视频 |
| 内容字段 | `title`、`publishTime`、`contentType`、`topicTags` | 支撑视频分析、内容分布、机会建议 |
| 基础互动 | `views`、`likes`、`comments`、`shares`、`saves` | 支撑互动质量和粘性判断 |
| 转化字段 | `profileVisits`、`newFollowers`、`conversionRate` | 支撑转粉漏斗和涨粉贡献 |
| 分布字段 | `trafficSourceBreakdown`、`audienceBreakdown` | 支撑流量来源、粉丝画像 |
| 生命周期 | `lifecycleStage`、`previousSnapshotId`、`collectedAt` | 支撑爆发、稳定、长尾、二次推荐判断 |

### 4.4 `CreatorMetricSnapshot`

达人账号维度快照。用于增长总览、粉丝分析、个人日报。

```ts
interface CreatorMetricSnapshot {
  snapshotId: string;
  creatorId: string;
  platform?: Platform;
  totalFollowers: number;
  newFollowers: number;
  lostFollowers: number;
  netFollowers: number;
  totalViews: number;
  totalInteractions: number;
  profileVisits: number;
  followerGrowthRate: number;
  viewToFollowerRate: number;
  interactionToFollowerRate: number;
  stickinessScore: number;
  growthHealthScore: number;
  collectedAt: string;
  windowSeconds: number;
}
```

说明：

- `platform` 为空表示全平台聚合。
- `windowSeconds` 用于区分 5s、30s、1h、1d 快照。
- `growthHealthScore` 是聚合结果，不由前端临时计算。

### 4.5 `AudienceProfileSnapshot`

粉丝画像快照。用于粉丝画像、机会建议、发布时间推荐。

```ts
interface AudienceProfileSnapshot {
  snapshotId: string;
  creatorId: string;
  platform?: Platform;
  gender: Record<string, number>;
  ageGroups: Record<string, number>;
  regions: Record<string, number>;
  activeHours: Record<string, number>;
  interestTags: Record<string, number>;
  highValueSegments: AudienceSegment[];
  collectedAt: string;
}

interface AudienceSegment {
  segmentId: string;
  label: string;
  share: number;
  growthRate: number;
  preferredContentTypes: ContentType[];
  preferredActiveHours: string[];
  primaryActions: string[];
}
```

### 4.6 `TopicTrendSnapshot`

话题机会快照。用于机会建议 - 热点机会。

```ts
interface TopicTrendSnapshot {
  topicId: string;
  topicName: string;
  platforms: Platform[];
  heatScore: number;
  growthRate: number;
  crossPlatformCount: number;
  relatedContentTypes: ContentType[];
  audienceFitScore: number;
  creatorFitScore: number;
  riskLevel: "LOW" | "MEDIUM" | "HIGH";
  collectedAt: string;
}
```

### 4.7 `Insight`

统一承载诊断、机会、风险、行动建议。页面里的“今日结论”“最大瓶颈”“下一步动作”都应来自该结构。

```ts
interface Insight {
  insightId: string;
  creatorId: string;
  type: InsightType;
  scope: "CREATOR" | "PLATFORM" | "VIDEO" | "CONTENT_TYPE" | "AUDIENCE" | "TOPIC";
  targetId?: string;
  title: string;
  summary: string;
  priority: "LOW" | "MEDIUM" | "HIGH";
  evidenceMetrics: EvidenceMetric[];
  recommendedActions: RecommendedAction[];
  generatedBy: "RULE_ENGINE" | "MLLIB" | "MANUAL_MOCK";
  generatedAt: string;
}

interface EvidenceMetric {
  label: string;
  value: number | string;
  unit?: string;
  baseline?: number | string;
  direction?: "UP" | "DOWN" | "FLAT";
}

interface RecommendedAction {
  actionId: string;
  title: string;
  description: string;
  expectedImpact?: string;
  relatedPage?: string;
}
```

---

## 5. 派生指标公式

| 指标 | 公式 | 说明 |
|---|---|---|
| 净增粉丝 | `newFollowers - lostFollowers` | 没有掉粉数据时，`lostFollowers = 0` |
| 播放转粉率 | `newFollowers / views` | 分母为 0 时返回 0 |
| 互动率 | `(likes + comments + shares + saves + danmakuCount) / views` | B站弹幕可参与互动 |
| 评论率 | `comments / views` | 互动质量指标 |
| 收藏率 | `saves / views` | 粘性与复访倾向 |
| 分享率 | `shares / views` | 外扩传播 |
| 主页访问转粉率 | `newFollowers / profileVisits` | 判断主页承接能力 |
| 粉丝增长率 | `netFollowers / previousTotalFollowers` | 用于粉丝趋势 |
| 内容效率 | `newFollowers / contentCount` | 用于内容分布 |
| 粘性指数 | `commentRate * 30 + saveRate * 35 + shareRate * 20 + repeatInteractionRate * 15` | 归一到 0-100 |
| 账号增长健康度 | `followerTrendScore * 0.3 + conversionScore * 0.25 + stickinessScore * 0.25 + contentEfficiencyScore * 0.2` | UI 主圆环指标 |

所有百分比内部建议保留 4 位小数，前端展示时再格式化为百分数。

---

## 6. 页面到数据映射

### 6.1 增长总览

| Tab | 数据来源 | 核心字段 / 指标 |
|---|---|---|
| 实时概览 | `CreatorMetricSnapshot`、`Insight` | `growthHealthScore`、`newFollowers`、`viewToFollowerRate`、`stickinessScore` |
| 粉丝转化 | `VideoMetricSnapshot`、`CreatorMetricSnapshot`、`Insight` | `views`、`profileVisits`、`newFollowers`、`conversionRate` |
| 粉丝粘性 | `VideoMetricSnapshot`、`Insight` | `comments`、`saves`、`shares`、`danmakuCount`、`stickinessScore` |
| 视频分布 | `VideoMetricSnapshot` | `platform`、`contentType`、`publishTime`、`trafficSourceBreakdown` |

### 6.2 粉丝分析

| Tab | 数据来源 | 核心字段 / 指标 |
|---|---|---|
| 增长趋势 | `CreatorMetricSnapshot` | `totalFollowers`、`newFollowers`、`lostFollowers`、`netFollowers`、`followerGrowthRate` |
| 转化来源 | `VideoMetricSnapshot` | `platform`、`videoId`、`trafficSourceBreakdown`、`newFollowers`、`conversionRate` |
| 粘性行为 | `VideoMetricSnapshot`、`AudienceProfileSnapshot` | `saveRate`、`commentRate`、`shareRate`、`danmakuCount`、`highValueSegments` |
| 粉丝画像 | `AudienceProfileSnapshot` | `gender`、`ageGroups`、`regions`、`activeHours`、`interestTags` |

### 6.3 视频分析

| Tab | 数据来源 | 核心字段 / 指标 |
|---|---|---|
| 最新视频 | `VideoMetricSnapshot` | `publishTime`、`views`、`newFollowers`、`conversionRate`、`lifecycleStage` |
| 涨粉贡献 | `VideoMetricSnapshot`、`Insight` | `newFollowers`、`views`、`conversionRate`、`contentType` |
| 互动质量 | `VideoMetricSnapshot`、`CommentEvent` 聚合 | `comments`、`saves`、`shares`、`danmakuCount`、`sentimentSummary` |
| 生命周期 | `VideoMetricSnapshot` | `lifecycleStage`、`previousSnapshotId`、`collectedAt`、增长斜率 |

### 6.4 内容分布

| Tab | 数据来源 | 核心字段 / 指标 |
|---|---|---|
| 平台分布 | `VideoMetricSnapshot` | `platform`、`views`、`newFollowers`、`conversionRate` |
| 内容类型 | `VideoMetricSnapshot` | `contentType`、`views`、`comments`、`saves`、`newFollowers` |
| 发布时间 | `VideoMetricSnapshot`、`AudienceProfileSnapshot` | `publishTime`、`activeHours`、`conversionRate`、`commentRate` |
| 流量来源 | `TrafficSourceMetric` | `source`、`views`、`newFollowers`、`conversionRate`、`saveRate` |

### 6.5 机会建议

| Tab | 数据来源 | 核心字段 / 指标 |
|---|---|---|
| 热点机会 | `TopicTrendSnapshot`、`AudienceProfileSnapshot` | `heatScore`、`growthRate`、`creatorFitScore`、`audienceFitScore` |
| 创作建议 | `Insight`、`TopicTrendSnapshot`、`VideoMetricSnapshot` | `recommendedActions`、`evidenceMetrics`、`contentType`、`publishTime` |
| 参考洞察 | `Insight` | 高转粉结构、标题关键词、封面特征、CTA 特征 |

### 6.6 个人中心

| Tab | 数据来源 | 核心字段 / 指标 |
|---|---|---|
| 数据报告 | `CreatorMetricSnapshot`、`Insight` | 日报、周报、月报摘要 |
| 平台绑定 | `PlatformAccount` | `bindingStatus`、`authExpiresAt`、`lastSyncedAt`、`syncLatencySeconds` |
| 采集设置 | `PlatformAccount` | `collectionIntervalSeconds`、`dataScopes` |
| 通知偏好 | `Insight`、用户配置 | 规则类型、阈值、开启状态 |

---

## 7. Mock 数据规则

Mock 数据必须模拟真实数据生成链路，不允许只为某个 UI 卡片写死字段。

### 7.1 最小 mock 数据集

| 数据集 | 最小数量 | 用途 |
|---|---:|---|
| 达人 | 1 | 当前 Phase 1 只做个人视角 |
| 平台账号 | 6 | 覆盖抖音、B站、小红书、视频号、YouTube、微博 |
| 视频快照 | 每平台至少 20 条 | 支撑排行、分布、生命周期 |
| 粉丝快照 | 每平台 7 天，每天至少 24 个点 | 支撑趋势和异常 |
| 画像快照 | 每平台 1 条 + 全平台聚合 1 条 | 支撑粉丝画像和机会建议 |
| 话题快照 | 至少 20 个话题 | 支撑热点机会 |
| 洞察建议 | 每页面每 Tab 至少 3 条 | 支撑诊断条和行动清单 |

### 7.2 数值一致性约束

Mock 生成时必须满足：

- `newFollowers <= profileVisits <= views`
- `likes + comments + shares + saves <= views * 2`，避免互动总数荒谬。
- `conversionRate = newFollowers / views`，不得手写不一致值。
- 平台聚合值必须等于视频明细求和或在可解释误差内。
- 内容类型占比、平台占比、流量来源占比总和应接近 100%。
- 同一视频在不同页面出现时，播放、涨粉、转粉率必须一致。

### 7.3 建议文案生成规则

每条 `Insight` 必须有：

1. `title`：短结论。
2. `summary`：为什么重要。
3. `evidenceMetrics`：至少 2 个证据指标。
4. `recommendedActions`：至少 1 个可执行动作。

示例：

```json
{
  "type": "OPPORTUNITY",
  "scope": "CONTENT_TYPE",
  "targetId": "TUTORIAL",
  "title": "教程类内容值得加码",
  "summary": "教程类播放占比 31%，但贡献 46% 新粉。",
  "evidenceMetrics": [
    { "label": "播放占比", "value": 31, "unit": "%" },
    { "label": "涨粉贡献", "value": 46, "unit": "%" }
  ],
  "recommendedActions": [
    {
      "title": "提高教程发布占比",
      "description": "下周将教程类内容提高到 40%，优先发布 B站完整版。"
    }
  ]
}
```

---

## 8. API 视图模型建议

后端 API 可以先返回页面视图模型，但视图模型内必须保留实体来源，避免 UI 与数据层断裂。

示例：

```ts
interface PageSection<T> {
  title: string;
  summary?: string;
  data: T;
  insights: Insight[];
}

interface GrowthDashboardViewModel {
  creator: CreatorProfile;
  currentSnapshot: CreatorMetricSnapshot;
  platformSnapshots: CreatorMetricSnapshot[];
  topVideos: VideoMetricSnapshot[];
  sections: {
    overview: PageSection<CreatorMetricSnapshot>;
    conversion: PageSection<VideoMetricSnapshot[]>;
    stickiness: PageSection<VideoMetricSnapshot[]>;
    distribution: PageSection<VideoMetricSnapshot[]>;
  };
}
```

推荐 REST 路径：

| API | 用途 |
|---|---|
| `GET /api/creators/:creatorId/dashboard/growth` | 增长总览 |
| `GET /api/creators/:creatorId/fans` | 粉丝分析 |
| `GET /api/creators/:creatorId/videos` | 视频分析 |
| `GET /api/creators/:creatorId/distribution` | 内容分布 |
| `GET /api/creators/:creatorId/opportunities` | 机会建议 |
| `GET /api/creators/:creatorId/profile` | 个人中心 |

列表型接口后续必须支持：

- `platform`
- `contentType`
- `dateFrom`
- `dateTo`
- `page`
- `pageSize`
- `sortBy`
- `sortOrder`

---

## 9. 信息密度规范

当前 UI 适合高保真原型，但真实产品需要控制每屏负担。所有页面遵循：

```text
结论先行 -> 证据支撑 -> 细节展开 -> 行动建议
```

### 9.1 每个 Tab 的信息上限

| 区域 | 建议上限 |
|---|---:|
| 顶部诊断结论 | 3 条 |
| 核心 KPI | 3-6 个 |
| 表格默认行数 | 3-5 行 |
| 行动建议 | 3 条 |
| 图表/图形模块 | 1-2 个 |

### 9.2 展示优先级

1. 用户现在最该知道什么。
2. 为什么这个判断成立。
3. 哪些数据可以进一步查看。
4. 下一步应该做什么。

### 9.3 降低负担的交互策略

- 诊断条只放结论，不放长解释。
- 表格默认 Top 3，更多内容用“展开”或进入详情页。
- 行动建议不要超过 3 条，超过则按优先级合并。
- 颜色只用于状态：绿色代表机会，黄色代表提醒，红色代表风险。
- 同一个 Tab 内不要同时出现超过 2 个主要视觉焦点。

---

## 10. 实施检查清单

后续实现 mock/API/数据库时，用以下清单验收：

1. 是否所有页面指标都能从核心实体推导，而不是卡片硬编码。
2. 同一视频在不同页面的播放、涨粉、转粉率是否一致。
3. 每条洞察是否带有证据指标和行动建议。
4. 页面默认展示是否控制在 Top 3 / Top 5。
5. 是否可以从 `VideoMetricSnapshot` 聚合出视频分析、内容分布、粉丝转化。
6. 是否可以从 `CreatorMetricSnapshot` 聚合出增长总览和粉丝趋势。
7. 是否可以从 `AudienceProfileSnapshot` 支撑粉丝画像和机会建议。
8. 是否保留平台原始字段到标准字段的映射说明，便于追溯。

---

## 11. 当前结论

CreatorPulse 的数据模型应围绕“视频快照、达人快照、画像快照、话题快照、洞察建议”构建。页面越复杂，越不能按 UI 模块写 mock。正确做法是先生成统一实体，再由页面聚合和筛选。

信息密度可以高，但必须分层。第一屏展示判断，第二层展示证据，第三层才展示细节，最后给出行动。这样既能保留当前 UI 的专业感，也不会让达人被数据压垮。
