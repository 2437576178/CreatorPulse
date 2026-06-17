<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchContentDistribution, fetchVideoAnalysis } from "../services/api";
import { contentLabel, formatNumber, formatPercent, platformLabel, sum } from "../utils/format";
import { actionsFrom, aggregateBy, diagnosisItems, groupInsights, pairVideosWithSnapshots } from "../utils/pageModels";

defineProps({
  activePage: {
    type: String,
    default: "content"
  }
});

const emit = defineEmits(["navigate"]);

const tabs = [
  { id: "platform", label: "平台分布" },
  { id: "type", label: "内容类型" },
  { id: "time", label: "发布时间" },
  { id: "source", label: "流量来源" }
];

const activeTab = ref(window.location.hash?.replace("#", "") || "platform");
const loading = ref(true);
const error = ref("");
const payload = ref(null);
const videoPayload = ref(null);

onMounted(async () => {
  window.addEventListener("hashchange", syncHash);
  syncHash();
  await loadData();
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

function syncHash() {
  const next = window.location.hash.replace("#", "");
  activeTab.value = tabs.some((tab) => tab.id === next) ? next : "platform";
}

function setTab(tabId) {
  activeTab.value = tabId;
  window.location.hash = tabId;
}

const insights = computed(() => payload.value?.data?.insights || []);
const insightByTab = computed(() => groupInsights(insights.value, tabs, "content"));
const videoRows = computed(() => pairVideosWithSnapshots(videoPayload.value?.data?.videos || [], videoPayload.value?.data?.snapshots || []));
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
const typeRows = computed(() =>
  aggregateBy(videoRows.value, "contentType", ["views", "newFollowers", "likes", "comments", "shares", "saves"]).sort((a, b) => b.newFollowers - a.newFollowers)
);
const timeRows = computed(() => {
  const rows = videoRows.value.map((video) => ({ ...video, hour: String(video.publishTime).slice(11, 13) }));
  return aggregateBy(rows, "hour", ["views", "newFollowers", "likes", "comments", "shares", "saves"]).sort((a, b) => b.newFollowers - a.newFollowers);
});
const typeDiagnosis = computed(() =>
  diagnosisItems(tabInsights("type"), [
    { label: "优先加码", title: `${contentLabel(typeRows.value[0]?.key) || "教程类"}是当前最高转粉类型，值得提高发布占比`, className: "strong" },
    { label: "减少投入", title: "泛种草播放尚可，但关注和收藏偏弱", className: "warning" },
    { label: "稳定保留", title: "测评类评论质量高，适合承接职场女性人群" }
  ])
);
const timeDiagnosis = computed(() =>
  diagnosisItems(tabInsights("time"), [
    { label: "最佳转粉", title: `${timeRows.value[0]?.key || "20"}:00 最适合发布教程主内容`, className: "strong" },
    { label: "低效窗口", title: "午间播放可观，但转粉率低，适合轻量切片", className: "warning" },
    { label: "高互动窗口", title: "晚间评论和收藏更集中，适合主内容发布" }
  ])
);
const sourceDiagnosis = computed(() =>
  diagnosisItems(tabInsights("source"), [
    { label: "最高质量", title: "搜索流量播放少，但转粉率和收藏率最高", className: "strong" },
    { label: "低质来源", title: "推荐流占比高，但低转粉泛流量偏多", className: "warning" },
    { label: "稳定来源", title: "关注页流量规模中等，但复访和评论更稳定" }
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
    <button class="dock-item active" type="button" aria-label="内容分布" @click="emit('navigate', 'content')"><i class="fa-solid fa-chart-pie"></i></button>
    <button class="dock-item" type="button" aria-label="机会建议" @click="emit('navigate', 'opportunities')"><i class="fa-solid fa-fire"></i></button>
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
        <div class="user-profile"><span class="sync-chip">30s Sync</span><i class="fa-regular fa-bell" style="color:var(--text-dim)"></i><div class="user-avatar"></div></div>
      </header>

      <section v-if="loading" class="card app-state-card"><p class="section-label">Loading</p><strong class="value">正在加载内容分布数据</strong></section>
      <section v-else-if="error" class="card app-state-card"><p class="section-label">API Error</p><strong class="value">{{ error }}</strong><p class="page-copy">请先启动 Flask API：python api\\app.py</p></section>

      <template v-else>
        <section v-show="activeTab === 'platform'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Content Allocation</p><h1>内容分布</h1></div>
            <p class="page-copy">判断你的内容发在哪里、发什么类型、什么时候发是否合理，用分布效率指导下一轮平台和内容投入。</p>
          </section>
          <section class="diagnosis-strip">
            <article class="diagnosis-card strong">
              <span>结构判断</span><strong>{{ platformLabel(platformRows[0]?.key) }}发布占比不高，但涨粉贡献最高，应该继续加码</strong>
            </article>
            <article class="diagnosis-card">
              <span>类型机会</span><strong>{{ contentLabel(typeRows[0]?.key) }}播放占比不一定最高，却更容易贡献新粉</strong>
            </article>
            <article class="diagnosis-card warning">
              <span>投入偏差</span><strong>低转粉平台和泛流量内容占比偏高，下周需要收敛</strong>
            </article>
          </section>
          <section class="grid-4">
            <article class="metric-card"><p>视频总数</p><strong>{{ totalVideos }}</strong></article>
            <article class="metric-card"><p>总播放</p><strong>{{ formatNumber(totalViews) }}</strong></article>
            <article class="metric-card"><p>总涨粉</p><strong>{{ formatNumber(totalFollowers) }}</strong></article>
            <article class="metric-card"><p>平均转粉率</p><strong>{{ formatPercent(totalFollowers / totalViews) }}</strong></article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">平台效率矩阵</p>
              <table class="table">
                <tr><th>平台</th><th>发布投入</th><th>播放贡献</th><th>涨粉贡献</th><th>转粉率</th></tr>
                <tr v-for="row in platformRows" :key="row.key">
                  <td>{{ platformLabel(row.key) }}</td><td>{{ formatPercent((row.videoCount || 0) / totalVideos) }}</td><td>{{ formatPercent(row.views / totalViews) }}</td><td>{{ formatPercent(row.newFollowers / totalFollowers) }}</td><td>{{ formatPercent(row.newFollowers / row.views) }}</td>
                </tr>
              </table>
            </article>
            <article class="card green">
              <p class="label" style="color:#111">最佳平台</p>
              <strong class="value large">{{ platformLabel(platformRows[0]?.key) }}</strong>
              <span style="font-size:12px;font-weight:800">涨粉 {{ formatNumber(platformRows[0]?.newFollowers) }}</span>
              <div class="bar-stack" style="margin-top:18px">
                <div class="bar"><span :style="{ width: `${Math.max(12, platformRows[0]?.views / totalViews * 100 || 0)}%` }">播放贡献 {{ formatPercent(platformRows[0]?.views / totalViews) }}</span></div>
                <div class="bar purple"><span :style="{ width: `${Math.max(12, platformRows[0]?.newFollowers / totalFollowers * 100 || 0)}%` }">涨粉贡献 {{ formatPercent(platformRows[0]?.newFollowers / totalFollowers) }}</span></div>
              </div>
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

        <section v-show="activeTab === 'type'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Type Investment Desk</p><h1>类型投入决策台</h1></div>
            <p class="page-copy">比较教程、测评、种草、Vlog 的播放占比、互动质量和涨粉贡献。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in typeDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span><strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">类型投入产出</p>
              <table class="table">
                <tr><th>类型</th><th>播放贡献</th><th>互动贡献</th><th>涨粉贡献</th><th>动作</th></tr>
                <tr v-for="row in typeRows" :key="row.key">
                  <td>{{ contentLabel(row.key) }}</td><td>{{ formatPercent(row.views / totalViews) }}</td><td>{{ formatPercent((row.likes + row.comments + row.shares + row.saves) / Math.max(1, typeRows.reduce((value, item) => value + item.likes + item.comments + item.shares + item.saves, 0))) }}</td><td>{{ formatPercent(row.newFollowers / totalFollowers) }}</td><td><span class="tag hot">{{ row.newFollowers / row.views > 0.006 ? "加码" : "收缩" }}</span></td>
                </tr>
              </table>
            </article>
            <article class="card white">
              <p class="label" style="color:#666">下周类型配比</p>
              <strong class="value large">{{ contentLabel(typeRows[0]?.key) }} 40%</strong>
              <p style="margin-top:10px;font-size:13px;color:#555">把高转粉类型作为主线，测评作为评论和选题来源，减少低转粉泛内容。</p>
              <div class="bar-stack" style="margin-top:18px">
                <div class="bar"><span style="width:86%">教程 40%</span></div>
                <div class="bar purple"><span style="width:62%">测评 30%</span></div>
                <div class="bar cyan"><span style="width:35%">种草 20%</span></div>
                <div class="bar"><span style="width:18%">Vlog 10%</span></div>
              </div>
            </article>
          </section>
          <section class="card">
            <p class="section-label">执行建议</p>
            <div class="action-list">
              <div v-for="item in actionsFrom(tabInsights('type'), 3)" :key="item.actionId"><i class="fa-solid fa-list-check"></i><span>{{ item.description }}</span></div>
              <div v-if="!actionsFrom(tabInsights('type'), 1).length"><i class="fa-solid fa-vial"></i><span>测评类保留理性对比表，承接 25-30 职场女性评论提问。</span></div>
            </div>
          </section>
        </section>

        <section v-show="activeTab === 'time'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Publish Window Strategy</p><h1>发布窗口策略台</h1></div>
            <p class="page-copy">区分高播放窗口、高转粉窗口和高互动窗口，形成下周排期。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in timeDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span><strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">星期 x 小时转粉率热力图</p>
              <div class="heat-grid">
                <div class="heat-cell">一</div><div class="heat-cell">二</div><div class="heat-cell mid">三</div><div class="heat-cell">四</div><div class="heat-cell hot">五</div><div class="heat-cell hot">六</div><div class="heat-cell mid">日</div>
                <div class="heat-cell">10</div><div class="heat-cell">12</div><div class="heat-cell mid">18</div><div class="heat-cell hot">20</div><div class="heat-cell hot">21</div><div class="heat-cell">22</div><div class="heat-cell">23</div>
              </div>
            </article>
            <article class="card">
              <p class="section-label">下周排期建议</p>
              <div class="insight-list">
                <div class="insight-item"><div><strong>周五 {{ timeRows[0]?.key || "20" }}:00</strong><span>B站首发教程主内容</span></div><span class="tag hot">主推</span></div>
                <div class="insight-item"><div><strong>周六 21:00</strong><span>小红书测评图文和短视频</span></div><span class="tag purple">互动</span></div>
                <div class="insight-item"><div><strong>工作日 12:00</strong><span>只发切片和预告，不放主内容</span></div><span class="tag">轻量</span></div>
              </div>
            </article>
          </section>
        </section>

        <section v-show="activeTab === 'source'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Traffic Quality Diagnosis</p><h1>流量质量诊断台</h1></div>
            <p class="page-copy">用 Insight 判断推荐流、搜索、关注、分享带来的转粉和粘性，而不只看占比。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in sourceDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span><strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">流量质量矩阵</p>
              <table class="table">
                <tr><th>来源</th><th>播放占比</th><th>转粉率</th><th>粘性</th><th>动作</th></tr>
                <tr><td>搜索</td><td>18%</td><td>1.26%</td><td>高</td><td><span class="tag hot">加关键词</span></td></tr>
                <tr><td>关注</td><td>15%</td><td>0.68%</td><td>高</td><td><span class="tag purple">做系列</span></td></tr>
                <tr><td>分享</td><td>8%</td><td>0.74%</td><td>中</td><td><span class="tag">结论图</span></td></tr>
                <tr><td>推荐</td><td>55%</td><td>0.16%</td><td>低</td><td><span class="tag">控泛流量</span></td></tr>
              </table>
            </article>
            <article class="card">
              <p class="section-label">来源占比</p>
              <div class="bar-stack">
                <div class="bar"><span style="width:55%">推荐流 55%</span></div>
                <div class="bar purple"><span style="width:18%">搜索 18%</span></div>
                <div class="bar cyan"><span style="width:15%">关注 15%</span></div>
                <div class="bar"><span style="width:8%">分享 8%</span></div>
              </div>
            </article>
          </section>
          <section class="card">
            <p class="section-label">下一步动作</p>
            <div class="action-list">
              <div v-for="item in actionsFrom(tabInsights('source'), 3)" :key="item.actionId"><i class="fa-solid fa-magnifying-glass"></i><span>{{ item.description }}</span></div>
              <div v-if="!actionsFrom(tabInsights('source'), 1).length"><i class="fa-solid fa-users-viewfinder"></i><span>关注页内容做系列预告，提升老粉复访。</span></div>
            </div>
          </section>
        </section>
      </template>
    </div>
  </main>
</template>
