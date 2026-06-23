<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import ChartPanel from "../components/ChartPanel.vue";
import { fetchContentDistribution, fetchVideoAnalysis } from "../services/api";
import { contentLabel, formatNumber, formatPercent, platformLabel, sum } from "../utils/format";
import { aggregateBy, pairVideosWithSnapshots } from "../utils/pageModels";

defineProps({
  activePage: {
    type: String,
    default: "content"
  }
});

const emit = defineEmits(["navigate"]);

const loading = ref(true);
const error = ref("");
const payload = ref(null);
const videoPayload = ref(null);
const platformTableProgress = ref(0);
const platformTableSeedOrder = ref([]);
let platformTableAnimationFrame = 0;

onMounted(async () => {
  await loadData();
});

onBeforeUnmount(() => {
  if (platformTableAnimationFrame) window.cancelAnimationFrame(platformTableAnimationFrame);
});

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    const [contentData, videoData] = await Promise.all([fetchContentDistribution(), fetchVideoAnalysis()]);
    payload.value = contentData;
    videoPayload.value = videoData;
  } catch (apiError) {
    error.value = apiError.message;
  } finally {
    loading.value = false;
  }
}

const videoRows = computed(() => pairVideosWithSnapshots(videoPayload.value?.data?.videos || [], videoPayload.value?.data?.snapshots || []));
const syncLatencySeconds = computed(() => Number(payload.value?.data?.syncLatencySeconds ?? 0));
const syncLatencyDisplay = computed(() => `${formatNumber(syncLatencySeconds.value)}s`);
const sparkPlatformSummaries = computed(() =>
  (payload.value?.data?.sparkPlatformSummaries || []).map((row) => ({
    key: row.platform,
    views: row.totalViews,
    newFollowers: row.newFollowers,
    videoCount: row.videoCount,
    conversionRate: row.conversionRate
  }))
);
const totalViews = computed(() => sum(videoRows.value, "views"));
const totalFollowers = computed(() => sum(videoRows.value, "newFollowers"));
const totalVideos = computed(() => videoRows.value.length);

const platformRows = computed(() =>
  (sparkPlatformSummaries.value.length
    ? sparkPlatformSummaries.value
    : aggregateBy(videoRows.value, "platform", ["views", "newFollowers", "likes", "comments", "shares", "saves"])
  ).sort((a, b) => b.newFollowers - a.newFollowers)
);
const shuffleRows = (rows) =>
  [...rows]
    .map((row) => ({ row, sortValue: Math.random() }))
    .sort((a, b) => a.sortValue - b.sortValue)
    .map(({ row }) => row.key);

function startPlatformTableAnimation() {
  if (!platformRows.value.length) return;
  if (platformTableAnimationFrame) window.cancelAnimationFrame(platformTableAnimationFrame);
  platformTableSeedOrder.value = shuffleRows(platformRows.value);
  platformTableProgress.value = 0;
  const startedAt = performance.now();
  const duration = 1800;
  const tick = (time) => {
    const rawProgress = Math.min((time - startedAt) / duration, 1);
    platformTableProgress.value = 1 - Math.pow(1 - rawProgress, 3);
    if (rawProgress < 1) {
      platformTableAnimationFrame = window.requestAnimationFrame(tick);
    } else {
      platformTableProgress.value = 1;
      platformTableAnimationFrame = 0;
    }
  };
  platformTableAnimationFrame = window.requestAnimationFrame(tick);
}

watch(
  () => platformRows.value.map((row) => `${row.key}:${row.views}:${row.newFollowers}:${row.videoCount}`).join("|"),
  () => {
    nextTick(startPlatformTableAnimation);
  },
  { immediate: true }
);
const typeRows = computed(() =>
  aggregateBy(videoRows.value, "contentType", ["views", "newFollowers", "likes", "comments", "shares", "saves"]).sort((a, b) => b.newFollowers - a.newFollowers)
);
const timeRows = computed(() => {
  const rows = videoRows.value.map((video) => ({ ...video, hour: String(video.publishTime).slice(11, 13) }));
  return aggregateBy(rows, "hour", ["views", "newFollowers", "likes", "comments", "shares", "saves"]).sort((a, b) => b.newFollowers - a.newFollowers);
});
const ratio = (value, total) => (Number(total || 0) ? Number(value || 0) / Number(total || 0) : 0);
const animatedNumber = (value) => Number(value || 0) * platformTableProgress.value;
function platformDecision(row) {
  const viewShare = ratio(row.views, totalViews.value);
  const followerShare = ratio(row.newFollowers, totalFollowers.value);
  if (followerShare - viewShare > 0.006) return { label: "加码", className: "hot" };
  if (viewShare - followerShare > 0.006) return { label: "收敛", className: "warn" };
  return { label: "观察", className: "" };
}
const topPlatform = computed(() => platformRows.value[0] || {});
const highestViewPlatform = computed(() => [...platformRows.value].sort((a, b) => Number(b.views || 0) - Number(a.views || 0))[0] || {});
const topType = computed(() => typeRows.value[0] || {});
const inefficientPlatform = computed(() =>
  [...platformRows.value].sort((first, second) => {
    const firstGap = ratio(first.views, totalViews.value) - ratio(first.newFollowers, totalFollowers.value);
    const secondGap = ratio(second.views, totalViews.value) - ratio(second.newFollowers, totalFollowers.value);
    return secondGap - firstGap;
  })[0] || {}
);
const platformDiagnosisCards = computed(() => {
  const bestPlatformName = platformLabel(topPlatform.value.key) || "最佳平台";
  const weakPlatformName = platformLabel(inefficientPlatform.value.key) || "低效平台";
  const typeName = contentLabel(topType.value.key) || "高转粉类型";
  return [
    {
      label: "结构判断",
      className: "strong",
      title: `${bestPlatformName}不是靠数量取胜，而是转粉效率最高`,
      detail: `发布占比 ${formatPercent(ratio(topPlatform.value.videoCount, totalVideos.value))}，涨粉贡献 ${formatPercent(ratio(topPlatform.value.newFollowers, totalFollowers.value))}，转粉率 ${formatPercent(ratio(topPlatform.value.newFollowers, topPlatform.value.views))}。下周优先把高转粉选题发到这里。`
    },
    {
      label: "类型机会",
      className: "",
      title: `${typeName}更适合承接新粉，不只是拿播放量`,
      detail: `播放贡献 ${formatPercent(ratio(topType.value.views, totalViews.value))}，涨粉贡献 ${formatPercent(ratio(topType.value.newFollowers, totalFollowers.value))}。建议把封面和开头都围绕“可保存步骤/结果预览”做。`
    },
    {
      label: "投入偏差",
      className: "warning",
      title: `${weakPlatformName}流量占比高，但涨粉承接偏弱`,
      detail: `播放贡献 ${formatPercent(ratio(inefficientPlatform.value.views, totalViews.value))}，涨粉贡献 ${formatPercent(ratio(inefficientPlatform.value.newFollowers, totalFollowers.value))}。下周减少泛流量内容，补关注理由和主页 CTA。`
    }
  ];
});
const platformSummaryCards = computed(() => [
  {
    label: "最佳平台",
    badge: "加码",
    tone: "is-primary",
    value: platformLabel(topPlatform.value.key) || "-",
    detail: `转粉率 ${formatPercent(ratio(topPlatform.value.newFollowers, topPlatform.value.views))} · 涨粉贡献 ${formatPercent(ratio(topPlatform.value.newFollowers, totalFollowers.value))}`
  },
  {
    label: "最高播放平台",
    badge: "对照",
    tone: "is-cool",
    value: platformLabel(highestViewPlatform.value.key) || "-",
    detail: `播放贡献 ${formatPercent(ratio(highestViewPlatform.value.views, totalViews.value))} · 涨粉贡献 ${formatPercent(ratio(highestViewPlatform.value.newFollowers, totalFollowers.value))}`
  },
  {
    label: "低效平台",
    badge: "收敛",
    tone: "is-warn",
    value: platformLabel(inefficientPlatform.value.key) || "-",
    detail: `播放贡献 ${formatPercent(ratio(inefficientPlatform.value.views, totalViews.value))} · 涨粉贡献 ${formatPercent(ratio(inefficientPlatform.value.newFollowers, totalFollowers.value))}`
  },
  {
    label: "样本视频数",
    badge: "样本",
    tone: "is-neutral",
    value: `${formatNumber(totalVideos.value)} 条`,
    detail: `本页按 ${platformRows.value.length} 个平台聚合，用来判断投入结构`
  }
]);
const animatedPlatformRows = computed(() => {
  const finalRows = [...platformRows.value].sort((a, b) => Number(b.views || 0) - Number(a.views || 0));
  const seedIndex = new Map(platformTableSeedOrder.value.map((key, index) => [key, index]));
  const finalIndex = new Map(finalRows.map((row, index) => [row.key, index]));
  const sortProgress = Math.max(0, (platformTableProgress.value - 0.4) / 0.6);

  return [...platformRows.value]
    .map((row, currentIndex) => {
      const startIndex = seedIndex.has(row.key) ? seedIndex.get(row.key) : currentIndex;
      const targetIndex = finalIndex.has(row.key) ? finalIndex.get(row.key) : currentIndex;
      return {
        ...row,
        sortScore: startIndex + (targetIndex - startIndex) * sortProgress
      };
    })
    .sort((a, b) => a.sortScore - b.sortScore);
});
const platformContributionQuadrantOption = computed(() => {
  const points = platformRows.value.map((row) => ({
    label: platformLabel(row.key),
    viewShare: ratio(row.views, totalViews.value),
    followerShare: ratio(row.newFollowers, totalFollowers.value),
    publishShare: ratio(row.videoCount, totalVideos.value),
    decision: platformDecision(row)
  }));
  const maxShare = Math.max(
    0.01,
    ...points.flatMap((point) => [point.viewShare, point.followerShare])
  ) * 1.18;
  const axisMax = Math.min(1, maxShare);
  return {
    animationDuration: 1700,
    animationDurationUpdate: 1700,
    tooltip: {
      formatter(params) {
        const item = params.data;
        return `${item.name}<br/>播放贡献 ${formatPercent(item.value[0])}<br/>涨粉贡献 ${formatPercent(item.value[1])}<br/>发布投入 ${formatPercent(item.value[2])}`;
      }
    },
    grid: { left: 48, right: 22, top: 28, bottom: 42 },
    xAxis: {
      type: "value",
      min: 0,
      max: axisMax,
      name: "播放贡献",
      nameLocation: "middle",
      nameGap: 28,
      axisLabel: { color: "#111111", formatter: (value) => formatPercent(value) },
      axisLine: { lineStyle: { color: "rgba(17,17,17,0.32)" } },
      splitLine: { lineStyle: { color: "rgba(17,17,17,0.1)" } }
    },
    yAxis: {
      type: "value",
      min: 0,
      max: axisMax,
      name: "涨粉贡献",
      nameGap: 18,
      axisLabel: { color: "#111111", formatter: (value) => formatPercent(value) },
      axisLine: { lineStyle: { color: "rgba(17,17,17,0.32)" } },
      splitLine: { lineStyle: { color: "rgba(17,17,17,0.1)" } }
    },
    series: [
      {
        name: "贡献均衡线",
        type: "line",
        countUpDimension: "all",
        symbol: "none",
        silent: true,
        data: [[0, 0], [axisMax, axisMax]],
        lineStyle: { color: "rgba(17,17,17,0.28)", type: "dashed", width: 2 }
      },
      {
        name: "平台贡献",
        type: "scatter",
        countUpDimension: "all",
        symbolSize(value) {
          return Math.max(18, Math.min(44, 18 + Number(value[2] || 0) * 420));
        },
        itemStyle: {
          color(params) {
            const decision = params.data?.decision?.label;
            if (decision === "加码") return "#c7ff00";
            if (decision === "收敛") return "#ff89b1";
            return "#8fd3ff";
          },
          borderColor: "#111111",
          borderWidth: 1.5,
          opacity: 0.92
        },
        label: {
          show: true,
          position: "top",
          color: "#111111",
          fontSize: 11,
          fontWeight: 900,
          formatter(params) {
            return params.data?.name || "";
          }
        },
        data: points.map((point) => ({
          name: point.label,
          value: [point.viewShare, point.followerShare, point.publishShare],
          decision: point.decision
        }))
      }
    ]
  };
});
</script>

<template>
  <nav class="left-dock" aria-label="主导航">
    <button class="dock-item" type="button" aria-label="增长总览" @click="emit('navigate', 'growth')"><i class="fa-solid fa-house"></i></button>
    <button class="dock-item" type="button" aria-label="粉丝分析" @click="emit('navigate', 'fans')"><i class="fa-solid fa-users"></i></button>
    <button class="dock-item active" type="button" aria-label="内容分布" @click="emit('navigate', 'content')"><i class="fa-solid fa-chart-pie"></i></button>
    <button class="dock-item" type="button" aria-label="机会建议" @click="emit('navigate', 'opportunities')"><i class="fa-solid fa-fire"></i></button>
    <button class="dock-item" type="button" aria-label="个人中心" @click="emit('navigate', 'profile')"><i class="fa-solid fa-gear"></i></button>
  </nav>

  <main class="glass-board">
    <div class="dashboard-content">
      <header class="board-header">
        <div class="brand-logo"><i class="fa-solid fa-circle-notch"></i> CreatorPulse</div>
        <div class="user-profile"><span class="sync-chip">{{ syncLatencyDisplay }} Sync</span><i class="fa-regular fa-bell" style="color:var(--text-dim)"></i><div class="user-avatar"></div></div>
      </header>

      <section v-if="loading" class="card app-state-card"><p class="section-label">Loading</p><strong class="value">正在加载内容分布数据</strong></section>
      <section v-else-if="error" class="card app-state-card"><p class="section-label">API Error</p><strong class="value">{{ error }}</strong><p class="page-copy">请先启动 Flask API：python api\\app.py</p></section>

      <template v-else>
        <section class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Content Allocation</p><h1>内容分布</h1></div>
            <p class="page-copy">判断你的内容发在哪里、发什么类型、什么时候发是否合理，用分布效率指导下一轮平台和内容投入。</p>
          </section>
          <section class="diagnosis-strip">
            <article
              v-for="item in platformDiagnosisCards"
              :key="item.label"
              class="diagnosis-card"
              :class="item.className"
            >
              <span>{{ item.label }}</span>
              <strong>{{ item.title }}</strong>
              <small>{{ item.detail }}</small>
            </article>
          </section>
          <section class="grid-4">
            <article
              v-for="item in platformSummaryCards"
              :key="item.label"
              class="metric-card platform-summary-card"
              :class="item.tone"
            >
              <div class="platform-summary-card__top">
                <p>{{ item.label }}</p>
                <span>{{ item.badge }}</span>
              </div>
              <strong>{{ item.value }}</strong>
              <small>{{ item.detail }}</small>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">平台投入回报表</p>
              <div class="table-scroll">
                <table class="table animated-platform-table">
                  <tr><th>平台</th><th>判断</th><th>发布投入</th><th>播放贡献</th><th>涨粉贡献</th><th>转粉率</th></tr>
                  <tr
                    v-for="row in animatedPlatformRows"
                    :key="row.key"
                    :style="{ '--row-progress': platformTableProgress }"
                  >
                    <td>{{ platformLabel(row.key) }}</td>
                    <td><span class="tag" :class="platformDecision(row).className">{{ platformDecision(row).label }}</span></td>
                    <td>{{ formatPercent(ratio(animatedNumber(row.videoCount), totalVideos)) }}</td>
                    <td>{{ formatPercent(ratio(animatedNumber(row.views), totalViews)) }}</td>
                    <td>{{ formatPercent(ratio(animatedNumber(row.newFollowers), totalFollowers)) }}</td>
                    <td>{{ formatPercent(ratio(animatedNumber(row.newFollowers), animatedNumber(row.views))) }}</td>
                  </tr>
                </table>
              </div>
            </article>
            <article class="card green platform-best-card contribution-quadrant-card">
              <p class="label" style="color:#111">平台贡献象限</p>
              <strong class="value">看谁有流量，也能转粉</strong>
              <span style="font-size:12px;font-weight:800">线以上加码，线以下收敛；气泡越大代表发布投入越高</span>
              <ChartPanel class="chart-panel-quadrant" :option="platformContributionQuadrantOption" />
            </article>
          </section>
          <section class="grid-3">
            <article class="card">
              <p class="section-label">内容类型倾向</p>
              <strong class="value">{{ contentLabel(typeRows[0]?.key) }}</strong>
              <span class="delta">涨粉 {{ formatNumber(typeRows[0]?.newFollowers) }}</span>
            </article>
            <article class="card">
              <p class="section-label">最佳发布时间</p>
              <strong class="value">{{ timeRows[0]?.key }}:00</strong>
              <span class="delta">转粉 {{ formatPercent(timeRows[0]?.newFollowers / timeRows[0]?.views) }}</span>
            </article>
            <article class="card">
              <p class="section-label">下周结构判断</p>
              <p class="page-copy">优先把高转粉平台、教程/测评内容和晚间窗口组合起来，减少低转粉泛流量内容投入。</p>
            </article>
          </section>
        </section>
      </template>
    </div>
  </main>
</template>
