<script setup>
import { computed, nextTick, onMounted, ref } from "vue";
import ChartPanel from "../components/ChartPanel.vue";
import { fetchFansAnalysis } from "../services/api";
import { heatmapOption, horizontalBarOption, verticalBarOption } from "../utils/chartOptions";
import { formatNumber, formatPercent } from "../utils/format";
import { diagnosisItems } from "../utils/pageModels";

defineProps({
  activePage: {
    type: String,
    default: "fans"
  }
});

const emit = defineEmits(["navigate"]);

const activeTab = ref(window.location.hash?.replace("#", "") || "growth");
const loading = ref(true);
const error = ref("");
const payload = ref(null);

const tabs = [
  { id: "growth", label: "增长趋势" },
  { id: "source", label: "转化来源" },
  { id: "stickiness", label: "粘性行为" },
  { id: "profile", label: "粉丝画像" }
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
    payload.value = await fetchFansAnalysis();
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
    activeTab.value = "growth";
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
const trend = computed(() => model.value?.trend || []);
const latest = computed(() => trend.value[trend.value.length - 1]);
const profile = computed(() => model.value?.audienceProfile);
const insights = computed(() => model.value?.insights || []);

const insightByTab = computed(() => {
  const grouped = {
    growth: [],
    source: [],
    stickiness: [],
    profile: []
  };
  for (const insight of insights.value) {
    for (const target of insight.pageTargets || []) {
      if (target === "fans.growth") grouped.growth.push(insight);
      if (target === "fans.source") grouped.source.push(insight);
      if (target === "fans.stickiness") grouped.stickiness.push(insight);
      if (target === "fans.profile") grouped.profile.push(insight);
    }
  }
  return grouped;
});

const growthInsights = computed(() => insightByTab.value.growth.slice(0, 3));
const sourceInsights = computed(() => insightByTab.value.source.slice(0, 3));
const stickinessInsights = computed(() => insightByTab.value.stickiness.slice(0, 3));
const profileInsights = computed(() => insightByTab.value.profile.slice(0, 3));
const sourceDiagnosis = computed(() =>
  diagnosisItems(sourceInsights.value, [
    { label: "主来源", title: "高转粉教程贡献今日最强新粉入口", className: "strong" },
    { label: "浪费来源", title: "推荐流播放高，但转粉效率偏低", className: "warning" },
    { label: "可复刻视频", title: "收藏后关注路径最清晰的视频值得继续延展", className: "" }
  ])
);
const fanStickinessDiagnosis = computed(() =>
  diagnosisItems(stickinessInsights.value, [
    { label: "质量判断", title: "深度粉丝占比提升，教程系列正在形成复访", className: "strong" },
    { label: "关键行为", title: "收藏回看和评论提问是当前最强留存信号", className: "" },
    { label: "流失风险", title: "泛推荐新粉复访偏低，需要系列化承接", className: "warning" }
  ])
);
const profileDiagnosis = computed(() =>
  diagnosisItems(profileInsights.value, [
    { label: "核心人群", title: "年轻女性更偏好可保存的教程内容", className: "strong" },
    { label: "增长人群", title: "职场人群增长快，更关注测评和效率", className: "" },
    { label: "沉默人群", title: "低互动人群需要更明确的场景内容", className: "warning" }
  ])
);

const trendMax = computed(() => Math.max(...trend.value.map((item) => item.newFollowers), 1));
const coreSegments = computed(() => profile.value?.highValueSegments || []);
const totalTrendViews = computed(() => trend.value.reduce((value, item) => value + Number(item.totalViews || 0), 0));
const trendChartOption = computed(() =>
  verticalBarOption(
    trend.value.map((item) => ({
      label: item.date?.slice(5) || "",
      value: item.newFollowers,
      detail: `新增 ${formatNumber(item.newFollowers)}`
    })),
    { barWidth: 38 }
  )
);
const fanConversionPathOption = computed(() =>
  horizontalBarOption([
    { label: "播放", value: latest.value?.totalViews || 0, text: formatNumber(latest.value?.totalViews) },
    { label: "新粉", value: latest.value?.newFollowers || 0, text: formatNumber(latest.value?.newFollowers), color: "#9a8eff" },
    { label: "净增", value: latest.value?.netFollowers || 0, text: formatNumber(latest.value?.netFollowers), color: "#61f4ff" },
    { label: "掉粉", value: latest.value?.lostFollowers || 0, text: formatNumber(latest.value?.lostFollowers) }
  ])
);
const activeHoursHeatmapOption = computed(() =>
  heatmapOption(
    ["8", "10", "12", "14", "18", "20", "21"],
    ["活跃"],
    [[0, 0, 22], [1, 0, 32], [2, 0, 58], [3, 0, 36], [4, 0, 62], [5, 0, 94], [6, 0, 88]]
  )
);

function firstAction(insight) {
  return insight?.recommendedActions?.[0]?.description || "";
}

function topRecord(record) {
  if (!record) return ["--", 0];
  return Object.entries(record).sort((a, b) => Number(b[1]) - Number(a[1]))[0] || ["--", 0];
}
</script>

<template>
  <nav class="left-dock" aria-label="主导航">
    <button class="dock-item" type="button" aria-label="增长总览" @click="emit('navigate', 'growth')"><i class="fa-solid fa-house"></i></button>
    <button class="dock-item active" type="button" aria-label="粉丝分析" @click="emit('navigate', 'fans')"><i class="fa-solid fa-users"></i></button>
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
          <span class="sync-chip">10s Sync</span>
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
        <section v-show="activeTab === 'growth'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Fan Growth System</p><h1>粉丝分析</h1></div>
            <p class="page-copy">从增长、转化、粘性和画像四个角度判断你的粉丝是否稳定增长，以及你的下一批内容应该服务哪类粉丝。</p>
          </section>

          <section class="diagnosis-strip">
            <article class="diagnosis-card strong">
              <span>增长判断</span>
              <strong>你的粉丝增长正在加速，主要由高转粉教程和收藏行为带动</strong>
            </article>
            <article class="diagnosis-card warning">
              <span>异常信号</span>
              <strong>今日掉粉 {{ formatNumber(latest?.lostFollowers) }}，需要关注低转粉泛流量内容</strong>
            </article>
            <article class="diagnosis-card">
              <span>下一步重点</span>
              <strong>把新粉承接到教程系列，减少一次性浏览用户流失</strong>
            </article>
          </section>

          <section class="grid-6">
            <article class="metric-card"><p>总粉丝</p><strong>{{ formatNumber(latest?.totalFollowers) }}</strong></article>
            <article class="metric-card"><p>今日新增</p><strong>{{ formatNumber(latest?.newFollowers) }}</strong></article>
            <article class="metric-card"><p>今日掉粉</p><strong>{{ formatNumber(latest?.lostFollowers) }}</strong></article>
            <article class="metric-card"><p>净增粉丝</p><strong>{{ formatNumber(latest?.netFollowers) }}</strong></article>
            <article class="metric-card"><p>增长率</p><strong>{{ formatPercent(latest?.followerGrowthRate) }}</strong></article>
            <article class="metric-card"><p>播放转粉率</p><strong>{{ formatPercent(latest?.viewToFollowerRate) }}</strong></article>
          </section>

          <section class="grid-2">
            <article class="card">
              <p class="section-label">7 天新增粉丝</p>
              <ChartPanel class="chart-panel-tall" :option="trendChartOption" />
              <div class="grid-3" style="margin-top:18px">
                <span class="tag hot">新增 {{ formatNumber(latest?.newFollowers) }}</span>
                <span class="tag purple">净增 {{ formatNumber(latest?.netFollowers) }}</span>
                <span class="tag">播放 {{ formatNumber(totalTrendViews) }}</span>
              </div>
            </article>
            <article class="card white">
              <p class="label" style="color:#666">粉丝转化路径</p>
              <strong class="value large">{{ formatPercent(latest?.viewToFollowerRate) }}</strong>
              <span style="font-size:12px;color:#ff5e5e;font-weight:800">播放到关注</span>
              <ChartPanel class="chart-panel-funnel" :option="fanConversionPathOption" />
            </article>
          </section>

          <section class="grid-3">
            <article class="card">
              <p class="section-label">增长判断</p>
              <div class="action-list">
                <div v-for="item in growthInsights" :key="item.insightId">
                  <i class="fa-solid fa-chart-line"></i><span>{{ item.summary }}</span>
                </div>
              </div>
            </article>
            <article class="card">
              <p class="section-label">粉丝画像</p>
              <strong class="value">{{ topRecord(profile?.ageGroups)[0] }}</strong>
              <p class="page-copy" style="margin-top:12px">核心人群占比 {{ formatPercent(topRecord(profile?.ageGroups)[1]) }}，内容应优先服务当前高价值受众。</p>
              <div style="margin-top:14px"><span class="tag hot">{{ topRecord(profile?.regions)[0] }}</span> <span class="tag purple">{{ topRecord(profile?.gender)[0] }}</span></div>
            </article>
            <article class="card">
              <p class="section-label">活跃时间段</p>
              <strong class="value">{{ topRecord(profile?.activeHours)[0] }}:00</strong>
              <ChartPanel class="chart-panel-heat compact" :option="activeHoursHeatmapOption" />
            </article>
          </section>
        </section>

        <section v-show="activeTab === 'source'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">New Fan Attribution</p><h1>新粉来源归因台</h1></div>
            <p class="page-copy">把新粉来源拆成可复刻的视频和平台路径，避免只看播放量。</p>
          </section>

          <section class="diagnosis-strip">
            <article v-for="item in sourceDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span>
              <strong>{{ item.title }}</strong>
            </article>
          </section>

          <section class="grid-2">
            <article class="card">
              <p class="section-label">来源证据</p>
              <div class="insight-list">
                <div v-for="item in sourceInsights" :key="item.insightId" class="insight-item">
                  <div><strong>{{ item.title }}</strong><span>{{ item.summary }}</span></div>
                  <span class="tag hot">{{ item.priority }}</span>
                </div>
              </div>
            </article>
            <article class="card">
              <p class="section-label">下一步动作</p>
              <div class="action-list">
                <div v-for="item in sourceInsights" :key="item.insightId">
                  <i class="fa-solid fa-route"></i><span>{{ firstAction(item) }}</span>
                </div>
              </div>
            </article>
          </section>
        </section>

        <section v-show="activeTab === 'stickiness'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Retention Quality</p><h1>粉丝留存质量台</h1></div>
            <p class="page-copy">用收藏、评论和连续互动类 Insight 判断你的粉丝是否有质量。</p>
          </section>

          <section class="diagnosis-strip">
            <article v-for="item in fanStickinessDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span>
              <strong>{{ item.title }}</strong>
            </article>
          </section>

          <section class="grid-2">
            <article class="card">
              <p class="section-label">高粘性行为</p>
              <div class="insight-list">
                <div v-for="item in stickinessInsights" :key="item.insightId" class="insight-item">
                  <div><strong>{{ item.title }}</strong><span>{{ item.summary }}</span></div>
                  <span class="tag purple">{{ item.type }}</span>
                </div>
              </div>
            </article>
            <article class="card">
              <p class="section-label">提升动作</p>
              <div class="action-list">
                <div v-for="item in stickinessInsights.flatMap((insight) => insight.recommendedActions).slice(0, 3)" :key="item.actionId">
                  <i class="fa-solid fa-bookmark"></i><span>{{ item.description }}</span>
                </div>
              </div>
            </article>
          </section>
        </section>

        <section v-show="activeTab === 'profile'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Audience Strategy Map</p><h1>受众策略地图</h1></div>
            <p class="page-copy">把粉丝画像转成下一批内容应该服务的人群和时间窗口。</p>
          </section>

          <section class="diagnosis-strip">
            <article v-for="item in profileDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span>
              <strong>{{ item.title }}</strong>
            </article>
          </section>

          <section class="grid-3">
            <article class="card green">
              <p class="label" style="color:#111">核心人群</p>
              <strong class="value large">{{ topRecord(profile?.ageGroups)[0] }}</strong>
              <span style="font-size:12px;font-weight:800">{{ formatPercent(topRecord(profile?.ageGroups)[1]) }}</span>
            </article>
            <article class="card">
              <p class="section-label">主要地域</p>
              <strong class="value">{{ topRecord(profile?.regions)[0] }}</strong>
              <span class="delta">{{ formatPercent(topRecord(profile?.regions)[1]) }}</span>
            </article>
            <article class="card">
              <p class="section-label">最佳活跃窗口</p>
              <strong class="value">{{ topRecord(profile?.activeHours)[0] }}:00</strong>
              <span class="delta">粉丝活跃高峰</span>
            </article>
          </section>

          <section class="grid-2">
            <article class="card">
              <p class="section-label">高价值人群分层</p>
              <div class="insight-list">
                <div v-for="segment in coreSegments" :key="segment.segmentId" class="insight-item">
                  <div><strong>{{ segment.label }}</strong><span>偏好 {{ segment.preferredContentTypes.join(" / ") }}，活跃 {{ segment.preferredActiveHours.join(" / ") }} 点</span></div>
                  <span class="tag hot">{{ formatPercent(segment.share) }}</span>
                </div>
              </div>
            </article>
            <article class="card">
              <p class="section-label">内容方向建议</p>
              <div class="action-list">
                <div v-for="item in profileInsights.flatMap((insight) => insight.recommendedActions).slice(0, 3)" :key="item.actionId">
                  <i class="fa-solid fa-user-check"></i><span>{{ item.description }}</span>
                </div>
              </div>
            </article>
          </section>
        </section>
      </template>
    </div>
  </main>
</template>
