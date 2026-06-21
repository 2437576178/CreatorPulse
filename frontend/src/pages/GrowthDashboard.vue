<script setup>
import { computed, nextTick, onMounted, ref } from "vue";
import ChartPanel from "../components/ChartPanel.vue";
import { fetchGrowthDashboard } from "../services/api";
import { horizontalBarOption } from "../utils/chartOptions";
import { contentLabel, formatNumber, formatPercent, sum } from "../utils/format";
import { diagnosisItems } from "../utils/pageModels";

defineProps({
  activePage: {
    type: String,
    default: "growth"
  }
});

const emit = defineEmits(["navigate"]);

const activeTab = ref(window.location.hash?.replace("#", "") || "overview");
const loading = ref(true);
const error = ref("");
const payload = ref(null);

const tabs = [
  { id: "overview", label: "实时概览" },
  { id: "conversion", label: "粉丝转化" },
  { id: "stickiness", label: "粉丝粘性" },
  { id: "distribution", label: "视频分布" }
];

onMounted(async () => {
  window.addEventListener("hashchange", syncHash);
  syncHash();
  await loadData();
});

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    payload.value = await fetchGrowthDashboard();
  } catch (apiError) {
    error.value = apiError.message;
  } finally {
    loading.value = false;
  }
}

function syncHash() {
  const next = window.location.hash.replace("#", "");
  if (tabs.some((tab) => tab.id === next)) {
    activeTab.value = next;
  } else {
    activeTab.value = "overview";
  }
  nextTick(() => {
    window.dispatchEvent(new CustomEvent("creatorpulse:replay-visible-charts"));
  });
}

function setTab(tabId) {
  const shouldReplay = activeTab.value === tabId;
  activeTab.value = tabId;
  window.location.hash = tabId;
  if (shouldReplay) {
    nextTick(() => {
      window.dispatchEvent(new CustomEvent("creatorpulse:replay-visible-charts"));
    });
  }
}

const creator = computed(() => payload.value?.creator);
const model = computed(() => payload.value?.data);
const snapshot = computed(() => model.value?.currentSnapshot);
const topVideos = computed(() => model.value?.topVideos || []);
const insights = computed(() => model.value?.insights || []);
const isWaitingForEvents = computed(() => snapshot.value?.dataStatus === "WAITING_FOR_EVENTS");
const growthIntroText = computed(() =>
  isWaitingForEvents.value
    ? "你的账号档案已创建，正在等待模拟事件接入。播放、互动、涨粉和健康度会在 Spark 写入指标后自动更新。"
    : "综合粉丝增长趋势、播放转粉率、粉丝粘性和内容效率，判断你的账号今天是否处在健康增长状态。"
);
const conversionRateHint = computed(() => (isWaitingForEvents.value ? "等待事件" : "高于均值"));
const stickinessHint = computed(() => (isWaitingForEvents.value ? "等待互动事件" : "高价值互动"));
const latestVideoTitle = computed(() => (isWaitingForEvents.value ? "等待视频指标事件" : topVideos.value[0]?.title));
const leadingContentTypeText = computed(() => (isWaitingForEvents.value ? "待接入" : contentLabel(leadingContentType.value?.contentType)));
const nextSuggestionCopy = computed(() =>
  isWaitingForEvents.value
    ? "模拟事件接入后，将基于播放、互动和涨粉表现生成专属创作建议。"
    : "优先延展当前高转粉内容结构，把播放入口承接到主页关注和系列内容。"
);

const insightByTab = computed(() => {
  const grouped = {
    overview: [],
    conversion: [],
    stickiness: [],
    distribution: []
  };
  for (const insight of insights.value) {
    for (const target of insight.pageTargets || []) {
      if (target === "growth.overview") grouped.overview.push(insight);
      if (target === "growth.conversion") grouped.conversion.push(insight);
      if (target === "growth.stickiness") grouped.stickiness.push(insight);
      if (target === "growth.distribution") grouped.distribution.push(insight);
    }
  }
  return grouped;
});

const overviewInsights = computed(() => takeInsights("overview"));
const conversionInsights = computed(() => takeInsights("conversion"));
const stickinessInsights = computed(() => takeInsights("stickiness"));
const distributionInsights = computed(() => takeInsights("distribution"));
const conversionDiagnosis = computed(() =>
  diagnosisItems(conversionInsights.value, [
    { label: "今日结论", title: "教程内容正在把高质量互动转成关注", className: "strong" },
    { label: "最大瓶颈", title: "主页访问承接效率关键，首屏 CTA 还需要更明确", className: "warning" },
    { label: "最佳来源", title: "高转粉视频结构值得继续复刻", className: "" }
  ])
);
const stickinessDiagnosis = computed(() =>
  diagnosisItems(stickinessInsights.value, [
    { label: "今日结论", title: "教程内容带来的收藏和复访最稳定", className: "strong" },
    { label: "高价值互动", title: "提问评论说明粉丝愿意继续交流", className: "" },
    { label: "低粘性风险", title: "泛流量点赞多，但复访偏低", className: "warning" }
  ])
);
const distributionDiagnosis = computed(() =>
  diagnosisItems(distributionInsights.value, [
    { label: "结构判断", title: "高转粉内容占比不高，但涨粉贡献最高", className: "strong" },
    { label: "内容倾向", title: "教程类贡献新粉，值得继续加码", className: "" },
    { label: "投入偏差", title: "低转粉泛流量内容需要减少", className: "warning" }
  ])
);

const totalViews = computed(() => sum(topVideos.value, "views"));
const totalFollowers = computed(() => sum(topVideos.value, "newFollowers"));
const totalProfiles = computed(() => sum(topVideos.value, "profileVisits"));
const totalInteractions = computed(() =>
  topVideos.value.reduce((value, video) => value + video.likes + video.comments + video.shares + video.saves, 0)
);
const totalSaves = computed(() => sum(topVideos.value, "saves"));
const totalComments = computed(() => sum(topVideos.value, "comments"));
const totalShares = computed(() => sum(topVideos.value, "shares"));
const platformCount = computed(() => new Set(topVideos.value.map((video) => video.platform)).size);
const latestVideoChartValues = [38, 54, 78, 92, 68];
const latestVideoChartDisplayValues = computed(() => (isWaitingForEvents.value ? [0, 0, 0, 0, 0] : latestVideoChartValues));

const contentTypeRows = computed(() => {
  const rows = {};
  for (const video of topVideos.value) {
    rows[video.contentType] ||= { contentType: video.contentType, views: 0, newFollowers: 0, saves: 0 };
    rows[video.contentType].views += video.views;
    rows[video.contentType].newFollowers += video.newFollowers;
    rows[video.contentType].saves += video.saves;
  }
  return Object.values(rows).sort((a, b) => b.newFollowers - a.newFollowers);
});
const leadingContentType = computed(() => contentTypeRows.value[0]);
const numberForChart = (value) => Number(value || 0);

const chartTextColor = "rgba(255,255,255,0.82)";
const chartMutedColor = "rgba(255,255,255,0.46)";

const growthHealthChartOption = computed(() => ({
  animationDuration: 1600,
  animationDurationUpdate: 1600,
  tooltip: {
    trigger: "item",
    formatter: "{b}<br/>{c} 分"
  },
  series: [
    {
      type: "gauge",
      name: "账号增长健康度",
      startAngle: 90,
      endAngle: -270,
      min: 0,
      max: 100,
      radius: "88%",
      pointer: { show: false },
      progress: {
        show: true,
        roundCap: true,
        width: 16,
        itemStyle: { color: "#bcff00" }
      },
      axisLine: {
        roundCap: true,
        lineStyle: { width: 16, color: [[1, "rgba(255,255,255,0.08)"]] }
      },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      title: { show: false },
      detail: { show: false },
      data: [{ value: Math.round(numberForChart(snapshot.value?.growthHealthScore)), name: "账号增长健康度" }]
    },
    {
      type: "gauge",
      name: "粉丝粘性",
      startAngle: 90,
      endAngle: -270,
      min: 0,
      max: 100,
      radius: "64%",
      pointer: { show: false },
      progress: {
        show: true,
        roundCap: true,
        width: 7,
        itemStyle: { color: "#9a8eff" }
      },
      axisLine: {
        roundCap: true,
        lineStyle: { width: 7, color: [[1, "rgba(255,255,255,0.08)"]] }
      },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      title: { show: false },
      detail: { show: false },
      data: [{ value: numberForChart(snapshot.value?.stickinessScore), name: "粉丝粘性" }]
    }
  ]
}));

const funnelChartOption = computed(() => ({
  animationDuration: 1600,
  animationDurationUpdate: 1600,
  tooltip: {
    trigger: "axis",
    axisPointer: { type: "shadow" },
    formatter(params) {
      const item = params[0];
      return `${item.name}<br/>${formatNumber(item.value)}`;
    }
  },
  grid: { left: 0, right: 0, top: 4, bottom: 4, containLabel: false },
  xAxis: { type: "value", show: false, max: Math.max(numberForChart(totalViews.value), 1) },
  yAxis: {
    type: "category",
    inverse: true,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { show: false },
    data: ["播放", "互动", "主页访问", "新增关注"]
  },
  series: [
    {
      type: "bar",
      barWidth: 34,
      itemStyle: {
        borderRadius: 8,
        color(params) {
          return ["#bcff00", "#9a8eff", "#61f4ff", "#bcff00"][params.dataIndex];
        }
      },
      label: {
        show: true,
        position: "insideLeft",
        color: "#111",
        fontSize: 11,
        fontWeight: 850,
        formatter(params) {
          return `${params.name} ${formatNumber(params.value)}`;
        }
      },
      data: [
        numberForChart(totalViews.value),
        numberForChart(totalInteractions.value),
        numberForChart(totalProfiles.value),
        numberForChart(totalFollowers.value)
      ]
    }
  ]
}));

const latestVideoChartOption = computed(() => ({
  animationDuration: 1600,
  animationDurationUpdate: 1600,
  tooltip: {
    trigger: "axis",
    axisPointer: { type: "shadow" },
    formatter(params) {
      const item = params[0];
      return `${item.name}<br/>增长强度 ${item.value}`;
    }
  },
  grid: { left: 0, right: 0, top: 10, bottom: 0, containLabel: false },
  xAxis: { type: "category", show: false, data: ["曝光", "点击", "互动", "关注", "回看"] },
  yAxis: { type: "value", show: false, max: Math.max(...latestVideoChartDisplayValues.value, 1) },
  series: [
    {
      type: "bar",
      barWidth: 86,
      itemStyle: {
        borderRadius: 6,
        color(params) {
          return params.dataIndex === 2 ? "#bcff00" : "rgba(255,255,255,0.28)";
        }
      },
      data: latestVideoChartDisplayValues.value
    }
  ]
}));

const contentMixChartOption = computed(() => ({
  animationDuration: 1600,
  animationDurationUpdate: 1600,
  tooltip: {
    trigger: "axis",
    axisPointer: { type: "shadow" },
    formatter(params) {
      const row = contentTypeRows.value[params[0].dataIndex];
      return `${contentLabel(row?.contentType)}<br/>播放 ${formatNumber(row?.views)}<br/>涨粉 ${formatNumber(row?.newFollowers)}`;
    }
  },
  grid: { left: 0, right: 0, top: 8, bottom: 0, containLabel: false },
  xAxis: { type: "category", show: false, data: contentTypeRows.value.slice(0, 5).map((row) => contentLabel(row.contentType)) },
  yAxis: { type: "value", show: false, max: Math.max(...contentTypeRows.value.slice(0, 5).map((row) => Number(row.newFollowers || 0)), 1) },
  series: [
    {
      type: "bar",
      barWidth: 52,
      itemStyle: {
        borderRadius: 6,
        color(params) {
          return ["rgba(255,255,255,0.34)", "#9a8eff", "#bcff00", "#9a8eff", "rgba(255,255,255,0.26)"][params.dataIndex] || "#bcff00";
        }
      },
      data: contentTypeRows.value.slice(0, 5).map((row) => row.newFollowers || 0)
    }
  ]
}));

const stickinessChartOption = computed(() => ({
  animationDuration: 1600,
  animationDurationUpdate: 1600,
  tooltip: {
    trigger: "axis",
    axisPointer: { type: "shadow" },
    formatter(params) {
      const item = params[0];
      return `${item.name}<br/>${formatNumber(item.value)}`;
    }
  },
  grid: { left: 0, right: 0, top: 4, bottom: 4, containLabel: false },
  xAxis: { type: "value", show: false, max: Math.max(numberForChart(totalSaves.value), numberForChart(totalComments.value), 1) },
  yAxis: {
    type: "category",
    inverse: true,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { show: false },
    data: ["评论", "收藏"]
  },
  series: [
    {
      type: "bar",
      barWidth: 34,
      itemStyle: {
        borderRadius: 8,
        color(params) {
          return params.dataIndex === 0 ? "#bcff00" : "#9a8eff";
        }
      },
      label: {
        show: true,
        position: "insideLeft",
        color: "#111",
        fontSize: 11,
        fontWeight: 850,
        formatter(params) {
          return `${params.name} ${formatNumber(params.value)}`;
        }
      },
      data: [numberForChart(totalComments.value), numberForChart(totalSaves.value)]
    }
  ]
}));
const stickinessTrendChartOption = computed(() =>
  horizontalBarOption(
    [
      { label: "收藏", value: sum(topVideos.value, "saves"), text: formatNumber(sum(topVideos.value, "saves")) },
      { label: "评论", value: sum(topVideos.value, "comments"), text: formatNumber(sum(topVideos.value, "comments")), color: "#9a8eff" },
      { label: "分享", value: sum(topVideos.value, "shares"), text: formatNumber(sum(topVideos.value, "shares")), color: "#61f4ff" },
      { label: "新增关注", value: totalFollowers.value, text: formatNumber(totalFollowers.value) }
    ],
    { barWidth: 34, animateLabels: true, duration: 2200, labelFormatter: (value) => formatNumber(value) }
  )
);

function takeInsights(tab) {
  const items = insightByTab.value[tab] || [];
  return items.slice(0, 3);
}

</script>

<template>
  <nav class="left-dock" aria-label="主导航">
    <button class="dock-item active" type="button" aria-label="增长总览" @click="emit('navigate', 'growth')"><i class="fa-solid fa-house"></i></button>
    <button class="dock-item" type="button" aria-label="粉丝分析" @click="emit('navigate', 'fans')"><i class="fa-solid fa-users"></i></button>
    <button class="dock-item" type="button" aria-label="视频分析" @click="emit('navigate', 'video')"><i class="fa-solid fa-play"></i></button>
    <button class="dock-item" type="button" aria-label="内容分布" @click="emit('navigate', 'content')"><i class="fa-solid fa-chart-pie"></i></button>
    <button class="dock-item" type="button" aria-label="机会建议" @click="emit('navigate', 'opportunities')"><i class="fa-solid fa-fire"></i></button>
    <button class="dock-item" type="button" aria-label="个人中心" @click="emit('navigate', 'profile')"><i class="fa-solid fa-gear"></i></button>
  </nav>

  <main class="glass-board">
    <div class="dashboard-content">
      <header class="board-header">
        <div class="brand-logo"><i class="fa-solid fa-circle-notch"></i> CreatorPulse</div>
        <div class="top-pills-tabs" role="tablist">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            class="top-pill"
            :class="{ active: activeTab === tab.id }"
            type="button"
            role="tab"
            :aria-selected="activeTab === tab.id"
            @click="setTab(tab.id)"
          >
            {{ tab.label }}
          </button>
        </div>
        <div class="user-profile">
          <span class="sync-chip">5s Sync</span>
          <i class="fa-regular fa-bell" style="color:var(--text-dim)"></i>
          <div class="user-avatar"></div>
        </div>
      </header>

      <section v-if="loading" class="card app-state-card">
        <p class="section-label">Loading</p>
        <strong class="value">正在加载增长总览数据</strong>
      </section>

      <section v-else-if="error" class="card app-state-card">
        <p class="section-label">API Error</p>
        <strong class="value">{{ error }}</strong>
        <p class="page-copy">请先启动 Flask API：python api\\app.py</p>
      </section>

      <template v-else>
        <section v-show="activeTab === 'overview'" class="tab-panel active">
          <section class="layout-main">
            <div>
              <p class="eyebrow">Growth Health</p>
              <h1>你的账号<br>增长健康度</h1>
              <p v-if="isWaitingForEvents" class="page-copy">{{ growthIntroText }}</p>
              <p v-else class="page-copy">
                综合粉丝增长趋势、播放转粉率、粉丝粘性和内容效率，判断你的账号今天是否处在健康增长状态。
              </p>

              <div class="huge-circle" aria-label="账号增长健康度">
                <ChartPanel :option="growthHealthChartOption" />
                <div class="circle-copy">
                  <strong>{{ Math.round(snapshot?.growthHealthScore || 0) }}</strong>
                  <span>账号增长健康度</span>
                  <span style="color:var(--neon-green);font-weight:800">粘性 {{ snapshot?.stickinessScore }}</span>
                </div>
              </div>

              <div v-if="isWaitingForEvents" class="grid-3">
                <div class="metric-card"><p>今日新粉</p><strong>0</strong><span class="delta">等待事件</span></div>
                <div class="metric-card"><p>播放转粉率</p><strong>0.00%</strong><span class="delta">等待事件</span></div>
                <div class="metric-card"><p>粘性指数</p><strong>0</strong><span class="delta">等待互动事件</span></div>
              </div>
              <div v-else class="grid-3">
                <div class="metric-card"><p>今日新粉</p><strong>{{ formatNumber(snapshot?.newFollowers) }}</strong><span class="delta">净增 {{ formatNumber(snapshot?.netFollowers) }}</span></div>
                <div class="metric-card"><p>播放转粉率</p><strong>{{ formatPercent(snapshot?.viewToFollowerRate) }}</strong><span class="delta">高于均值</span></div>
                <div class="metric-card"><p>粘性指数</p><strong>{{ snapshot?.stickinessScore }}</strong><span class="delta">高价值互动</span></div>
              </div>
            </div>

            <div style="display:flex;flex-direction:column;gap:22px">
              <div class="grid-6">
                <div class="metric-card"><p>平台</p><strong>{{ platformCount }}</strong></div>
                <div class="metric-card"><p>内容</p><strong>{{ topVideos.length }}</strong></div>
                <div class="metric-card"><p>总播放</p><strong>{{ formatNumber(totalViews) }}</strong></div>
                <div class="metric-card"><p>新粉</p><strong>{{ formatNumber(totalFollowers) }}</strong></div>
                <div class="metric-card"><p>转粉率</p><strong>{{ formatPercent(totalFollowers / totalViews) }}</strong></div>
                <div class="metric-card"><p>同步延迟</p><strong>5s</strong></div>
              </div>

              <div class="grid-2">
                <article v-if="isWaitingForEvents" class="card white">
                  <p class="label" style="color:#666">粉丝转化漏斗</p>
                  <strong class="value large">0</strong>
                  <span style="font-size:12px;color:#ff5e5e;font-weight:800">等待播放、主页访问和关注事件</span>
                  <ChartPanel class="chart-panel-funnel" :option="funnelChartOption" />
                </article>
                <article v-else class="card white">
                  <p class="label" style="color:#666">粉丝转化漏斗</p>
                  <strong class="value large">{{ formatNumber(totalFollowers) }}</strong>
                  <span style="font-size:12px;color:#ff5e5e;font-weight:800">主页访问到关注 {{ formatPercent(totalFollowers / totalProfiles) }}</span>
                  <ChartPanel class="chart-panel-funnel" :option="funnelChartOption" />
                </article>
                <article v-if="isWaitingForEvents" class="card purple">
                  <p class="label" style="color:#111">最新视频涨粉表现</p>
                  <strong class="value large">+0</strong>
                  <span style="font-size:12px;color:#fff;font-weight:800">等待视频指标事件</span>
                  <ChartPanel class="chart-panel-bars" :option="latestVideoChartOption" />
                </article>
                <article v-else class="card purple">
                  <p class="label" style="color:#111">最新视频涨粉表现</p>
                  <strong class="value large">+{{ formatNumber(topVideos[0]?.newFollowers) }}</strong>
                  <span style="font-size:12px;color:#fff;font-weight:800">{{ topVideos[0]?.title }}</span>
                  <ChartPanel class="chart-panel-bars" :option="latestVideoChartOption" />
                </article>
              </div>

              <div class="grid-3">
                <article v-if="isWaitingForEvents" class="card">
                  <p class="section-label">视频分布情况</p>
                  <strong class="value">待接入</strong>
                  <span class="delta">涨粉 0</span>
                  <ChartPanel class="chart-panel-bars compact" :option="contentMixChartOption" />
                </article>
                <article v-if="!isWaitingForEvents" class="card">
                  <p class="section-label">视频分布情况</p>
                  <strong class="value">{{ contentLabel(leadingContentType?.contentType) }}</strong>
                  <span class="delta">涨粉 {{ formatNumber(leadingContentType?.newFollowers) }}</span>
                  <ChartPanel class="chart-panel-bars compact" :option="contentMixChartOption" />
                </article>
                <article v-if="isWaitingForEvents" class="card">
                  <p class="section-label">下一步创作建议</p>
                  <strong class="value">等待数据</strong>
                  <span class="delta">分享 0</span>
                  <p class="page-copy" style="margin-top:12px">模拟事件接入后，将基于播放、互动和涨粉表现生成专属创作建议。</p>
                </article>
                <article v-else class="card">
                  <p class="section-label">粉丝粘性信号</p>
                  <strong class="value">{{ snapshot?.stickinessScore }}</strong>
                  <span class="delta">收藏 {{ formatNumber(totalSaves) }}</span>
                  <ChartPanel class="chart-panel-mini" :option="stickinessChartOption" />
                </article>
                <article v-if="!isWaitingForEvents" class="card">
                  <p class="section-label">下一步创作建议</p>
                  <strong class="value">{{ contentLabel(leadingContentType?.contentType) }}</strong>
                  <span class="delta">分享 {{ formatNumber(totalShares) }}</span>
                  <p class="page-copy" style="margin-top:12px">优先延展当前高转粉内容结构，把播放入口承接到主页关注和系列内容。</p>
                </article>
              </div>
            </div>
          </section>
        </section>

        <section v-show="activeTab === 'conversion'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Conversion Diagnosis</p><h1>转化诊断台</h1></div>
            <p class="page-copy">追踪你的内容从曝光到关注的每一步，找到今天最该修正的转化瓶颈和最值得复刻的涨粉路径。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in conversionDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span>
              <strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card white">
              <p class="label" style="color:#666">路径漏斗与掉点</p>
              <div class="path-flow">
                <div class="path-step hot"><span>播放</span><strong>{{ formatNumber(totalViews) }}</strong><em>入口充足</em></div>
                <div class="path-step"><span>互动</span><strong>{{ formatNumber(totalInteractions) }}</strong><em>互动形成兴趣</em></div>
                <div class="path-step risk"><span>主页访问</span><strong>{{ formatNumber(totalProfiles) }}</strong><em>承接效率关键</em></div>
                <div class="path-step"><span>关注</span><strong>{{ formatNumber(totalFollowers) }}</strong><em>{{ formatPercent(totalFollowers / totalViews) }}</em></div>
              </div>
            </article>
            <article class="card">
              <p class="section-label">下一步动作</p>
              <div class="action-list">
                <div v-for="item in conversionInsights.flatMap((insight) => insight.recommendedActions).slice(0, 3)" :key="item.actionId">
                  <i class="fa-solid fa-arrow-up-right-dots"></i><span>{{ item.description }}</span>
                </div>
              </div>
            </article>
          </section>
        </section>

        <section v-show="activeTab === 'stickiness'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Fan Quality Diagnosis</p><h1>粉丝质量诊断</h1></div>
            <p class="page-copy">根据收藏、评论、分享和 Insight 判断你的粉丝是否正在形成高价值互动。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in stickinessDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span>
              <strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">粘性趋势拆解</p>
              <ChartPanel class="chart-panel-funnel" :option="stickinessTrendChartOption" />
            </article>
            <article class="card">
              <p class="section-label">下一步动作</p>
              <div class="action-list">
                <div v-for="item in stickinessInsights.flatMap((insight) => insight.recommendedActions).slice(0, 3)" :key="item.actionId">
                  <i class="fa-solid fa-bookmark"></i><span>{{ item.description }}</span>
                </div>
              </div>
            </article>
          </section>
        </section>

        <section v-show="activeTab === 'distribution'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Content Mix Calibration</p><h1>内容结构校准</h1></div>
            <p class="page-copy">比较你的发布投入、播放贡献和涨粉贡献，判断下周内容应该多发什么、在哪发、什么时候发。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in distributionDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span>
              <strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">内容类型贡献</p>
              <table class="table">
                <tr><th>类型</th><th>播放</th><th>新粉</th><th>收藏</th></tr>
                <tr v-for="row in contentTypeRows" :key="row.contentType">
                  <td>{{ contentLabel(row.contentType) }}</td>
                  <td>{{ formatNumber(row.views) }}</td>
                  <td>{{ formatNumber(row.newFollowers) }}</td>
                  <td>{{ formatNumber(row.saves) }}</td>
                </tr>
              </table>
            </article>
            <article class="card">
              <p class="section-label">下周发布配比建议</p>
              <div class="action-list">
                <div v-for="item in distributionInsights.flatMap((insight) => insight.recommendedActions).slice(0, 3)" :key="item.actionId">
                  <i class="fa-solid fa-video"></i><span>{{ item.description }}</span>
                </div>
              </div>
            </article>
          </section>
        </section>
      </template>
    </div>
  </main>
</template>
