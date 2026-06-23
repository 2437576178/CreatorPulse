<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import ChartPanel from "../components/ChartPanel.vue";
import { fetchFansAnalysis } from "../services/api";
import { heatmapOption } from "../utils/chartOptions";
import { contentLabel, formatNumber, formatPercent } from "../utils/format";

defineProps({
  activePage: {
    type: String,
    default: "fans"
  }
});

const emit = defineEmits(["navigate"]);

const loading = ref(true);
const error = ref("");
const payload = ref(null);
const radarAnimationProgress = ref(0);
let radarAnimationFrame = null;

onMounted(async () => {
  await loadData();
});

onBeforeUnmount(() => {
  if (radarAnimationFrame) {
    window.cancelAnimationFrame(radarAnimationFrame);
  }
});

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    payload.value = await fetchFansAnalysis();
    replayRadarAnimation();
  } catch (apiError) {
    error.value = apiError.message;
  } finally {
    loading.value = false;
  }
}

function easeOutCubic(value) {
  return 1 - Math.pow(1 - value, 3);
}

function replayRadarAnimation() {
  if (radarAnimationFrame) {
    window.cancelAnimationFrame(radarAnimationFrame);
  }
  radarAnimationProgress.value = 0;
  const duration = 1600;
  const startTime = performance.now();

  function tick(now) {
    const rawProgress = Math.min((now - startTime) / duration, 1);
    radarAnimationProgress.value = easeOutCubic(rawProgress);
    if (rawProgress < 1) {
      radarAnimationFrame = window.requestAnimationFrame(tick);
      return;
    }
    radarAnimationFrame = null;
  }

  radarAnimationFrame = window.requestAnimationFrame(tick);
}

const creator = computed(() => payload.value?.creator);
const model = computed(() => payload.value?.data);
const trend = computed(() => model.value?.trend || []);
const latest = computed(() => trend.value[trend.value.length - 1]);
const topVideos = computed(() => model.value?.topVideos || []);
const profile = computed(() => model.value?.audienceProfile);
const insights = computed(() => model.value?.insights || []);
const syncLatencySeconds = computed(() => Number(model.value?.syncLatencySeconds ?? 0));
const syncLatencyDisplay = computed(() => `${formatNumber(syncLatencySeconds.value)}s`);

const growthInsights = computed(() =>
  insights.value.filter((insight) => (insight.pageTargets || []).includes("fans.growth")).slice(0, 3)
);

const todayNewFollowers = computed(() => Number(model.value?.newFollowers ?? latest.value?.newFollowers ?? 0));
const displayTrend = computed(() =>
  trend.value.map((item, index) => (
    index === trend.value.length - 1
      ? { ...item, newFollowers: todayNewFollowers.value, netFollowers: todayNetFollowers.value }
      : item
  ))
);
const trendMax = computed(() => Math.max(...displayTrend.value.map((item) => item.newFollowers), 1));
const totalLostFollowers = computed(() => displayTrend.value.reduce((value, item) => value + Number(item.lostFollowers || 0), 0));
const todayNetFollowers = computed(() => Math.max(0, todayNewFollowers.value - Number(latest.value?.lostFollowers || 0)));
const previousNewFollowers = computed(() => {
  const previous = trend.value[trend.value.length - 2];
  return Number(previous?.newFollowers || 0);
});
const newFollowersDelta = computed(() => todayNewFollowers.value - previousNewFollowers.value);
const topFollowerVideo = computed(() =>
  [...topVideos.value].sort((first, second) => Number(second.newFollowers || 0) - Number(first.newFollowers || 0))[0]
);
const topFollowerVideoTitle = computed(() => topFollowerVideo.value?.title || topFollowerVideo.value?.videoTitle || "最高转粉视频");
const topFollowerVideoFollowers = computed(() => Number(topFollowerVideo.value?.newFollowers || 0));
const coreAgeGroup = computed(() => topRecord(profile.value?.ageGroups || {})[0] || "--");
const coreAgeShare = computed(() => Number(topRecord(profile.value?.ageGroups || {})[1] || 0));
const profileLabelMap = {
  female: "女性",
  male: "男性",
  other: "其他",
  unknown: "未知",
  tutorial: "教程",
  review: "测评",
  seeding: "种草",
  vlog: "Vlog",
  live_clip: "直播切片",
  lifestyle: "生活方式",
  beauty: "美妆",
  office: "职场",
  student: "学生",
  commuter: "通勤",
  "18-24 女性新手用户": "年轻女性",
  "25-30 职场女性": "职场女性"
};
const labelForProfileKey = (key) => {
  if (!key) return "--";
  const raw = String(key).trim();
  const normalized = raw.toLowerCase();
  if (/^\d{1,2}$/.test(normalized)) return `${normalized}:00`;
  return profileLabelMap[raw] || profileLabelMap[normalized] || contentLabel(raw) || raw;
};
const audienceWordCloudItems = computed(() => {
  const items = [];
  const addRecord = (record, type, limit = 3) => {
    for (const [key, value] of Object.entries(record || {}).sort((a, b) => Number(b[1]) - Number(a[1])).slice(0, limit)) {
      items.push({ label: labelForProfileKey(key), value: Number(value || 0), type });
    }
  };

  addRecord(profile.value?.ageGroups, "age", 2);
  addRecord(profile.value?.gender, "gender", 2);
  addRecord(profile.value?.regions, "region", 2);
  addRecord(profile.value?.activeHours, "time", 2);

  for (const segment of (profile.value?.highValueSegments || []).slice(0, 2)) {
    items.push({ label: labelForProfileKey(segment.label), value: Number(segment.share || 0), type: "segment" });
    for (const contentType of (segment.preferredContentTypes || []).slice(0, 2)) {
      items.push({ label: labelForProfileKey(contentType), value: Number(segment.share || 0) * 0.82, type: "content" });
    }
  }

  const max = Math.max(...items.map((item) => item.value), 1);
  return items
    .filter((item) => item.label && item.label !== "--")
    .sort((a, b) => b.value - a.value)
    .slice(0, 12)
    .map((item, index) => ({
      ...item,
      size: Math.round(12 + (item.value / max) * 22),
      weight: index < 3 ? 900 : 800,
      tone: index % 4
    }));
});
const growthEvidence = computed(() =>
  `依据：今日新增 ${formatNumber(animatedNumber(todayNewFollowers.value))}，较昨日 ${newFollowersDelta.value >= 0 ? "+" : "-"}${formatNumber(Math.abs(animatedNumber(newFollowersDelta.value)))}，播放转粉率 ${formatPercent(animatedViewToFollowerRate.value)}`
);
const anomalyEvidence = computed(() =>
  `依据：掉粉 ${formatNumber(animatedNumber(latest.value?.lostFollowers))}，净增 ${formatNumber(animatedNumber(todayNetFollowers.value))}，粘性指数 ${formatNumber(Number(latest.value?.stickinessScore || 0) * radarAnimationProgress.value)}`
);
const nextStepEvidence = computed(() =>
  `依据：${coreAgeGroup.value} 占比 ${formatPercent(coreAgeShare.value * radarAnimationProgress.value)}，${topFollowerVideoTitle.value} 新增 ${formatNumber(animatedNumber(topFollowerVideoFollowers.value))} 粉`
);
const latestViewToFollowerScore = computed(() => Math.min(100, Math.round(Number(latest.value?.viewToFollowerRate || 0) * 1600)));
const latestGrowthSpeedScore = computed(() => Math.min(100, Math.round(todayNewFollowers.value / Math.max(trendMax.value, 1) * 100)));
const latestNetGrowthScore = computed(() => Math.min(100, Math.round(todayNetFollowers.value / Math.max(todayNewFollowers.value || 1, 1) * 100)));
const latestStickinessScore = computed(() => Math.min(100, Math.round(Number(latest.value?.stickinessScore || 0))));
const latestRetentionRiskScore = computed(() => Math.max(0, 100 - Math.min(100, Math.round(Number(latest.value?.lostFollowers || 0) / Math.max(todayNewFollowers.value || 1, 1) * 100))));
const growthJudgementRadarItems = computed(() => [
  { label: "增长速度", value: latestGrowthSpeedScore.value },
  { label: "转粉效率", value: latestViewToFollowerScore.value },
  { label: "净增稳定", value: latestNetGrowthScore.value },
  { label: "粘性质量", value: latestStickinessScore.value },
  { label: "风险控制", value: latestRetentionRiskScore.value }
]);
function radarPoint(index, value = 100, total = 5, radius = 70) {
  const angle = (-90 + (360 / total) * index) * Math.PI / 180;
  const distance = radius * (Number(value) / 100);
  return {
    x: 100 + Math.cos(angle) * distance,
    y: 100 + Math.sin(angle) * distance
  };
}
function smoothClosedPath(points) {
  if (!points.length) return "";
  const commands = [`M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`];
  for (let index = 0; index < points.length; index += 1) {
    const previous = points[(index - 1 + points.length) % points.length];
    const current = points[index];
    const next = points[(index + 1) % points.length];
    const afterNext = points[(index + 2) % points.length];
    const controlOne = {
      x: current.x + (next.x - previous.x) / 6,
      y: current.y + (next.y - previous.y) / 6
    };
    const controlTwo = {
      x: next.x - (afterNext.x - current.x) / 6,
      y: next.y - (afterNext.y - current.y) / 6
    };
    commands.push(`C ${controlOne.x.toFixed(2)} ${controlOne.y.toFixed(2)} ${controlTwo.x.toFixed(2)} ${controlTwo.y.toFixed(2)} ${next.x.toFixed(2)} ${next.y.toFixed(2)}`);
  }
  return `${commands.join(" ")} Z`;
}
const growthJudgementRadarAxes = computed(() =>
  growthJudgementRadarItems.value.map((item, index, items) => {
    const end = radarPoint(index, 100, items.length, 86);
    const labelPoint = radarPoint(index, 136, items.length);
    return { ...item, end, labelPoint };
  })
);
const growthJudgementRadarPath = computed(() =>
  smoothClosedPath(growthJudgementRadarItems.value.map((item, index, items) => radarPoint(index, item.value * radarAnimationProgress.value, items.length)))
);
const animatedNumber = (value) => Math.round(Number(value || 0) * radarAnimationProgress.value);
const animatedViewToFollowerRate = computed(() => Number(latest.value?.viewToFollowerRate || 0) * radarAnimationProgress.value);
const trendChartOption = computed(() => {
  const rows = displayTrend.value.map((item) => ({
    date: item.date?.slice(5) || "",
    newFollowers: Number(item.newFollowers || 0),
    netFollowers: Math.max(0, Number(item.netFollowers || 0))
  }));
  const maxValue = Math.max(...rows.flatMap((item) => [item.newFollowers, item.netFollowers]), 1);
  return {
    animationDuration: 1600,
    animationDurationUpdate: 1600,
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: "rgba(255,255,255,0.34)", width: 1 } },
      formatter(params) {
        const row = rows[params[0]?.dataIndex] || {};
        return `${row.date}<br/>新增粉丝 ${formatNumber(row.newFollowers)}<br/>净增粉丝 ${formatNumber(row.netFollowers)}`;
      }
    },
    grid: { left: 12, right: 16, top: 34, bottom: 30, containLabel: false },
    legend: {
      top: 0,
      right: 4,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: "rgba(255,255,255,0.72)", fontSize: 11, fontWeight: 800 },
      data: ["新增", "净增"]
    },
    xAxis: {
      type: "category",
      data: rows.map((item) => item.date),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: "rgba(255,255,255,0.66)", fontSize: 10, fontWeight: 800 }
    },
    yAxis: {
      type: "value",
      show: true,
      max: Math.ceil(maxValue * 1.2),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.08)", type: "dashed" } }
    },
    series: [
      {
        name: "新增",
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 10,
        lineStyle: { width: 5, color: "#ff89b1" },
        itemStyle: { color: "#ff89b1", borderColor: "#fff", borderWidth: 2 },
        label: {
          show: true,
          position: "top",
          color: "#fff",
          fontSize: 11,
          fontWeight: 850,
          formatter(params) {
            return Number(params.value || 0) > 0 ? `+${formatNumber(params.value)}` : "";
          }
        },
        data: rows.map((item) => item.newFollowers)
      },
      {
        name: "净增",
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 9,
        lineStyle: { width: 4, color: "#9a8eff" },
        itemStyle: { color: "#9a8eff", borderColor: "#fff", borderWidth: 2 },
        data: rows.map((item) => item.netFollowers)
      }
    ]
  };
});
const conversionPathRows = computed(() => [
  { key: "views", label: "播放", value: latest.value?.totalViews || 0, hint: "流量入口", connector: "× 转粉率" },
  { key: "followers", label: "新增关注", value: todayNewFollowers.value, hint: formatPercent(animatedViewToFollowerRate.value), connector: "- 掉粉" },
  { key: "lost", label: "掉粉", value: latest.value?.lostFollowers || 0, hint: "流失", connector: "=" },
  { key: "net", label: "净增", value: todayNetFollowers.value, hint: "最终增长" }
]);
const activeHoursHeatmapOption = computed(() =>
  heatmapOption(
    ["8", "10", "12", "14", "18", "20", "21"],
    ["活跃"],
    [[0, 0, 22], [1, 0, 32], [2, 0, 58], [3, 0, 36], [4, 0, 62], [5, 0, 94], [6, 0, 88]],
    { countUpLabels: true, labelSuffix: "", colors: ["rgba(255, 137, 177, 0.28)", "rgba(255, 137, 177, 0.68)", "#ff89b1"] }
  )
);

function topRecord(record) {
  if (!record) return ["--", 0];
  return Object.entries(record).sort((a, b) => Number(b[1]) - Number(a[1]))[0] || ["--", 0];
}
</script>

<template>
  <nav class="left-dock" aria-label="主导航">
    <button class="dock-item" type="button" aria-label="增长总览" @click="emit('navigate', 'growth')"><i class="fa-solid fa-house"></i></button>
    <button class="dock-item active" type="button" aria-label="粉丝分析" @click="emit('navigate', 'fans')"><i class="fa-solid fa-users"></i></button>
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
        <strong class="value">正在加载粉丝分析数据</strong>
      </section>

      <section v-else-if="error" class="card app-state-card">
        <p class="section-label">API Error</p>
        <strong class="value">{{ error }}</strong>
        <p class="page-copy">请先启动 Flask API：python api\\app.py</p>
      </section>

      <template v-else>
        <section class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Fan Growth System</p><h1>粉丝分析</h1></div>
            <p class="page-copy">从增长、转化、粘性和画像四个角度判断你的粉丝是否稳定增长，以及你的下一批内容应该服务哪类粉丝。</p>
          </section>

          <section class="diagnosis-strip">
            <article class="diagnosis-card strong">
              <span>增长判断</span>
              <strong>今日新增 {{ formatNumber(animatedNumber(todayNewFollowers)) }} 粉，{{ newFollowersDelta >= 0 ? "增长在提速" : "增长较昨日回落" }}</strong>
              <small>{{ growthEvidence }}</small>
            </article>
            <article class="diagnosis-card warning">
              <span>异常信号</span>
              <strong>{{ latest?.lostFollowers ? "掉粉需要跟进" : "暂未出现明显掉粉" }}，重点复盘低转粉流量</strong>
              <small>{{ anomalyEvidence }}</small>
            </article>
            <article class="diagnosis-card">
              <span>下一步重点</span>
              <strong>围绕高转粉内容做连续选题，把新粉接到系列内容里</strong>
              <small>{{ nextStepEvidence }}</small>
            </article>
          </section>

          <section class="grid-2">
            <article class="card">
              <p class="section-label">7 天新增/净增趋势</p>
              <ChartPanel class="chart-panel-tall" :option="trendChartOption" />
              <div class="grid-3" style="margin-top:18px">
                <span class="tag hot trend-new-followers-tag">新增 {{ formatNumber(todayNewFollowers) }}</span>
                <span class="tag purple">净增 {{ formatNumber(todayNetFollowers) }}</span>
                <span class="tag">掉粉 {{ formatNumber(totalLostFollowers) }}</span>
              </div>
            </article>
            <article class="card white">
              <p class="label" style="color:#666">粉丝转化路径</p>
              <strong class="value large">{{ formatPercent(animatedViewToFollowerRate) }}</strong>
              <span style="font-size:12px;color:#ff5e5e;font-weight:800">播放到关注</span>
              <div class="fan-conversion-path" aria-label="播放到关注的转化路径">
                <template v-for="row in conversionPathRows" :key="row.key">
                  <div
                    class="fan-conversion-step"
                    :class="`step-${row.key}`"
                    :style="{ '--step-progress': radarAnimationProgress }"
                  >
                    <span>{{ row.label }}</span>
                    <strong>{{ formatNumber(animatedNumber(row.value)) }}</strong>
                    <em>{{ row.hint }}</em>
                  </div>
                  <b v-if="row.connector" class="fan-conversion-connector">{{ row.connector }}</b>
                </template>
              </div>
              <p class="fan-conversion-formula">播放 × 转粉率 = 新增关注；新增关注 - 掉粉 = 净增</p>
            </article>
          </section>

          <section class="grid-3">
            <article class="card">
              <p class="section-label">增长判断</p>
              <div class="smooth-radar-chart" aria-label="增长判断雷达图">
                <svg viewBox="0 0 200 200" role="img">
                  <circle cx="100" cy="100" r="28" class="smooth-radar-ring"></circle>
                  <circle cx="100" cy="100" r="48" class="smooth-radar-ring"></circle>
                  <circle cx="100" cy="100" r="70" class="smooth-radar-ring strong"></circle>
                  <g v-for="axis in growthJudgementRadarAxes" :key="axis.label">
                    <line x1="100" y1="100" :x2="axis.end.x" :y2="axis.end.y" class="smooth-radar-axis"></line>
                    <text :x="axis.labelPoint.x" :y="axis.labelPoint.y" text-anchor="middle" dominant-baseline="middle">{{ axis.label }}</text>
                  </g>
                  <path :d="growthJudgementRadarPath" class="smooth-radar-area"></path>
                  <path :d="growthJudgementRadarPath" class="smooth-radar-edge"></path>
                </svg>
              </div>
              <div class="grid-3" style="margin-top:14px">
                <span class="tag hot">速度 {{ latestGrowthSpeedScore }}</span>
                <span class="tag purple">转粉 {{ latestViewToFollowerScore }}</span>
                <span class="tag">风险 {{ latestRetentionRiskScore }}</span>
              </div>
              <p class="page-copy growth-judgement-copy" style="margin-top:12px">{{ growthInsights[0]?.summary || "当前增长判断会综合新增、净增、播放转粉、粘性和掉粉风险。" }}</p>
            </article>
            <article class="card">
              <p class="section-label">粉丝画像</p>
              <div class="audience-word-cloud" aria-label="粉丝画像词云">
                <span
                  v-for="item in audienceWordCloudItems"
                  :key="`${item.type}-${item.label}`"
                  :class="`tone-${item.tone}`"
                  :style="{ fontSize: `${item.size}px`, fontWeight: item.weight }"
                >
                  {{ item.label }}
                </span>
              </div>
              <p class="page-copy" style="margin-top:12px">核心人群 {{ labelForProfileKey(topRecord(profile?.ageGroups)[0]) }}，占比 {{ formatPercent(topRecord(profile?.ageGroups)[1]) }}。</p>
            </article>
            <article class="card">
              <p class="section-label">活跃时间段</p>
              <strong class="value">{{ topRecord(profile?.activeHours)[0] }}:00</strong>
              <ChartPanel class="chart-panel-heat compact" :option="activeHoursHeatmapOption" />
            </article>
          </section>
        </section>

      </template>
    </div>
  </main>
</template>
