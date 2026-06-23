<script setup>
import { computed, onMounted, ref } from "vue";
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

const loading = ref(true);
const error = ref("");
const payload = ref(null);
const healthTooltip = ref({ visible: false, x: 130, y: 130 });

onMounted(async () => {
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
const leadingContentTypeText = computed(() => (isWaitingForEvents.value ? "待接入" : contentLabel(leadingContentType.value?.contentType)));
const nextSuggestionCopy = computed(() =>
  isWaitingForEvents.value
    ? "模拟事件接入后，将基于播放、互动和涨粉表现生成专属创作建议。"
    : `${contentLabel(leadingContentType.value?.contentType)}带来 ${formatNumber(leadingContentType.value?.newFollowers)} 个新粉，优先延展这类高转粉内容。`
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

const accountPlatformCount = computed(() => model.value?.platformCount ?? new Set(topVideos.value.map((video) => video.platform)).size);
const accountNewPlatformCount = computed(() => model.value?.newPlatformCount ?? 0);
const accountVideoCount = computed(() => model.value?.videoCount ?? topVideos.value.length);
const accountNewVideoCount = computed(() => model.value?.newVideoCount ?? 0);
const accountTotalViews = computed(() => model.value?.totalViews ?? sum(topVideos.value, "views"));
const accountNewViews = computed(() => model.value?.newViews ?? 0);
const accountTotalFollowers = computed(() => model.value?.totalFollowers ?? snapshot.value?.totalFollowers ?? 0);
const accountNewFollowers = computed(() => Number(model.value?.newFollowers || 0));
const accountTotalInteractions = computed(() => Number(model.value?.totalInteractions ?? snapshot.value?.totalInteractions ?? 0));
const accountProfileVisits = computed(() => Number(model.value?.profileVisits ?? snapshot.value?.profileVisits ?? 0));
const accountSyncLatencySeconds = computed(() => Number(model.value?.syncLatencySeconds ?? 0));
const accountConversionRate = computed(() => Number(snapshot.value?.viewToFollowerRate ?? (accountTotalViews.value ? accountNewFollowers.value / accountTotalViews.value : 0)));
const conversionRateHint = computed(() => (isWaitingForEvents.value ? "等待事件" : model.value?.conversionRateStatus || "按目标评估"));
const stickinessActionText = computed(() =>
  calibratedStickinessScore.value >= 1 ? "互动承接稳定" : "互动承接偏弱"
);
const topVideoActionText = computed(() =>
  numberForChart(topVideos.value[0]?.newFollowers) >= accountNewFollowers.value * 0.2
    ? "适合继续复刻"
    : "适合继续观察"
);
const syncLatencyText = computed(() => (accountSyncLatencySeconds.value <= 10 ? "实时同步" : "同步延迟偏高"));
const syncLatencyDisplay = computed(() => `${formatNumber(accountSyncLatencySeconds.value)}s`);
const latestVideoFollowerRows = computed(() => {
  if (isWaitingForEvents.value) {
    return Array.from({ length: 5 }, (_, index) => ({ label: `第${index + 1}条`, value: 0 }));
  }
  return topVideos.value.slice(0, 5).map((video, index) => ({
    label: index === 0 ? "最涨粉" : `第${index + 1}名`,
    value: numberForChart(video?.newFollowers),
    title: video?.title || `第${index + 1}条视频`
  }));
});

const contentTypeRows = computed(() => {
  if (model.value?.contentTypeRows?.length) {
    return [...model.value.contentTypeRows].sort((a, b) => Number(b.newFollowers || 0) - Number(a.newFollowers || 0));
  }
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
const clampScore = (value) => Math.max(0, Math.min(100, Number(value || 0)));
const calibratedStickinessScore = computed(() =>
  accountTotalViews.value ? clampScore((accountTotalInteractions.value / accountTotalViews.value) * 180) : clampScore(snapshot.value?.stickinessScore)
);
const currentGrowthHealthScore = computed(() => clampScore(snapshot.value?.growthHealthScore));
const currentGrowthHealthScoreDisplay = computed(() => Math.round(currentGrowthHealthScore.value));
const conversionSteps = computed(() => [
  { key: "views", label: "播放", value: accountTotalViews.value, tone: "green" },
  { key: "interactions", label: "互动", value: accountTotalInteractions.value, tone: "purple" },
  { key: "profiles", label: "进主页", value: accountProfileVisits.value, tone: "cyan" },
  { key: "followers", label: "关注", value: accountNewFollowers.value, tone: "green" }
]);
const conversionFunnelVisualWidths = [100, 72, 58, 44];
const conversionFunnelRows = computed(() => {
  return conversionSteps.value.map((step, index) => {
    const next = conversionSteps.value[index + 1];
    const nextRate = next && step.value ? next.value / step.value : null;
    return {
      ...step,
      index,
      realValue: Number(step.value || 0),
      visualWidth: conversionFunnelVisualWidths[index] || 44,
      nextRate
    };
  });
});
const conversionStepHint = (step) => (step.nextRate === null ? "最终关注" : `下一步 ${formatPercent(step.nextRate)}`);
const healthFormulaParts = computed(() => {
  const current = snapshot.value || {};
  const profileVisits = accountProfileVisits.value;
  const viewToFollowerRate = accountConversionRate.value;
  const profileConversionRate = profileVisits ? accountNewFollowers.value / profileVisits : 0;
  const interactionRate = accountTotalViews.value ? accountTotalInteractions.value / accountTotalViews.value : 0;
  const retainedFollowerRate = accountNewFollowers.value ? numberForChart(current.netFollowers) / accountNewFollowers.value : 0;
  const targetScore = (value, target, points) => Math.min(points, (Number(value || 0) / target) * points);
  const parts = [
    {
      label: "播放转粉",
      source: `${formatPercent(viewToFollowerRate)} / 目标 ${formatPercent(0.0008)}`,
      points: targetScore(viewToFollowerRate, 0.0008, 40)
    },
    {
      label: "主页承接",
      source: `${formatPercent(profileConversionRate)} / 目标 ${formatPercent(0.08)}`,
      points: targetScore(profileConversionRate, 0.08, 30)
    },
    {
      label: "互动粘性",
      source: `${formatPercent(interactionRate)} / 目标 ${formatPercent(0.03)}`,
      points: targetScore(interactionRate, 0.03, 20)
    },
    {
      label: "新增留存",
      source: `${formatPercent(retainedFollowerRate)} / 目标 ${formatPercent(0.9)}`,
      points: targetScore(retainedFollowerRate, 0.9, 10)
    }
  ];
  let runningTotal = 0;
  const rows = parts.map((part) => {
    runningTotal += part.points;
    return {
      ...part,
      cumulative: runningTotal
    };
  });
  const subtotal = rows.reduce((total, item) => total + item.points, 0);
  const finalScore = currentGrowthHealthScoreDisplay.value;
  return { parts: rows, subtotal, finalScore };
});

const chartTextColor = "rgba(255,255,255,0.82)";
const chartMutedColor = "rgba(255,255,255,0.46)";

const growthHealthChartOption = computed(() => ({
  animationDuration: 1600,
  animationDurationUpdate: 1600,
  tooltip: {
    show: false
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
      data: [{ value: currentGrowthHealthScoreDisplay.value, name: "账号增长健康度" }]
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
      data: [{ value: calibratedStickinessScore.value, name: "粉丝粘性" }]
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
      const row = latestVideoFollowerRows.value[item.dataIndex];
      return `${row?.title || item.name}<br/>新增粉丝 +${formatNumber(item.value)}`;
    }
  },
  grid: { left: 8, right: 8, top: 30, bottom: 28, containLabel: false },
  xAxis: {
    type: "category",
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: "rgba(17,17,17,0.68)",
      fontSize: 11,
      fontWeight: 850,
      interval: 0
    },
    data: latestVideoFollowerRows.value.map((row) => row.label)
  },
  yAxis: { type: "value", show: false, max: Math.max(...latestVideoFollowerRows.value.map((row) => row.value), 1) },
  series: [
    {
      type: "bar",
      barWidth: 48,
      itemStyle: {
        borderRadius: [8, 8, 8, 8],
        color(params) {
          return params.dataIndex === 0 ? "#bcff00" : "rgba(255,255,255,0.36)";
        }
      },
      label: {
        show: true,
        position: "top",
        color: "#111",
        fontSize: 12,
        fontWeight: 900,
        formatter(params) {
          return `+${formatNumber(params.value)}粉`;
        }
      },
      data: latestVideoFollowerRows.value.map((row) => row.value)
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
      return `${contentLabel(row?.contentType)}内容<br/>播放 ${formatNumber(row?.views)}<br/>新增粉丝 ${formatNumber(row?.newFollowers)}`;
    }
  },
  grid: { left: 0, right: 0, top: 26, bottom: 26, containLabel: false },
  xAxis: { type: "category", show: false, data: contentTypeRows.value.slice(0, 5).map((row) => contentLabel(row.contentType)) },
  yAxis: { type: "value", show: false, max: Math.max(...contentTypeRows.value.slice(0, 5).map((row) => Number(row.newFollowers || 0)), 1) * 1.24 },
  series: [
    {
      type: "bar",
      barWidth: 44,
      itemStyle: {
        borderRadius: 6,
        color(params) {
          return ["#ffffff", "#9a8eff", "#bcff00", "#9a8eff", "#ffffff"][params.dataIndex] || "#ffffff";
        }
      },
      label: {
        show: true,
        position(params) {
          const maxValue = Math.max(...contentTypeRows.value.slice(0, 5).map((row) => Number(row.newFollowers || 0)), 1);
          return Number(params.value || 0) >= maxValue * 0.36 ? "insideTop" : "top";
        },
        distance: 5,
        color: "#111",
        fontSize: 10,
        lineHeight: 12,
        fontWeight: 850,
        width: 58,
        overflow: "break",
        formatter(params) {
          const row = contentTypeRows.value[params.dataIndex];
          return `${contentLabel(row?.contentType)}\n${formatNumber(params.value)}新粉`;
        }
      },
      labelLayout: {
        hideOverlap: false
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
      return `${item.name}次数<br/>${formatNumber(item.value)}`;
    }
  },
  grid: { left: 0, right: 0, top: 4, bottom: 4, containLabel: false },
  xAxis: { type: "value", show: false, max: Math.max(numberForChart(accountTotalInteractions.value), numberForChart(accountNewFollowers.value), 1) },
  yAxis: {
    type: "category",
    inverse: true,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { show: false },
    data: ["互动", "新粉"]
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
      data: [numberForChart(accountTotalInteractions.value), numberForChart(accountNewFollowers.value)]
    }
  ]
}));
function takeInsights(tab) {
  const items = insightByTab.value[tab] || [];
  return items.slice(0, 3);
}

function moveHealthTooltip(event) {
  const rect = event.currentTarget.getBoundingClientRect();
  const cardWidth = Math.min(320, window.innerWidth - 56);
  const cardHeight = 340;
  const pointerX = Number.isFinite(event.clientX) ? event.clientX : rect.right;
  const pointerY = Number.isFinite(event.clientY) ? event.clientY : rect.top + rect.height / 2;
  const nextX = Math.min(pointerX + 18, window.innerWidth - cardWidth - 18);
  const nextY = Math.min(pointerY + 18, window.innerHeight - cardHeight - 18);
  healthTooltip.value = {
    visible: true,
    x: Math.max(18, nextX),
    y: Math.max(18, nextY)
  };
}

function showHealthTooltip(event) {
  moveHealthTooltip(event);
}

function hideHealthTooltip() {
  healthTooltip.value.visible = false;
}

</script>

<template>
  <nav class="left-dock" aria-label="主导航">
    <button class="dock-item active" type="button" aria-label="增长总览" @click="emit('navigate', 'growth')"><i class="fa-solid fa-house"></i></button>
    <button class="dock-item" type="button" aria-label="粉丝分析" @click="emit('navigate', 'fans')"><i class="fa-solid fa-users"></i></button>
    <button class="dock-item" type="button" aria-label="内容分布" @click="emit('navigate', 'content')"><i class="fa-solid fa-chart-pie"></i></button>
    <button class="dock-item" type="button" aria-label="机会建议" @click="emit('navigate', 'opportunities')"><i class="fa-solid fa-fire"></i></button>
    <button class="dock-item" type="button" aria-label="个人中心" @click="emit('navigate', 'profile')"><i class="fa-solid fa-gear"></i></button>
  </nav>

  <main class="glass-board">
    <div class="dashboard-content">
      <header class="board-header">
        <div class="brand-logo"><i class="fa-solid fa-circle-notch"></i> CreatorPulse</div>
        <div class="user-profile">
          <span class="sync-chip">{{ syncLatencyDisplay }} Sync</span>
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
        <section class="tab-panel active">
          <section class="layout-main">
            <div>
              <p class="eyebrow">Growth Health</p>
              <h1>你的账号<br>增长健康度</h1>
              <p v-if="isWaitingForEvents" class="page-copy">{{ growthIntroText }}</p>
              <p v-else class="page-copy">
                综合粉丝增长趋势、播放转粉率、粉丝粘性和内容效率，判断你的账号今天是否处在健康增长状态。
              </p>

              <div
                class="huge-circle health-tooltip-anchor"
                aria-label="账号增长健康度"
                :style="{ '--tooltip-x': `${healthTooltip.x}px`, '--tooltip-y': `${healthTooltip.y}px` }"
                tabindex="0"
                @mouseenter="showHealthTooltip"
                @mousemove="moveHealthTooltip"
                @mouseleave="hideHealthTooltip"
                @focusin="showHealthTooltip"
                @focusout="hideHealthTooltip"
              >
                <ChartPanel :option="growthHealthChartOption" />
                <div class="circle-copy">
                  <strong>{{ currentGrowthHealthScoreDisplay }}</strong>
                  <span>账号增长健康度</span>
                  <span style="color:var(--neon-green);font-weight:800">粘性 {{ calibratedStickinessScore.toFixed(2) }}</span>
                </div>
                <aside v-show="healthTooltip.visible" class="health-formula-tooltip" aria-hidden="true">
                  <span class="health-formula-kicker">健康度公式</span>
                  <strong>{{ currentGrowthHealthScoreDisplay }} 分</strong>
                  <p>按播放转粉、主页承接、互动粘性和新增留存的目标达成度计分，最高 100 分。</p>
                  <div class="health-formula-list">
                    <div v-for="part in healthFormulaParts.parts" :key="part.label">
                      <span>{{ part.label }}</span>
                      <em>{{ part.source }}</em>
                      <strong>+{{ part.points.toFixed(1) }}</strong>
                      <small>累计 {{ part.cumulative.toFixed(1) }}</small>
                    </div>
                  </div>
                  <footer>
                    <span>封顶前 {{ healthFormulaParts.subtotal.toFixed(1) }}</span>
                    <strong>{{ currentGrowthHealthScoreDisplay }} 分</strong>
                  </footer>
                </aside>
              </div>

              <div v-if="isWaitingForEvents" class="grid-3">
                <div class="metric-card"><p>今日新粉</p><strong>0</strong><span class="delta">等待事件</span></div>
                <div class="metric-card"><p>播放转粉率</p><strong>0.00%</strong><span class="delta">等待事件</span></div>
                <div class="metric-card"><p>粘性指数</p><strong>0</strong><span class="delta">等待互动事件</span></div>
              </div>
              <div v-else class="grid-3">
                <div class="metric-card"><p>今日新粉</p><strong>{{ formatNumber(accountNewFollowers) }}</strong><span class="delta">合计新增 {{ formatNumber(accountNewFollowers) }}</span></div>
                <div class="metric-card"><p>播放转粉率</p><strong>{{ formatPercent(accountConversionRate) }}</strong><span class="delta">{{ conversionRateHint }}</span></div>
                <div class="metric-card"><p>粘性指数</p><strong>{{ calibratedStickinessScore.toFixed(2) }}</strong><span class="delta">互动率校准</span></div>
              </div>
            </div>

            <div style="display:flex;flex-direction:column;gap:22px">
              <div class="grid-6">
                <div class="metric-card"><p>总粉丝</p><strong>{{ formatNumber(accountTotalFollowers) }}</strong><span class="delta">+{{ formatNumber(accountNewFollowers) }}</span></div>
                <div class="metric-card"><p>总播放</p><strong>{{ formatNumber(accountTotalViews) }}</strong><span class="delta">+{{ formatNumber(accountNewViews) }}</span></div>
                <div class="metric-card"><p>总视频</p><strong>{{ formatNumber(accountVideoCount) }}</strong><span class="delta">+{{ formatNumber(accountNewVideoCount) }}</span></div>
                <div class="metric-card"><p>转粉率</p><strong>{{ formatPercent(accountConversionRate) }}</strong><span class="delta">{{ conversionRateHint }}</span></div>
                <div class="metric-card"><p>平台</p><strong>{{ accountPlatformCount }}</strong><span class="delta">{{ accountNewPlatformCount > 0 ? `+${formatNumber(accountNewPlatformCount)}` : "已绑定" }}</span></div>
                <div class="metric-card"><p>同步延迟</p><strong>{{ syncLatencyDisplay }}</strong><span class="delta">{{ syncLatencyText }}</span></div>
              </div>

              <div class="grid-2">
                <article v-if="isWaitingForEvents" class="card white">
                  <p class="label" style="color:#666">看过的人怎么变成粉丝</p>
                  <strong class="value large">0</strong>
                  <span style="font-size:12px;color:#ff5e5e;font-weight:800">从播放、互动、进主页到最后关注，看看粉丝是在哪一步流失的</span>
                  <div class="straight-funnel" aria-label="播放到关注的转化路径">
                    <span class="straight-funnel-arrow left" aria-hidden="true"></span>
                    <span class="straight-funnel-arrow right" aria-hidden="true"></span>
                    <article
                      v-for="step in conversionFunnelRows"
                      :key="step.key"
                      class="straight-funnel-step"
                      :class="[`tone-${step.tone}`, `level-${step.index}`]"
                      :style="{ '--funnel-width': `${step.visualWidth}%`, '--funnel-delay': `${step.index * 0.12}s` }"
                    >
                      <div class="straight-funnel-main">
                        <span>{{ step.label }}</span>
                        <strong>{{ formatNumber(step.realValue) }}</strong>
                      </div>
                      <em>{{ conversionStepHint(step) }}</em>
                    </article>
                  </div>
                </article>
                <article v-else class="card white">
                  <p class="label" style="color:#666">看过的人怎么变成粉丝</p>
                  <strong class="value large">{{ formatNumber(accountNewFollowers) }}</strong>
                  <span style="font-size:12px;color:#ff5e5e;font-weight:800">进主页后关注率 {{ formatPercent(accountNewFollowers / accountProfileVisits) }}</span>
                  <div class="straight-funnel" aria-label="播放到关注的转化路径">
                    <span class="straight-funnel-arrow left" aria-hidden="true"></span>
                    <span class="straight-funnel-arrow right" aria-hidden="true"></span>
                    <article
                      v-for="step in conversionFunnelRows"
                      :key="step.key"
                      class="straight-funnel-step"
                      :class="[`tone-${step.tone}`, `level-${step.index}`]"
                      :style="{ '--funnel-width': `${step.visualWidth}%`, '--funnel-delay': `${step.index * 0.12}s` }"
                    >
                      <div class="straight-funnel-main">
                        <span>{{ step.label }}</span>
                        <strong>{{ formatNumber(step.realValue) }}</strong>
                      </div>
                      <em>{{ conversionStepHint(step) }}</em>
                    </article>
                  </div>
                </article>
                <article v-if="isWaitingForEvents" class="card purple">
                  <p class="label" style="color:#111">单条视频最高涨粉</p>
                  <strong class="value large">+0</strong>
                  <span style="font-size:12px;color:#fff;font-weight:800">单条内容新增 +0 粉，适合继续观察</span>
                  <span style="display:block;margin-top:4px;font-size:11px;color:rgba(17,17,17,0.62);font-weight:850">下方对比涨粉前 5 条视频的新增粉丝</span>
                  <ChartPanel class="chart-panel-bars" :option="latestVideoChartOption" />
                </article>
                <article v-else class="card purple">
                  <p class="label" style="color:#111">单条视频最高涨粉</p>
                  <strong class="value large">+{{ formatNumber(topVideos[0]?.newFollowers) }}</strong>
                  <span style="font-size:12px;color:#fff;font-weight:800">单条内容新增 +{{ formatNumber(topVideos[0]?.newFollowers) }} 粉，{{ topVideoActionText }}</span>
                  <span style="display:block;margin-top:4px;font-size:11px;color:rgba(17,17,17,0.62);font-weight:850">下方对比涨粉前 5 条视频的新增粉丝</span>
                  <ChartPanel class="chart-panel-bars" :option="latestVideoChartOption" />
                </article>
              </div>

              <div class="grid-3">
                <article v-if="isWaitingForEvents" class="card">
                  <p class="section-label">哪类视频更容易涨粉</p>
                  <strong class="value">暂无数据</strong>
                  <span class="delta">同步后看内容类型表现</span>
                  <ChartPanel class="chart-panel-bars compact" :option="contentMixChartOption" />
                </article>
                <article v-if="!isWaitingForEvents" class="card">
                  <p class="section-label">哪类视频更容易涨粉</p>
                  <strong class="value">{{ contentLabel(leadingContentType?.contentType) }}</strong>
                  <span class="delta">带来 {{ formatNumber(leadingContentType?.newFollowers) }} 个新粉</span>
                  <ChartPanel class="chart-panel-bars compact" :option="contentMixChartOption" />
                </article>
                <article v-if="isWaitingForEvents" class="card">
                  <p class="section-label">下一步创作建议</p>
                  <strong class="value">等待数据</strong>
                  <span class="delta">等待互动与分享数据</span>
                  <p class="page-copy" style="margin-top:12px">模拟事件接入后，将基于播放、互动和涨粉表现生成专属创作建议。</p>
                </article>
                <article v-else class="card">
                  <p class="section-label">粉丝愿不愿意互动</p>
                  <strong class="value">粉丝粘性-{{ calibratedStickinessScore.toFixed(2) }}</strong>
                  <span class="delta">互动 {{ formatNumber(accountTotalInteractions) }}，新粉 {{ formatNumber(accountNewFollowers) }}</span>
                  <ChartPanel class="chart-panel-mini" :option="stickinessChartOption" />
                </article>
                <article v-if="!isWaitingForEvents" class="card">
                  <p class="section-label">下一步创作建议</p>
                  <strong class="value">{{ contentLabel(leadingContentType?.contentType) }}</strong>
                  <span class="delta">{{ stickinessActionText }}</span>
                  <p class="page-copy" style="margin-top:12px">{{ nextSuggestionCopy }}</p>
                </article>
              </div>
            </div>
          </section>
        </section>
      </template>
    </div>
  </main>
</template>
