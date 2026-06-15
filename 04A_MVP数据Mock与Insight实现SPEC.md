# CreatorPulse MVP 数据 Mock 与 Insight 实现 SPEC

> 适用阶段：CreatorPulse MVP / Phase 1 静态数据驱动版本  
> 配套文档：`04_数据字段与页面映射SPEC.md`、`03_数据模拟与业务流程详解.md`、`05_UI设计/最终版`  
> 目标：在暂未接入抖音、B站、小红书真实 API 的情况下，用一套统一 mock 数据驱动所有页面，并用第一阶段规则引擎生成可解释的 Insight。

---

## 1. MVP 范围

本阶段不接真实平台数据，不做复杂 AI 分析，不做完整数据仓库。

本阶段要实现：

1. 生成一套统一 mock 数据，而不是每个页面单独写死数据。
2. 页面里的核心数字、排行、诊断、行动建议都能从 mock 数据推导出来。
3. Insight 先用“规则 + 文案模板”生成。
4. 保留未来接入真实数据、数据库和 AI 文案润色的扩展空间。

本阶段暂不实现：

1. 真实平台授权与数据拉取。
2. Spark Streaming / SparkSQL / MLlib 真实计算链路。
3. AI 自动发现复杂模式。
4. 多达人、多租户、权限体系。

---

## 2. 数据契约与建表关系

`04_数据字段与页面映射SPEC.md` 是数据契约。它会指导后续建表，但不是简单地“一种数据对象 = 一张表”。

正确关系是：

```text
数据契约定义系统需要什么数据
  -> 数据库表根据实体、明细、查询需求拆分
    -> API 根据页面需要组合返回
      -> 前端只消费标准字段和 Insight
```

例如：

`VideoMetricSnapshot` 是一条视频在某个时间点的指标快照。建表时可以有主表：

```text
video_metric_snapshots
```

但它内部的 `trafficSourceBreakdown` 是一个数组，一条视频可能同时有推荐、搜索、关注页、分享等来源，所以更适合拆成子表：

```text
video_traffic_source_metrics
```

因此：

```text
数据对象数量 != 数据表数量
```

MVP 阶段可以先用 JSON 文件或 JS mock 模块表达数据契约，暂时不强制建数据库。

---

## 3. MVP 推荐数据表雏形

如果后续开始落库，MVP 第一版建议从这些表开始：

| 表名 | 用途 |
|---|---|
| `creators` | 达人基础信息 |
| `platform_accounts` | 抖音、B站、小红书账号绑定和采集状态 |
| `videos` | 视频基础信息 |
| `video_metric_snapshots` | 单条视频最新指标快照 |
| `video_traffic_source_metrics` | 单条视频的流量来源拆分 |
| `creator_metric_snapshots` | 账号整体 7 天趋势 |
| `audience_profile_snapshots` | 粉丝画像快照 |
| `topic_trend_snapshots` | 热点话题数据 |
| `insights` | 诊断、机会、风险、行动建议 |
| `insight_evidence_metrics` | Insight 的证据指标 |
| `recommended_actions` | Insight 对应的行动建议 |

MVP 如果先不建库，可以用同名 JSON 数组表示这些数据。

---

## 4. MVP Mock 数据规模

第一版 mock 数据固定生成：

| 数据类型 | 数量 |
|---|---:|
| 达人 | 1 个 |
| 平台 | 3 个：抖音、B站、小红书 |
| 视频 | 每个平台 8-10 条 |
| 视频快照 | 每条视频 1 条最新快照 |
| 账号趋势 | 整体 7 天趋势 |
| 粉丝画像 | 1 份全平台画像 |
| 热点话题 | 10 条 |
| Insight | 20-30 条 |

平台枚举：

```ts
type Platform = "DOUYIN" | "BILIBILI" | "XIAOHONGSHU";
```

内容类型枚举：

```ts
type ContentType = "TUTORIAL" | "REVIEW" | "SEEDING" | "VLOG" | "LIVE_CLIP";
```

---

## 5. Mock 生成顺序

不要按页面生成 mock，例如不要写：

```text
growthDashboardMock
fansAnalysisMock
videoAnalysisMock
```

应该按真实数据链路生成：

```text
1. creator
2. platformAccounts
3. videos
4. videoMetricSnapshots
5. videoTrafficSourceMetrics
6. creatorMetricSnapshots
7. audienceProfileSnapshot
8. topicTrendSnapshots
9. insights
```

原因：

1. 同一条视频在不同页面出现时，播放、新粉、转粉率必须一致。
2. 页面上的平台排行、内容类型分布、粉丝转化都应该来自同一批视频数据聚合。
3. Insight 必须能追溯到具体证据字段。

---

## 6. MVP 核心 Mock 对象

### 6.1 Creator

```ts
interface Creator {
  creatorId: string;
  displayName: string;
  avatarUrl?: string;
  nicheTags: string[];
  timezone: string;
}
```

示例：

```json
{
  "creatorId": "creator_001",
  "displayName": "通勤美妆研究所",
  "nicheTags": ["通勤妆", "平价测评", "新手教程"],
  "timezone": "Asia/Shanghai"
}
```

### 6.2 PlatformAccount

```ts
interface PlatformAccount {
  accountId: string;
  creatorId: string;
  platform: Platform;
  platformDisplayName: string;
  bindingStatus: "BOUND" | "EXPIRED" | "ERROR";
  syncLatencySeconds: number;
  collectionIntervalSeconds: number;
  dataScopes: string[];
}
```

### 6.3 Video

```ts
interface Video {
  videoId: string;
  creatorId: string;
  platform: Platform;
  title: string;
  contentType: ContentType;
  topicTags: string[];
  publishTime: string;
  lifecycleStage: "BURST" | "STABLE" | "LONG_TAIL" | "SECONDARY_BOOST" | "DECLINING";
}
```

### 6.4 VideoMetricSnapshot

```ts
interface VideoMetricSnapshot {
  snapshotId: string;
  videoId: string;
  creatorId: string;
  platform: Platform;
  views: number;
  likes: number;
  comments: number;
  shares: number;
  saves: number;
  profileVisits: number;
  newFollowers: number;
  completionRate: number;
  averageWatchSeconds: number;
  engagementRate: number;
  conversionRate: number;
  commentRate: number;
  saveRate: number;
  shareRate: number;
  collectedAt: string;
}
```

### 6.5 TrafficSourceMetric

```ts
interface TrafficSourceMetric {
  videoId: string;
  source: "RECOMMENDATION" | "SEARCH" | "FOLLOWING" | "SHARE" | "PROFILE";
  views: number;
  newFollowers: number;
  conversionRate: number;
  saveRate: number;
  commentRate: number;
}
```

### 6.6 CreatorMetricSnapshot

```ts
interface CreatorMetricSnapshot {
  snapshotId: string;
  creatorId: string;
  date: string;
  totalFollowers: number;
  newFollowers: number;
  lostFollowers: number;
  netFollowers: number;
  totalViews: number;
  totalInteractions: number;
  profileVisits: number;
  followerGrowthRate: number;
  viewToFollowerRate: number;
  stickinessScore: number;
  growthHealthScore: number;
}
```

### 6.7 AudienceProfileSnapshot

```ts
interface AudienceProfileSnapshot {
  snapshotId: string;
  creatorId: string;
  gender: Record<string, number>;
  ageGroups: Record<string, number>;
  regions: Record<string, number>;
  activeHours: Record<string, number>;
  interestTags: Record<string, number>;
}
```

### 6.8 TopicTrendSnapshot

```ts
interface TopicTrendSnapshot {
  topicId: string;
  topicName: string;
  platforms: Platform[];
  heatScore: number;
  growthRate: number;
  audienceFitScore: number;
  creatorFitScore: number;
  riskLevel: "LOW" | "MEDIUM" | "HIGH";
}
```

---

## 7. Mock 数值一致性规则

生成 mock 时必须满足：

```text
newFollowers <= profileVisits <= views
likes + comments + shares + saves <= views * 2
conversionRate = newFollowers / views
commentRate = comments / views
saveRate = saves / views
shareRate = shares / views
engagementRate = (likes + comments + shares + saves) / views
netFollowers = newFollowers - lostFollowers
```

聚合规则：

```text
平台总播放 = 该平台所有视频 views 之和
平台新增粉丝 = 该平台所有视频 newFollowers 之和
内容类型播放 = 该内容类型所有视频 views 之和
内容类型新增粉丝 = 该内容类型所有视频 newFollowers 之和
账号总播放 = 所有平台视频 views 之和
账号新增粉丝 = 所有平台视频 newFollowers 之和
```

这样可以避免页面之间数字互相打架。

---

## 8. Insight 是什么

Insight 是系统根据数据生成的一条“分析结论 + 证据 + 建议”。

它不是原始数据，也不是普通页面文案。

原始数据：

```text
B站教程视频播放 92.4 万
新增粉丝 8620
转粉率 1.14%
收藏率 12.8%
```

生成 Insight：

```text
结论：B站教程内容值得复刻
证据：转粉率 1.14%，新增粉丝 8620，收藏率 12.8%
建议：下周继续做通勤妆 3 集系列
```

页面里的这些内容都应该优先来自 Insight：

```text
今日结论
最大瓶颈
最佳来源
低粘性风险
下一步动作
授权风险
热点机会
创作建议
```

---

## 9. MVP Insight 数据结构

```ts
interface Insight {
  insightId: string;
  creatorId: string;
  type: "DIAGNOSIS" | "OPPORTUNITY" | "RISK" | "ACTION" | "REPORT";
  scope: "CREATOR" | "PLATFORM" | "VIDEO" | "CONTENT_TYPE" | "AUDIENCE" | "TOPIC" | "ACCOUNT";
  targetId?: string;
  title: string;
  summary: string;
  priority: "LOW" | "MEDIUM" | "HIGH";
  evidenceMetrics: EvidenceMetric[];
  recommendedActions: RecommendedAction[];
  generatedBy: "RULE_ENGINE";
  generatedAt: string;
  pageTargets: string[];
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

`pageTargets` 用来声明这条 Insight 可以出现在哪些页面或 Tab，例如：

```json
["growth.conversion", "fans.source", "video.contribution"]
```

---

## 10. Insight 三阶段路线

### 阶段一：规则 + 文案模板

MVP 只实现这一阶段。

特点：

1. 规则提前定义。
2. 文案模板提前定义。
3. 数字和对象来自 mock 数据。
4. 每条 Insight 必须有证据和行动建议。

示例：

```text
如果某内容类型的转粉率高于账号平均值 30%
并且新增粉丝贡献占比超过 35%
则生成“该内容类型值得加码”的机会 Insight
```

### 阶段二：规则生成结构，AI 润色文案

后续实现。

规则仍然决定：

```text
结论类型
证据指标
建议动作
优先级
```

AI 只负责把 `title`、`summary`、`description` 写得更自然。

AI 不允许凭空新增没有证据的数据。

### 阶段三：AI / ML 辅助发现复杂模式

后续实现。

可以让模型或算法发现：

```text
什么标题结构更容易转粉
什么发布时间对特定人群更有效
什么内容组合容易形成长尾
哪些粉丝人群正在流失
```

但最终输出仍必须落到统一 Insight 结构，并保留 `evidenceMetrics`。

---

## 11. MVP 第一阶段 Insight 规则

### 11.1 转化机会规则

触发条件：

```text
video.conversionRate >= accountAverageConversionRate * 1.3
并且 video.newFollowers >= 1000
```

输出：

```text
type = OPPORTUNITY
scope = VIDEO
title = "{videoTitle} 值得复刻"
```

证据：

```text
播放量
新增粉丝
转粉率
```

建议：

```text
复刻该视频的选题、人群表达、开头结构和 CTA。
```

### 11.2 高播放低转粉风险规则

触发条件：

```text
video.views >= platformAverageViews * 1.5
并且 video.conversionRate <= accountAverageConversionRate * 0.6
```

输出：

```text
type = RISK
scope = VIDEO
title = "{videoTitle} 播放高但转粉偏低"
```

建议：

```text
前 8 秒明确适合谁关注，减少泛流量空转。
```

### 11.3 教程内容加码规则

触发条件：

```text
contentType = TUTORIAL
并且 tutorialNewFollowersShare >= 35%
并且 tutorialSaveRate >= accountAverageSaveRate
```

输出：

```text
type = OPPORTUNITY
scope = CONTENT_TYPE
title = "教程类内容值得加码"
```

建议：

```text
下周提高教程发布占比，优先做系列化。
```

### 11.4 测评内容评论机会规则

触发条件：

```text
contentType = REVIEW
并且 reviewCommentRate >= accountAverageCommentRate * 1.2
```

输出：

```text
type = OPPORTUNITY
scope = CONTENT_TYPE
title = "测评内容适合承接评论选题"
```

建议：

```text
把评论区高频问题做成下一条视频或 Q&A 续集。
```

### 11.5 低粘性风险规则

触发条件：

```text
video.likeRate 高
并且 video.saveRate 低
并且 video.conversionRate 低
```

输出：

```text
type = RISK
scope = VIDEO
title = "{videoTitle} 互动偏浅，复访风险高"
```

建议：

```text
增加收藏理由、步骤清单或系列入口。
```

### 11.6 平台投入调整规则

触发条件：

```text
platformPublishShare 高
并且 platformNewFollowersShare 低
```

输出：

```text
type = DIAGNOSIS
scope = PLATFORM
title = "{platform} 投入和涨粉贡献不匹配"
```

建议：

```text
减少该平台低转粉内容，把它改成高转粉内容的切片导流。
```

### 11.7 发布时间机会规则

触发条件：

```text
某小时段 conversionRate >= averageConversionRate * 1.2
```

输出：

```text
type = OPPORTUNITY
scope = CREATOR
title = "{hour} 是更适合发布主内容的窗口"
```

建议：

```text
把教程和测评主内容安排在该时间段。
```

### 11.8 热点机会规则

触发条件：

```text
topic.creatorFitScore >= 85
并且 topic.riskLevel != HIGH
```

输出：

```text
type = OPPORTUNITY
scope = TOPIC
title = "{topicName} 适合作为下一条内容选题"
```

建议：

```text
结合当前高转粉内容类型生成脚本结构。
```

### 11.9 授权风险规则

触发条件：

```text
platformAccount.bindingStatus = EXPIRED
或 syncLatencySeconds > 60
```

输出：

```text
type = RISK
scope = ACCOUNT
title = "{platform} 授权或同步状态需要处理"
```

建议：

```text
刷新授权或检查采集任务，避免数据断流。
```

---

## 12. Insight 文案模板

文案模板可以提前写好，但最终数字必须来自数据。

### 12.1 机会模板

```text
{targetName} 值得加码，因为 {metricA} 达到 {valueA}{unitA}，高于账号平均水平。
```

### 12.2 风险模板

```text
{targetName} 存在 {riskName}，当前 {metricA} 为 {valueA}{unitA}，低于目标 {baseline}{unitA}。
```

### 12.3 行动模板

```text
下周优先执行：{actionDescription}，预期改善 {expectedMetric}。
```

### 12.4 视频复刻模板

```text
复刻 {videoTitle} 的结构：结果预览、步骤拆解、收藏引导和系列预告。
```

---

## 13. Insight 生成流程

```text
输入 mock 数据
  -> 计算全局均值和平台均值
    -> 遍历视频、平台、内容类型、话题、账号状态
      -> 命中规则
        -> 填充文案模板
          -> 生成 Insight
            -> 按 priority 排序
              -> 分发到对应页面 Tab
```

伪代码：

```ts
function generateInsights(data: MockData): Insight[] {
  const metrics = calculateBaselines(data);
  const insights: Insight[] = [];

  for (const video of data.videoMetricSnapshots) {
    if (isHighConversionVideo(video, metrics)) {
      insights.push(buildHighConversionVideoInsight(video, metrics));
    }

    if (isHighViewLowConversionVideo(video, metrics)) {
      insights.push(buildLowConversionRiskInsight(video, metrics));
    }
  }

  insights.push(...buildContentTypeInsights(data, metrics));
  insights.push(...buildPlatformInsights(data, metrics));
  insights.push(...buildTopicInsights(data, metrics));
  insights.push(...buildAccountHealthInsights(data));

  return rankInsights(insights).slice(0, 30);
}
```

---

## 14. 页面消费方式

页面不要直接关心规则怎么判断。

页面只消费：

```text
标准指标数据
Insight[]
```

例如增长总览的粉丝转化 Tab：

```ts
interface GrowthConversionViewModel {
  funnel: {
    views: number;
    interactions: number;
    profileVisits: number;
    newFollowers: number;
  };
  topSources: VideoMetricSnapshot[];
  insights: Insight[];
}
```

页面渲染逻辑：

```text
诊断条 = insights 里 priority 最高的 3 条
核心证据区 = funnel / table / bar chart
行动建议 = insights.recommendedActions 里的 Top 3
```

---

## 15. MVP 验收标准

实现 mock 和 Insight 后，用以下清单验收：

1. 是否只有一套统一 mock 数据，而不是每个页面一套。
2. 同一条视频在不同页面的播放、新粉、转粉率是否一致。
3. 所有百分比是否由公式计算，而不是手写。
4. 每条 Insight 是否至少包含 2 个证据指标。
5. 每条 Insight 是否至少包含 1 个行动建议。
6. 页面诊断条是否来自 Insight，而不是写死文案。
7. 非首页 Tab 默认是否只展示“诊断 + 证据 + 行动”。
8. 是否可以把 mock 数据替换成 API 返回数据，而不重写页面结构。

---

## 16. 当前结论

MVP 不需要一开始就做复杂数据平台。正确路径是：

```text
统一 mock 数据
  -> 统一公式计算
    -> 第一阶段规则生成 Insight
      -> 页面消费 ViewModel
        -> 后续替换为真实 API / 数据库
```

Insight 第一阶段不是 AI，而是可解释规则。规则和模板提前写好，数字、对象和证据来自数据。这样既能保证页面专业感，也能避免未来接真实数据时推倒重来。
