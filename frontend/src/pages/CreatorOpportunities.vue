<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchOpportunities } from "../services/api";
import { formatPercent } from "../utils/format";
import { actionsFrom, diagnosisItems, groupInsights, topRows } from "../utils/pageModels";

defineProps({
  activePage: {
    type: String,
    default: "opportunities"
  }
});

const emit = defineEmits(["navigate"]);

const tabs = [
  { id: "hot", label: "热点机会" },
  { id: "advice", label: "创作建议" },
  { id: "reference", label: "参考洞察" }
];

const activeTab = ref(window.location.hash?.replace("#", "") || "hot");
const loading = ref(true);
const error = ref("");
const payload = ref(null);

onMounted(async () => {
  window.addEventListener("hashchange", syncHash);
  syncHash();
  await loadData();
});

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    payload.value = await fetchOpportunities();
  } catch (apiError) {
    error.value = apiError.message;
  } finally {
    loading.value = false;
  }
}

function syncHash() {
  const next = window.location.hash.replace("#", "");
  activeTab.value = tabs.some((tab) => tab.id === next) ? next : "hot";
}

function setTab(tabId) {
  activeTab.value = tabId;
  window.location.hash = tabId;
}

const model = computed(() => payload.value?.data);
const topics = computed(() => model.value?.topics || []);
const insights = computed(() => model.value?.insights || []);
const insightByTab = computed(() => groupInsights(insights.value, tabs, "opportunities"));
const hotTopics = computed(() => topRows(topics.value, "creatorFitScore", 6));
const bestTopic = computed(() => hotTopics.value[0]);
const adviceDiagnosis = computed(() =>
  diagnosisItems(tabInsights("advice"), [
    { label: "推荐选题", title: `${bestTopic.value?.topicName || "下一条教程内容"}适合作为下一条内容，适配度 ${bestTopic.value?.creatorFitScore || 91}`, className: "strong" },
    { label: "注意事项", title: "不要做泛种草标题，必须明确新手和通勤场景", className: "warning" },
    { label: "预期收益", title: "预计播放转粉率和收藏率会高于泛流量内容" }
  ])
);
const referenceDiagnosis = computed(() =>
  diagnosisItems(tabInsights("reference"), [
    { label: "最强结构", title: "前 8 秒结果预览能显著提高完播和关注", className: "strong" },
    { label: "避免误用", title: "不要照搬人设，只借鉴转粉结构和节奏", className: "warning" },
    { label: "可迁移动作", title: "标题、封面、结尾 CTA 都可复用到下一条内容" }
  ])
);

function tabInsights(tabId) {
  return (insightByTab.value[tabId] || []).slice(0, 3);
}
</script>

<template>
  <nav class="left-dock" aria-label="主导航">
    <button class="dock-item" type="button" aria-label="增长总览" @click="emit('navigate', 'growth')"><i class="fa-solid fa-house"></i></button>
    <button class="dock-item" type="button" aria-label="粉丝分析" @click="emit('navigate', 'fans')"><i class="fa-solid fa-users"></i></button>
    <button class="dock-item" type="button" aria-label="视频分析" @click="emit('navigate', 'video')"><i class="fa-solid fa-play"></i></button>
    <button class="dock-item" type="button" aria-label="内容分布" @click="emit('navigate', 'content')"><i class="fa-solid fa-chart-pie"></i></button>
    <button class="dock-item active" type="button" aria-label="机会建议" @click="emit('navigate', 'opportunities')"><i class="fa-solid fa-fire"></i></button>
    <button class="dock-item" type="button" aria-label="个人中心" @click="emit('navigate', 'profile')"><i class="fa-solid fa-gear"></i></button>
  </nav>

  <main class="glass-board">
    <div class="dashboard-content">
      <header class="board-header">
        <div class="brand-logo"><i class="fa-solid fa-circle-notch"></i> CreatorPulse</div>
        <div class="top-pills-tabs" role="tablist">
          <button v-for="tab in tabs" :key="tab.id" class="top-pill" :class="{ active: activeTab === tab.id }" type="button" role="tab" :aria-selected="activeTab === tab.id" @click="setTab(tab.id)">
            {{ tab.label }}
          </button>
        </div>
        <div class="user-profile"><span class="sync-chip">60s Sync</span><i class="fa-regular fa-bell" style="color:var(--text-dim)"></i><div class="user-avatar"></div></div>
      </header>

      <section v-if="loading" class="card app-state-card"><p class="section-label">Loading</p><strong class="value">正在加载机会建议数据</strong></section>
      <section v-else-if="error" class="card app-state-card"><p class="section-label">API Error</p><strong class="value">{{ error }}</strong><p class="page-copy">请先启动 Flask API：python api\\app.py</p></section>

      <template v-else>
        <section v-show="activeTab === 'hot'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Opportunity Radar</p><h1>机会建议</h1></div>
            <p class="page-copy">从热点、粉丝偏好和历史高转粉结构里找到你的下一条内容机会，避免只追热度不转粉。</p>
          </section>
          <section class="diagnosis-strip">
            <article class="diagnosis-card strong">
              <span>最佳机会</span><strong>{{ bestTopic?.topicName }}适合作为下一条内容选题</strong>
            </article>
            <article class="diagnosis-card warning">
              <span>注意风险</span><strong>热点只做流量入口，标题必须明确人群和关注理由</strong>
            </article>
            <article class="diagnosis-card">
              <span>复刻结构</span><strong>结果预览 + 步骤拆解 + 收藏引导仍是最稳结构</strong>
            </article>
          </section>
          <section class="grid-3">
            <article class="card green"><p class="label" style="color:#111">最佳机会</p><strong class="value large">{{ bestTopic?.topicName }}</strong><span style="font-size:12px;font-weight:800">适配度 {{ bestTopic?.creatorFitScore }}</span></article>
            <article class="card"><p class="section-label">最高热度</p><strong class="value">{{ hotTopics[0]?.heatScore }}</strong><span class="delta">话题雷达</span></article>
            <article class="card"><p class="section-label">风险等级</p><strong class="value">{{ bestTopic?.riskLevel }}</strong><span class="delta">MVP 规则</span></article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">机会雷达</p>
              <div class="radar-cloud">
                <div
                  v-for="topic in hotTopics"
                  :key="topic.topicId"
                  class="bubble"
                  :class="{ hot: topic.topicId === bestTopic?.topicId, purple: topic.creatorFitScore >= 85 && topic.topicId !== bestTopic?.topicId }"
                  :style="{ '--s': `${Math.max(72, Math.min(132, topic.creatorFitScore + 28))}px` }"
                >
                  {{ topic.topicName }}
                </div>
              </div>
            </article>
            <article class="card">
              <p class="section-label">热点话题</p>
              <table class="table">
                <tr><th>话题</th><th>热度</th><th>适配</th><th>增长</th></tr>
                <tr v-for="topic in hotTopics" :key="topic.topicId">
                  <td>{{ topic.topicName }}</td><td>{{ topic.heatScore }}</td><td>{{ topic.creatorFitScore }}</td><td>{{ formatPercent(topic.growthRate) }}</td>
                </tr>
              </table>
            </article>
          </section>
        </section>

        <section v-show="activeTab === 'advice'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Next Content Generator</p><h1>下一条内容生成台</h1></div>
            <p class="page-copy">把选题、脚本结构、标题封面、发布时间和平台策略拆成可执行动作。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in adviceDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span><strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">脚本结构</p>
              <div class="bar-stack">
                <div class="bar"><span style="width:100%">0-8s：结果预览 + 痛点开场</span></div>
                <div class="bar purple"><span style="width:100%">8-90s：三步完成底妆和眼妆</span></div>
                <div class="bar cyan"><span style="width:100%">90-160s：常见错误和修正</span></div>
                <div class="bar"><span style="width:100%">结尾：收藏引导 + 下一集预告</span></div>
              </div>
            </article>
            <article class="card">
              <p class="section-label">执行清单</p>
              <div class="action-list">
                <div v-for="item in actionsFrom(tabInsights('advice'), 5)" :key="item.actionId"><i class="fa-solid fa-wand-magic-sparkles"></i><span>{{ item.description }}</span></div>
                <div v-if="!actionsFrom(tabInsights('advice'), 1).length"><i class="fa-solid fa-clock"></i><span>周五 20:00 B站首发完整版，小红书同步封面图文。</span></div>
              </div>
            </article>
          </section>
        </section>

        <section v-show="activeTab === 'reference'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">High Conversion Pattern</p><h1>高转粉结构拆解</h1></div>
            <p class="page-copy">只提取可复用内容结构，不做复杂竞品管理。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in referenceDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span><strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">结构拆解</p>
              <table class="table">
                <tr><th>参考内容特征</th><th>表现</th><th>可借鉴动作</th></tr>
                <tr><td>前 8 秒结果预览</td><td>完播率 +18%</td><td><span class="tag hot">加入开场</span></td></tr>
                <tr><td>标题含新手必看</td><td>转粉率 +42%</td><td><span class="tag purple">标题复用</span></td></tr>
                <tr><td>结尾收藏引导</td><td>收藏率 +31%</td><td><span class="tag">脚本加入</span></td></tr>
                <tr><td>步骤编号清晰</td><td>评论提问 +24%</td><td><span class="tag">保留章节</span></td></tr>
              </table>
            </article>
            <article class="card">
              <p class="section-label">你的可复用模板</p>
              <div class="action-list">
                <div><i class="fa-solid fa-eye"></i><span>开场先给完整结果，再进入步骤，不先讲背景。</span></div>
                <div><i class="fa-solid fa-heading"></i><span>标题固定包含人群、时间和结果：新手 / 5 分钟 / 通勤。</span></div>
                <div><i class="fa-solid fa-bookmark"></i><span>结尾明确说“收藏这条，明早按步骤做”。</span></div>
              </div>
            </article>
          </section>
        </section>
      </template>
    </div>
  </main>
</template>
