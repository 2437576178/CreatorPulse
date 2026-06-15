<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchGrowthDashboard } from "../services/api";
import { contentLabel, formatNumber, formatPercent, priorityClass, sum } from "../utils/format";

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
  try {
    payload.value = await fetchGrowthDashboard();
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
    activeTab.value = "overview";
  }
}

function setTab(tabId) {
  activeTab.value = tabId;
  window.location.hash = tabId;
}

const creator = computed(() => payload.value?.creator);
const model = computed(() => payload.value?.data);
const snapshot = computed(() => model.value?.currentSnapshot);
const topVideos = computed(() => model.value?.topVideos || []);
const insights = computed(() => model.value?.insights || []);

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

const totalViews = computed(() => sum(topVideos.value, "views"));
const totalFollowers = computed(() => sum(topVideos.value, "newFollowers"));
const totalProfiles = computed(() => sum(topVideos.value, "profileVisits"));
const totalInteractions = computed(() =>
  topVideos.value.reduce((value, video) => value + video.likes + video.comments + video.shares + video.saves, 0)
);

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

function takeInsights(tab) {
  const items = insightByTab.value[tab] || [];
  return items.slice(0, 3);
}

</script>

<template>
  <nav class="left-dock" aria-label="主导航">
    <button class="dock-item active" type="button" aria-label="增长总览" @click="emit('navigate', 'growth')"><i class="fa-solid fa-house"></i></button>
    <button class="dock-item" type="button" aria-label="粉丝分析" @click="emit('navigate', 'fans')"><i class="fa-solid fa-users"></i></button>
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
              <p class="page-copy">
                {{ creator?.displayName }} 当前由统一 mock API 驱动，健康度、转粉和粘性都来自同一批数据。
              </p>

              <div class="huge-circle" aria-label="账号增长健康度">
                <svg viewBox="0 0 36 36" style="width:100%;height:100%;transform:rotate(-90deg)">
                  <circle cx="18" cy="18" r="14" fill="none" stroke="rgba(255,255,255,0.07)" stroke-width="3.6"/>
                  <circle cx="18" cy="18" r="14" fill="none" stroke="var(--neon-green)" stroke-width="3.6" :stroke-dasharray="`${snapshot?.growthHealthScore || 0} 100`"/>
                  <circle cx="18" cy="18" r="10.2" fill="none" stroke="var(--neon-purple)" stroke-width="1.7" :stroke-dasharray="`${snapshot?.stickinessScore || 0} 100`"/>
                </svg>
                <div class="circle-copy">
                  <strong>{{ Math.round(snapshot?.growthHealthScore || 0) }}</strong>
                  <span>账号增长健康度</span>
                  <span style="color:var(--neon-green);font-weight:800">粘性 {{ snapshot?.stickinessScore }}</span>
                </div>
              </div>

              <div class="grid-3">
                <div class="metric-card"><p>今日新粉</p><strong>{{ formatNumber(snapshot?.newFollowers) }}</strong><span class="delta">净增 {{ formatNumber(snapshot?.netFollowers) }}</span></div>
                <div class="metric-card"><p>播放转粉率</p><strong>{{ formatPercent(snapshot?.viewToFollowerRate) }}</strong><span class="delta">API 计算</span></div>
                <div class="metric-card"><p>粘性指数</p><strong>{{ snapshot?.stickinessScore }}</strong><span class="delta">高价值互动</span></div>
              </div>
            </div>

            <div style="display:flex;flex-direction:column;gap:22px">
              <section class="diagnosis-strip">
                <article v-for="item in overviewInsights" :key="item.insightId" class="diagnosis-card" :class="priorityClass(item.priority)">
                  <span>{{ item.type }}</span>
                  <strong>{{ item.title }}</strong>
                </article>
              </section>

              <div class="grid-2">
                <article class="card white">
                  <p class="label" style="color:#666">粉丝转化漏斗</p>
                  <strong class="value large">{{ formatNumber(totalFollowers) }}</strong>
                  <span style="font-size:12px;color:#ff5e5e;font-weight:800">主页访问到关注 {{ formatPercent(totalFollowers / totalProfiles) }}</span>
                  <div class="bar-stack" style="margin-top:18px">
                    <div class="bar"><span style="width:100%">播放 {{ formatNumber(totalViews) }}</span></div>
                    <div class="bar purple"><span style="width:62%">互动 {{ formatNumber(totalInteractions) }}</span></div>
                    <div class="bar cyan"><span style="width:38%">主页访问 {{ formatNumber(totalProfiles) }}</span></div>
                    <div class="bar"><span style="width:18%">新增关注 {{ formatNumber(totalFollowers) }}</span></div>
                  </div>
                </article>
                <article class="card purple">
                  <p class="label" style="color:#111">最新视频涨粉表现</p>
                  <strong class="value large">+{{ formatNumber(topVideos[0]?.newFollowers) }}</strong>
                  <span style="font-size:12px;color:#fff;font-weight:800">{{ topVideos[0]?.title }}</span>
                </article>
              </div>
            </div>
          </section>
        </section>

        <section v-show="activeTab === 'conversion'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Conversion Diagnosis</p><h1>转化诊断台</h1></div>
            <p class="page-copy">从 API 返回的 Insight 和视频快照里追踪播放、主页访问和新增关注。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in conversionInsights" :key="item.insightId" class="diagnosis-card" :class="priorityClass(item.priority)">
              <span>{{ item.scope }}</span>
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
            <article v-for="item in stickinessInsights" :key="item.insightId" class="diagnosis-card" :class="priorityClass(item.priority)">
              <span>{{ item.scope }}</span>
              <strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">粘性趋势拆解</p>
              <div class="bar-stack">
                <div class="bar"><span style="width:82%">收藏 {{ formatNumber(sum(topVideos, 'saves')) }}</span></div>
                <div class="bar purple"><span style="width:68%">评论 {{ formatNumber(sum(topVideos, 'comments')) }}</span></div>
                <div class="bar cyan"><span style="width:58%">分享 {{ formatNumber(sum(topVideos, 'shares')) }}</span></div>
                <div class="bar"><span style="width:42%">新增关注 {{ formatNumber(totalFollowers) }}</span></div>
              </div>
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
            <p class="page-copy">用 API 聚合出的 Top 视频，快速判断哪些内容类型最值得继续投入。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in distributionInsights" :key="item.insightId" class="diagnosis-card" :class="priorityClass(item.priority)">
              <span>{{ item.scope }}</span>
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
