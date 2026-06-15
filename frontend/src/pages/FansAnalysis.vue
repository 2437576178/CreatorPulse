<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchFansAnalysis } from "../services/api";
import { formatNumber, formatPercent, priorityClass } from "../utils/format";

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
  try {
    payload.value = await fetchFansAnalysis();
  } catch (apiError) {
    error.value = apiError.message;
  } finally {
    loading.value = false;
  }
});

function syncHash() {
  const next = window.location.hash.replace("#", "");
  if (tabs.some((tab) => tab.id === next)) {
    activeTab.value = next;
  } else {
    activeTab.value = "growth";
  }
}

function setTab(tabId) {
  activeTab.value = tabId;
  window.location.hash = tabId;
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

const trendMax = computed(() => Math.max(...trend.value.map((item) => item.newFollowers), 1));
const coreSegments = computed(() => profile.value?.highValueSegments || []);

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
    <button class="dock-item" type="button" aria-label="视频分析"><i class="fa-solid fa-play"></i></button>
    <button class="dock-item" type="button" aria-label="内容分布"><i class="fa-solid fa-chart-pie"></i></button>
    <button class="dock-item" type="button" aria-label="机会建议"><i class="fa-solid fa-fire"></i></button>
    <button class="dock-item" type="button" aria-label="个人中心"><i class="fa-solid fa-gear"></i></button>
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
          <span class="sync-chip">API Sync</span>
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
            <div><p class="eyebrow">Fan Growth Overview</p><h1>粉丝增长趋势</h1></div>
            <p class="page-copy">{{ creator?.displayName }} 的粉丝趋势来自 7 天账号快照，用于判断增长是否加速、异常或放缓。</p>
          </section>

          <section class="diagnosis-strip">
            <article v-for="item in growthInsights" :key="item.insightId" class="diagnosis-card" :class="priorityClass(item.priority)">
              <span>{{ item.scope }}</span>
              <strong>{{ item.title }}</strong>
            </article>
          </section>

          <section class="grid-4">
            <article class="metric-card"><p>总粉丝</p><strong>{{ formatNumber(latest?.totalFollowers) }}</strong></article>
            <article class="metric-card"><p>今日新增</p><strong>{{ formatNumber(latest?.newFollowers) }}</strong></article>
            <article class="metric-card"><p>今日掉粉</p><strong>{{ formatNumber(latest?.lostFollowers) }}</strong></article>
            <article class="metric-card"><p>播放转粉率</p><strong>{{ formatPercent(latest?.viewToFollowerRate) }}</strong></article>
          </section>

          <section class="grid-2">
            <article class="card">
              <p class="section-label">7 天新增粉丝</p>
              <div class="bar-stack">
                <div v-for="item in trend" :key="item.snapshotId" class="bar">
                  <span :style="{ width: `${Math.max(12, item.newFollowers / trendMax * 100)}%` }">{{ item.date.slice(5) }} {{ formatNumber(item.newFollowers) }}</span>
                </div>
              </div>
            </article>
            <article class="card">
              <p class="section-label">增长判断</p>
              <div class="action-list">
                <div v-for="item in growthInsights" :key="item.insightId">
                  <i class="fa-solid fa-chart-line"></i><span>{{ item.summary }}</span>
                </div>
              </div>
            </article>
          </section>
        </section>

        <section v-show="activeTab === 'source'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">New Fan Attribution</p><h1>新粉来源归因台</h1></div>
            <p class="page-copy">把新粉来源拆成可复刻的视频和平台路径，避免只看播放量。</p>
          </section>

          <section class="diagnosis-strip">
            <article v-for="item in sourceInsights" :key="item.insightId" class="diagnosis-card" :class="priorityClass(item.priority)">
              <span>{{ item.scope }}</span>
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
            <article v-for="item in stickinessInsights" :key="item.insightId" class="diagnosis-card" :class="priorityClass(item.priority)">
              <span>{{ item.scope }}</span>
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
            <article v-for="item in profileInsights" :key="item.insightId" class="diagnosis-card" :class="priorityClass(item.priority)">
              <span>{{ item.scope }}</span>
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
