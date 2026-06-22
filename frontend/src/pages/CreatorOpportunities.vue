<script setup>
import { computed, nextTick, onMounted, ref } from "vue";
import ChartPanel from "../components/ChartPanel.vue";
import { fetchOpportunities } from "../services/api";
import { horizontalBarOption } from "../utils/chartOptions";
import { formatPercent } from "../utils/format";
import { actionsFrom, diagnosisItems, groupInsights } from "../utils/pageModels";

defineProps({
  activePage: {
    type: String,
    default: "opportunities"
  }
});

const emit = defineEmits(["navigate"]);

const tabs = [
  { id: "hot", label: "选题机会" },
  { id: "advice", label: "怎么拍" }
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

const model = computed(() => payload.value?.data);
const topics = computed(() => model.value?.topics || []);
const insights = computed(() => model.value?.insights || []);
const isInitialReferenceOnly = computed(() => insights.value.length === 0);
const insightByTab = computed(() => groupInsights(insights.value, tabs, "opportunities"));
const topicRecommendScore = (topic) =>
  Math.round(Number(topic?.creatorFitScore || 0) * 0.5 + Number(topic?.heatScore || 0) * 0.25 + Number(topic?.growthRate || 0) * 100 * 0.25);
const uniqueTopics = computed(() => {
  const byName = new Map();
  for (const topic of topics.value) {
    const name = String(topic?.topicName || topic?.topicId || "").trim();
    if (!name) continue;
    const current = byName.get(name);
    if (!current || topicRecommendScore(topic) > topicRecommendScore(current)) {
      byName.set(name, topic);
    }
  }
  return [...byName.values()];
});
const hotTopics = computed(() =>
  uniqueTopics.value
    .map((topic) => ({ ...topic, recommendScore: topicRecommendScore(topic) }))
    .sort((a, b) => b.recommendScore - a.recommendScore)
    .slice(0, 6)
);
const bestTopic = computed(() => hotTopics.value[0]);
const opportunityIntroText = computed(() =>
  isInitialReferenceOnly.value
    ? "这里先展示初始热点样本。模拟事件接入后，系统会结合你的播放、互动和涨粉表现生成专属机会建议。"
    : "从热点、粉丝偏好和历史高转粉结构里找到你的下一条内容机会，避免只追热度不转粉。"
);
const bestTopicTitle = computed(() =>
  isInitialReferenceOnly.value
    ? `${bestTopic.value?.topicName || "热点样本"}仅作为初始参考，等待账号事件后校准`
    : `${bestTopic.value?.topicName || "下一条内容"}适合作为下一条内容选题`
);
const bestTopicLabel = computed(() => (isInitialReferenceOnly.value ? "初始参考" : "最佳机会"));
const bestTopicScoreText = computed(() =>
  isInitialReferenceOnly.value ? `样本适配度 ${bestTopic.value?.creatorFitScore || 0}` : `适配度 ${bestTopic.value?.creatorFitScore || 0}`
);
const topicHeatText = (score) => (Number(score || 0) >= 85 ? "很热" : Number(score || 0) >= 70 ? "中高" : "一般");
const topicFitText = (score) => (Number(score || 0) >= 90 ? "很适合" : Number(score || 0) >= 80 ? "适合" : "可观察");
const topicRiskText = (risk) => ({ LOW: "低", MEDIUM: "中", HIGH: "高" })[risk] || risk || "-";
const bestTopicReasonCards = computed(() => [
  {
    label: "现在热不热",
    value: `${bestTopic.value?.heatScore || 0}`,
    hint: topicHeatText(bestTopic.value?.heatScore)
  },
  {
    label: "适不适合你",
    value: `${bestTopic.value?.creatorFitScore || 0}`,
    hint: topicFitText(bestTopic.value?.creatorFitScore)
  },
  {
    label: "预计涨粉机会",
    value: formatPercent(bestTopic.value?.growthRate),
    hint: "高于普通选题"
  },
  {
    label: "风险",
    value: topicRiskText(bestTopic.value?.riskLevel),
    hint: "可执行"
  }
]);
const candidateTopics = computed(() =>
  hotTopics.value.map((topic, index) => ({
    ...topic,
    rank: index + 1,
    recommendScore: topic.recommendScore ?? topicRecommendScore(topic)
  }))
);
const scriptStructureRows = computed(() => {
  const topicName = bestTopic.value?.topicName || "下一条内容";
  const includesAny = (words) => words.some((word) => topicName.includes(word));
  const isMakeup = includesAny(["妆", "底妆", "眼妆", "粉底", "持妆"]);
  const isProductList = includesAny(["好物", "包", "清单"]);
  const isReview = includesAny(["测评", "横评", "复盘", "挑战"]);
  const isCommute = includesAny(["通勤", "早八", "职场"]);

  if (isProductList) {
    return [
      { label: "0-8s", value: 100, text: `展示「${topicName}」完整清单` },
      { label: "8-90s", value: 100, text: "拆 3 个必备好物和使用场景", color: "#9a8eff" },
      { label: "90-160s", value: 100, text: "讲避坑、替代选择和预算排序", color: "#61f4ff" },
      { label: "结尾", value: 100, text: "引导收藏 + 评论想看哪种场景" }
    ];
  }

  if (isReview) {
    return [
      { label: "0-8s", value: 100, text: `先给「${topicName}」结论排名` },
      { label: "8-90s", value: 100, text: "按价格、效果和适合人群对比", color: "#9a8eff" },
      { label: "90-160s", value: 100, text: "展示实测差异和不推荐理由", color: "#61f4ff" },
      { label: "结尾", value: 100, text: "总结购买建议 + 引导收藏" }
    ];
  }

  if (isMakeup) {
    return [
      { label: "0-8s", value: 100, text: `展示「${topicName}」前后对比` },
      { label: "8-90s", value: 100, text: "拆 3 个关键步骤和产品顺序", color: "#9a8eff" },
      { label: "90-160s", value: 100, text: "讲卡粉、脱妆、斑驳的修正", color: "#61f4ff" },
      { label: "结尾", value: 100, text: "引导收藏 + 评论肤质场景" }
    ];
  }

  if (isCommute) {
    return [
      { label: "0-8s", value: 100, text: `先给「${topicName}」省时结果` },
      { label: "8-90s", value: 100, text: "拆通勤前、中、后的执行步骤", color: "#9a8eff" },
      { label: "90-160s", value: 100, text: "讲迟到、补妆、携带的应急处理", color: "#61f4ff" },
      { label: "结尾", value: 100, text: "引导收藏 + 评论通勤时长" }
    ];
  }

  return [
    { label: "0-8s", value: 100, text: `先展示「${topicName}」结果` },
    { label: "8-90s", value: 100, text: "拆 3 个执行步骤和适合人群", color: "#9a8eff" },
    { label: "90-160s", value: 100, text: "讲常见误区和可替代方案", color: "#61f4ff" },
    { label: "结尾", value: 100, text: "引导收藏 + 评论下一条想看什么" }
  ];
});
const scriptStructureChartOption = computed(() =>
  horizontalBarOption(scriptStructureRows.value)
);
const adviceDiagnosis = computed(() =>
  isInitialReferenceOnly.value
    ? [
        { key: "initial-topic", label: "等待校准", title: "下一条内容建议需要先接入播放、互动和涨粉事件。", className: "strong" },
        { key: "initial-risk", label: "当前限制", title: "热点样本只能做参考，不能直接判断你的账号一定适合。", className: "warning" },
        { key: "initial-next", label: "下一步", title: "启动模拟链路后，会按你的真实事件表现生成选题和发布时间建议。", className: "" }
      ]
    : diagnosisItems(tabInsights("advice"), [
    { label: "推荐选题", title: `${bestTopic.value?.topicName || "下一条教程内容"}适合作为下一条内容，适配度 ${bestTopic.value?.creatorFitScore || 91}`, className: "strong" },
    { label: "注意事项", title: "不要做泛种草标题，必须明确新手和通勤场景", className: "warning" },
    { label: "预期收益", title: "预计播放转粉率和收藏率会高于泛流量内容" }
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
            <div><p class="eyebrow">Next Topic Decision</p><h1>下一条内容建议</h1></div>
            <p class="page-copy">先看系统建议你下一条拍什么，再看为什么推荐、还有哪些备选选题。</p>
          </section>

          <section class="opportunity-decision-panel">
            <article class="opportunity-decision-card">
              <p class="label">系统建议</p>
              <strong>下一条拍：{{ bestTopic?.topicName || "等待选题" }}</strong>
              <span>{{ isInitialReferenceOnly ? "这是初始热点样本，等事件接入后会按你的账号表现重新校准。" : "这个选题兼顾话题热度、账号适配和预期涨粉机会。" }}</span>
              <button class="decision-action" type="button" @click="setTab('advice')">查看怎么拍</button>
            </article>
            <article class="opportunity-explain-card">
              <p class="section-label">为什么推荐它</p>
              <div class="reason-grid">
                <div v-for="item in bestTopicReasonCards" :key="item.label" class="reason-tile">
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                  <em>{{ item.hint }}</em>
                </div>
              </div>
            </article>
          </section>

          <section class="grid-2">
            <article class="card">
              <p class="section-label">候选选题推荐排行</p>
              <div class="topic-rank-list">
                <article v-for="topic in candidateTopics" :key="topic.topicId" class="topic-rank-item" :class="{ best: topic.topicId === bestTopic?.topicId }">
                  <span class="topic-rank-index">{{ topic.rank }}</span>
                  <div class="topic-rank-body">
                    <div class="topic-rank-title">
                      <strong>{{ topic.topicName }}</strong>
                      <div class="topic-rank-side">
                        <span class="topic-rank-stats">适配 {{ topic.creatorFitScore }} · 热度 {{ topic.heatScore }} · 涨粉 {{ formatPercent(topic.growthRate) }}</span>
                        <span class="topic-score">{{ topic.recommendScore }}</span>
                        <span v-if="topic.topicId === bestTopic?.topicId" class="topic-best-chip">最推荐</span>
                      </div>
                    </div>
                    <div class="topic-rank-track">
                      <span :style="{ width: `${topic.recommendScore}%` }"></span>
                    </div>
                  </div>
                </article>
              </div>
            </article>
            <article class="card">
              <p class="section-label">其他可以考虑的选题</p>
              <table class="table">
                <tr><th>候选选题</th><th>现在热不热</th><th>适不适合你</th><th>预计涨粉机会</th></tr>
                <tr v-for="topic in hotTopics" :key="topic.topicId">
                  <td>{{ topic.topicName }}</td><td>{{ topic.heatScore }} · {{ topicHeatText(topic.heatScore) }}</td><td>{{ topic.creatorFitScore }} · {{ topicFitText(topic.creatorFitScore) }}</td><td>{{ formatPercent(topic.growthRate) }}</td>
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
              <ChartPanel class="chart-panel-funnel" :option="scriptStructureChartOption" />
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

      </template>
    </div>
  </main>
</template>
