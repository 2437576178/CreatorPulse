<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchVideoAnalysis } from "../services/api";
import { contentLabel, formatNumber, formatPercent, lifecycleLabel, platformLabel, sum } from "../utils/format";
import { actionsFrom, aggregateBy, diagnosisItems, groupInsights, pairVideosWithSnapshots, topRows } from "../utils/pageModels";

defineProps({
  activePage: {
    type: String,
    default: "video"
  }
});

const emit = defineEmits(["navigate"]);

const tabs = [
  { id: "latest", label: "最新视频" },
  { id: "contribution", label: "涨粉贡献" },
  { id: "quality", label: "互动质量" },
  { id: "life", label: "生命周期" }
];

const activeTab = ref(window.location.hash?.replace("#", "") || "latest");
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
    payload.value = await fetchVideoAnalysis();
  } catch (apiError) {
    error.value = apiError.message;
  } finally {
    loading.value = false;
  }
}

function syncHash() {
  const next = window.location.hash.replace("#", "");
  activeTab.value = tabs.some((tab) => tab.id === next) ? next : "latest";
}

function setTab(tabId) {
  activeTab.value = tabId;
  window.location.hash = tabId;
}

const model = computed(() => payload.value?.data);
const videos = computed(() => model.value?.videos || []);
const snapshots = computed(() => model.value?.snapshots || []);
const videoRows = computed(() => pairVideosWithSnapshots(videos.value, snapshots.value));
const insights = computed(() => model.value?.insights || []);
const insightByTab = computed(() => groupInsights(insights.value, tabs, "video"));
const sparkContributions = computed(() => model.value?.sparkContributions || []);

const latestVideos = computed(() =>
  [...videoRows.value].sort((a, b) => String(b.publishTime).localeCompare(String(a.publishTime))).slice(0, 3)
);
const contributionVideos = computed(() =>
  (sparkContributions.value.length ? sparkContributions.value : topRows(videoRows.value, "newFollowers", 10)).slice(0, 3)
);
const qualityVideos = computed(() => topRows(videoRows.value, "engagementRate", 6));
const lifecycleRows = computed(() =>
  aggregateBy(videoRows.value, "lifecycleStage", ["views", "newFollowers", "likes", "comments", "shares", "saves"])
);
const lifecycleStageRows = computed(() =>
  lifecycleRows.value.slice(0, 4).map((row) => ({
    ...row,
    representative: topRows(videoRows.value.filter((video) => video.lifecycleStage === row.key), "newFollowers", 1)[0]
  }))
);
const totalViews = computed(() => sum(videoRows.value, "views"));
const totalFollowers = computed(() => sum(videoRows.value, "newFollowers"));
const totalInteractions = computed(() =>
  videoRows.value.reduce((value, video) => value + video.likes + video.comments + video.shares + video.saves, 0)
);
const totalSaves = computed(() => sum(videoRows.value, "saves"));
const totalComments = computed(() => sum(videoRows.value, "comments"));
const totalShares = computed(() => sum(videoRows.value, "shares"));
const totalLikes = computed(() => sum(videoRows.value, "likes"));
const bestConversionVideo = computed(() => [...videoRows.value].sort((a, b) => Number(b.conversionRate || 0) - Number(a.conversionRate || 0))[0]);
const lowConversionCount = computed(() => videoRows.value.filter((video) => Number(video.views || 0) > totalViews.value / Math.max(videoRows.value.length, 1) && Number(video.conversionRate || 0) < 0.003).length);
const highStickinessCount = computed(() => videoRows.value.filter((video) => Number(video.saveRate || 0) > 0.08 || Number(video.engagementRate || 0) > 0.12).length);
const contributionDiagnosis = computed(() =>
  diagnosisItems(tabInsights("contribution"), [
    { label: "最值得复刻", title: `${bestConversionVideo.value?.title || "教程视频"}带来最高转粉效率`, className: "strong" },
    { label: "高播放低转粉", title: `${lowConversionCount.value} 条视频需要补主页 CTA 和关注理由`, className: "warning" },
    { label: "复刻方向", title: "结果预览 + 步骤拆解 + 收藏引导表现最好" }
  ])
);
const qualityDiagnosis = computed(() =>
  diagnosisItems(tabInsights("quality"), [
    { label: "高价值信号", title: "评论提问和收藏回看正在推动教程类视频转粉", className: "strong" },
    { label: "风险互动", title: "普通点赞偏浅，需要用收藏和评论问题提高复访", className: "warning" },
    { label: "平台差异", title: "B站弹幕密度高，小红书收藏强，抖音点赞偏浅" }
  ])
);
const lifeDiagnosis = computed(() =>
  diagnosisItems(tabInsights("life"), [
    { label: "当前机会", title: "爆发期视频适合追加评论置顶和系列预告", className: "strong" },
    { label: "衰退提醒", title: "高播放低转粉视频进入衰退前要复盘标题预期", className: "warning" },
    { label: "长尾资产", title: "教程类长尾贡献稳定，可整理成合集入口" }
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
    <button class="dock-item active" type="button" aria-label="视频分析" @click="emit('navigate', 'video')"><i class="fa-solid fa-play"></i></button>
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
        <div class="user-profile"><span class="sync-chip">5s Sync</span><i class="fa-regular fa-bell" style="color:var(--text-dim)"></i><div class="user-avatar"></div></div>
      </header>

      <section v-if="loading" class="card app-state-card">
        <p class="section-label">Loading</p><strong class="value">正在加载视频分析数据</strong>
      </section>
      <section v-else-if="error" class="card app-state-card">
        <p class="section-label">API Error</p><strong class="value">{{ error }}</strong><p class="page-copy">请先启动 Flask API：python api\\app.py</p>
      </section>

      <template v-else>
        <section v-show="activeTab === 'latest'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Video Growth Review</p><h1>视频分析</h1></div>
            <p class="page-copy">找出哪些视频真正带来粉丝增长，哪些只有播放没有转粉，并复盘标题、封面、发布时间和内容类型。</p>
          </section>
          <section class="grid-4">
            <article class="card green"><p class="label" style="color:#111">涨粉贡献 TOP</p><strong class="value large">+{{ formatNumber(bestConversionVideo?.newFollowers) }}</strong><span style="font-size:12px;font-weight:800">{{ bestConversionVideo?.title }}</span></article>
            <article class="card"><p class="section-label">高播放低转粉</p><strong class="value">{{ lowConversionCount }} 条</strong><span class="delta red">需要复盘 CTA</span></article>
            <article class="card"><p class="section-label">高粘性视频</p><strong class="value">{{ highStickinessCount }} 条</strong><span class="delta">收藏率高于 15%</span></article>
            <article class="card"><p class="section-label">正在加速</p><strong class="value">5 条</strong><span class="delta">5s 增长持续上升</span></article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">单视频增长曲线</p>
              <div class="media-row">
                <div class="thumb"></div>
                <div>
                  <strong>{{ bestConversionVideo?.title }}</strong>
                  <p class="page-copy">{{ platformLabel(bestConversionVideo?.platform) }} / {{ contentLabel(bestConversionVideo?.contentType) }}，适合继续放大。</p>
                </div>
              </div>
              <div class="mini-bars" style="height:190px;margin-top:20px">
                <span style="height:36px"></span><span style="height:52px"></span><span style="height:90px"></span><span style="height:136px"></span><span style="height:172px"></span><span style="height:150px"></span>
              </div>
            </article>
            <article class="card white">
              <p class="label" style="color:#666">推荐复盘</p>
              <strong class="value large">{{ formatPercent(bestConversionVideo?.conversionRate) }}</strong>
              <span style="font-size:12px;color:#ff5e5e;font-weight:800">播放转粉率高于均值</span>
              <div class="bar-stack" style="margin-top:20px">
                <div class="bar"><span style="width:82%">标题关键词匹配</span></div>
                <div class="bar purple"><span style="width:76%">发布时间有效</span></div>
                <div class="bar cyan"><span style="width:69%">封面收藏倾向</span></div>
              </div>
            </article>
          </section>
          <section class="card">
            <p class="section-label">视频列表</p>
            <table class="table">
              <tr><th>视频</th><th>平台</th><th>播放</th><th>涨粉</th><th>转粉率</th><th>状态</th></tr>
              <tr v-for="video in latestVideos" :key="video.videoId">
                <td><div class="media-row"><div class="thumb"></div><span>{{ video.title }}</span></div></td>
                <td>{{ platformLabel(video.platform) }}</td>
                <td>{{ formatNumber(video.views) }}</td>
                <td>{{ formatNumber(video.newFollowers) }}</td>
                <td>{{ formatPercent(video.conversionRate) }}</td>
                <td><span class="tag hot">加速</span></td>
              </tr>
            </table>
          </section>
        </section>

        <section v-show="activeTab === 'contribution'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Follower Attribution</p><h1>视频涨粉归因台</h1></div>
            <p class="page-copy">对比播放、新粉和转粉率，找出真正带来关注的视频。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in contributionDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span><strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">涨粉贡献排行</p>
              <table class="table">
                <tr><th>视频</th><th>平台</th><th>播放</th><th>涨粉</th><th>转粉率</th><th>动作</th></tr>
                <tr v-for="video in contributionVideos" :key="video.videoId">
                  <td>{{ video.title }}</td><td>{{ platformLabel(video.platform) }}</td><td>{{ formatNumber(video.views) }}</td><td>+{{ formatNumber(video.newFollowers) }}</td><td>{{ formatPercent(video.conversionRate) }}</td><td><span class="tag hot">{{ video.conversionRate > 0.008 ? "复刻系列" : "改 CTA" }}</span></td>
                </tr>
              </table>
            </article>
            <article class="card white">
              <p class="label" style="color:#666">复刻价值评分</p>
              <strong class="value large">91</strong>
              <p style="margin-top:10px;font-size:13px;color:#555">高复刻价值来自明确人群、可收藏步骤和结尾系列预告。</p>
              <div class="bar-stack" style="margin-top:18px">
                <div class="bar"><span style="width:91%">内容结构 91</span></div>
                <div class="bar purple"><span style="width:82%">转粉效率 82</span></div>
                <div class="bar cyan"><span style="width:76%">评论质量 76</span></div>
              </div>
            </article>
          </section>
          <section class="card">
            <p class="section-label">下一步动作</p>
            <div class="action-list">
              <div v-for="item in actionsFrom(tabInsights('contribution'), 3)" :key="item.actionId">
                <i class="fa-solid fa-repeat"></i><span>{{ item.description }}</span>
              </div>
              <div v-if="!actionsFrom(tabInsights('contribution'), 1).length"><i class="fa-solid fa-repeat"></i><span>把最高转粉视频拆成 3 集系列，继续承接高转粉人群。</span></div>
            </div>
          </section>
        </section>

        <section v-show="activeTab === 'quality'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Interaction Value</p><h1>互动价值诊断</h1></div>
            <p class="page-copy">区分点赞、评论提问、收藏回看和分享推荐，判断互动是否有业务价值。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in qualityDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span><strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">互动价值分布</p>
              <div class="bar-stack">
                <div class="bar"><span :style="{ width: `${Math.max(18, totalSaves / totalInteractions * 100 || 0)}%` }">收藏回看 {{ formatNumber(totalSaves) }}</span></div>
                <div class="bar purple"><span :style="{ width: `${Math.max(18, totalComments / totalInteractions * 100 || 0)}%` }">评论提问 {{ formatNumber(totalComments) }}</span></div>
                <div class="bar cyan"><span :style="{ width: `${Math.max(18, totalShares / totalInteractions * 100 || 0)}%` }">分享推荐 {{ formatNumber(totalShares) }}</span></div>
                <div class="bar"><span :style="{ width: `${Math.max(18, totalLikes / totalInteractions * 100 || 0)}%` }">普通点赞 {{ formatNumber(totalLikes) }}</span></div>
              </div>
            </article>
            <article class="card">
              <p class="section-label">提升动作</p>
              <div class="action-list">
                <div v-for="item in actionsFrom(tabInsights('quality'), 3)" :key="item.actionId">
                  <i class="fa-solid fa-bookmark"></i><span>{{ item.description }}</span>
                </div>
                <div v-if="!actionsFrom(tabInsights('quality'), 1).length"><i class="fa-solid fa-comments"></i><span>把评论区问题做成下一条视频开头，提高连续互动。</span></div>
              </div>
            </article>
          </section>
        </section>

        <section v-show="activeTab === 'life'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Lifecycle Management</p><h1>视频阶段管理</h1></div>
            <p class="page-copy">把视频分成爆发、稳定、长尾和二次推荐，决定补投、复刻或复盘。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in lifeDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span><strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">阶段动作矩阵</p>
              <table class="table">
                <tr><th>阶段</th><th>代表视频</th><th>信号</th><th>动作</th></tr>
                <tr v-for="row in lifecycleStageRows" :key="row.key">
                  <td>{{ lifecycleLabel(row.key) }}</td><td>{{ row.representative?.title || "待观察视频" }}</td><td>{{ formatNumber(row.newFollowers) }} 新粉</td><td><span class="tag hot">{{ row.newFollowers > 8000 ? "置顶 CTA" : "合集入口" }}</span></td>
                </tr>
              </table>
            </article>
            <article class="card">
              <p class="section-label">生命周期分布</p>
              <div class="bar-stack">
                <div v-for="row in lifecycleRows" :key="row.key" class="bar" :class="{ purple: row.key === 'STABLE', cyan: row.key === 'LONG_TAIL' }">
                  <span :style="{ width: `${Math.max(18, row.views / totalViews * 100 || 0)}%` }">{{ lifecycleLabel(row.key) }} {{ formatNumber(row.views) }}</span>
                </div>
              </div>
            </article>
          </section>
        </section>
      </template>
    </div>
  </main>
</template>
