<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchProfile } from "../services/api";
import { platformLabel } from "../utils/format";
import { actionsFrom, diagnosisItems, groupInsights } from "../utils/pageModels";

defineProps({
  activePage: {
    type: String,
    default: "profile"
  }
});

const emit = defineEmits(["navigate"]);

const tabs = [
  { id: "reports", label: "数据报告" },
  { id: "bindings", label: "平台绑定" },
  { id: "settings", label: "采集设置" },
  { id: "notify", label: "通知偏好" }
];

const activeTab = ref(window.location.hash?.replace("#", "") || "reports");
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
    payload.value = await fetchProfile();
  } catch (apiError) {
    error.value = apiError.message;
  } finally {
    loading.value = false;
  }
}

function syncHash() {
  const next = window.location.hash.replace("#", "");
  activeTab.value = tabs.some((tab) => tab.id === next) ? next : "reports";
}

function setTab(tabId) {
  activeTab.value = tabId;
  window.location.hash = tabId;
}

const model = computed(() => payload.value?.data);
const creator = computed(() => payload.value?.creator);
const accounts = computed(() => model.value?.platformAccounts || []);
const insights = computed(() => model.value?.insights || []);
const insightByTab = computed(() => groupInsights(insights.value, tabs, "profile"));
const reportInsights = computed(() => insightByTab.value.reports || []);
const hasMetricReports = computed(() => reportInsights.value.length > 0);
const isProfileOnly = computed(() => accounts.value.length === 0);
const maxLatency = computed(() => Math.max(...accounts.value.map((item) => item.syncLatencySeconds), 0));
const boundCount = computed(() => accounts.value.filter((item) => item.bindingStatus === "BOUND").length);
const reportStatusText = computed(() => (hasMetricReports.value ? "已生成" : "待生成"));
const reportIntroText = computed(() =>
  hasMetricReports.value
    ? "集中管理你的个人报告、平台绑定、采集频率和通知偏好。报告区用于复盘，设置区用于低频配置。"
    : isProfileOnly.value
    ? "账号档案和平台绑定已完成。增长日报、周报和月报会在模拟事件写入指标后生成。"
    : "账号档案和平台绑定已完成，正在等待增长复盘指标生成。"
);
const weeklyReviewText = computed(() =>
  hasMetricReports.value
    ? "账号增长健康度保持稳定，教程类内容贡献最大"
    : "账号档案已创建，等待模拟事件写入后生成增长复盘。"
);
const creatorName = computed(() => creator.value?.displayName || "你的账号");
const creatorTags = computed(() => (creator.value?.nicheTags || []).join(" / ") || "等待完善账号领域");
const profileFollowerText = computed(() => (hasMetricReports.value ? "已接入" : "待生成"));
const profileFollowerSubText = computed(() => (hasMetricReports.value ? "指标已开始生成" : "等待复盘指标"));
const dailyReportTitle = computed(() => (hasMetricReports.value ? "今日增长" : "暂无日报"));
const dailyReportCopy = computed(() =>
  hasMetricReports.value ? "净增粉丝保持增长，最佳视频来自教程内容。" : "模拟事件写入后，这里会生成你的单日新增、播放转粉和异常变化。"
);
const weeklyReportTitle = computed(() => (hasMetricReports.value ? "内容结构" : "暂无周报"));
const weeklyReportCopy = computed(() =>
  hasMetricReports.value ? "教程类内容贡献更稳，建议提高高转粉平台发布占比。" : "等待至少一段连续事件后，系统会汇总本周内容结构和涨粉来源。"
);
const monthlyReportTitle = computed(() => (hasMetricReports.value ? "账号复盘" : "暂无月报"));
const monthlyReportCopy = computed(() =>
  hasMetricReports.value ? "账号增长健康度稳定，粘性显著改善。" : "月报会在累计足够事件指标后生成，现在只保留账号档案和绑定状态。"
);
const bindingsDiagnosis = computed(() =>
  diagnosisItems(tabInsights("bindings"), [
    { label: "健康平台", title: "抖音、B站、小红书同步正常，可以继续参与实时分析", className: "strong" },
    { label: "授权风险", title: "授权即将过期的平台需要刷新后再纳入周报", className: "warning" },
    { label: "同步状态", title: "核心平台延迟保持在 5-10s，满足增长总览展示" }
  ])
);
const settingsDiagnosis = computed(() =>
  diagnosisItems(tabInsights("settings"), [
    { label: "推荐策略", title: "视频和粉丝数据保持高频，话题和报告数据保持稳定批量", className: "strong" },
    { label: "风险", title: "评论情绪采集过低会影响负面提醒准确性", className: "warning" },
    { label: "稳定性", title: "当前策略可以支撑 5s 增长总览和 30s 粉丝趋势" }
  ])
);
const notifyDiagnosis = computed(() =>
  diagnosisItems(tabInsights("notify"), [
    { label: "已开启", title: "高价值提醒覆盖热点、异常、掉粉和负面评论", className: "strong" },
    { label: "建议新增", title: "授权过期提醒可以避免数据断流", className: "warning" },
    { label: "提醒原则", title: "只有能指导下一步创作或修正风险的事件才提醒" }
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
    <button class="dock-item" type="button" aria-label="机会建议" @click="emit('navigate', 'opportunities')"><i class="fa-solid fa-fire"></i></button>
    <button class="dock-item active" type="button" aria-label="个人中心" @click="emit('navigate', 'profile')"><i class="fa-solid fa-gear"></i></button>
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
        <div class="user-profile"><span class="sync-chip">6 Platforms</span><i class="fa-regular fa-bell" style="color:var(--text-dim)"></i><div class="user-avatar"></div></div>
      </header>

      <section v-if="loading" class="card app-state-card"><p class="section-label">Loading</p><strong class="value">正在加载个人中心数据</strong></section>
      <section v-else-if="error" class="card app-state-card"><p class="section-label">API Error</p><strong class="value">{{ error }}</strong><p class="page-copy">请先启动 Flask API：python api\\app.py</p></section>

      <template v-else>
        <section v-show="activeTab === 'reports'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Creator Profile</p><h1>个人中心</h1></div>
            <p class="page-copy">{{ reportIntroText }}</p>
          </section>
          <section class="diagnosis-strip">
            <article class="diagnosis-card strong"><span>{{ isProfileOnly ? "等待数据" : "本周复盘" }}</span><strong>{{ weeklyReviewText }}</strong></article>
            <article class="diagnosis-card warning"><span>待处理</span><strong>授权状态需要定期检查，否则同步会继续延迟</strong></article>
            <article class="diagnosis-card"><span>提醒策略</span><strong>当前保留高价值提醒，未启用低价值噪声通知</strong></article>
          </section>
          <section class="profile-band">
            <article class="card green">
              <p class="label" style="color:#111">{{ creatorName }}</p>
              <strong class="value large">{{ profileFollowerText }}</strong>
              <span style="font-size:12px;font-weight:800">{{ profileFollowerSubText }}</span>
              <p style="margin-top:18px;font-size:12px;line-height:1.6">领域标签：{{ creatorTags }}</p>
            </article>
            <div class="grid-4">
              <div class="metric-card"><p>绑定平台</p><strong>{{ boundCount }}</strong></div>
              <div class="metric-card"><p>当前同步</p><strong>{{ maxLatency }}s</strong></div>
              <div class="metric-card"><p>本周报告</p><strong>{{ reportStatusText }}</strong></div>
              <div class="metric-card"><p>通知</p><strong>4 项开启</strong></div>
            </div>
          </section>

          <section class="grid-3">
            <article class="card">
              <p class="section-label">个人日报</p>
              <strong class="value">{{ dailyReportTitle }}</strong>
              <p class="page-copy" style="margin-top:12px">{{ dailyReportCopy }}</p>
              <span class="tag hot" style="margin-top:14px">{{ isProfileOnly ? "等待事件数据" : "查看日报" }}</span>
            </article>
            <article class="card">
              <p class="section-label">个人周报</p>
              <strong class="value">{{ weeklyReportTitle }}</strong>
              <p class="page-copy" style="margin-top:12px">{{ weeklyReportCopy }}</p>
              <span class="tag purple" style="margin-top:14px">{{ isProfileOnly ? "等待事件数据" : "查看周报" }}</span>
            </article>
            <article class="card">
              <p class="section-label">个人月报</p>
              <strong class="value">{{ monthlyReportTitle }}</strong>
              <p class="page-copy" style="margin-top:12px">{{ monthlyReportCopy }}</p>
              <span class="tag" style="margin-top:14px">{{ isProfileOnly ? "等待事件数据" : "导出月报" }}</span>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">平台绑定</p>
              <table class="table">
                <tr><th>平台</th><th>账号</th><th>授权</th><th>采集频率</th><th>延迟</th></tr>
                <tr v-for="account in accounts" :key="account.accountId">
                  <td>{{ platformLabel(account.platform) }}</td>
                  <td>{{ account.platformDisplayName }}</td>
                  <td><span class="tag hot">{{ account.bindingStatus }}</span></td>
                  <td>{{ account.collectionIntervalSeconds }} 秒</td>
                  <td>{{ account.syncLatencySeconds }} 秒</td>
                </tr>
              </table>
            </article>
            <article class="card">
              <p class="section-label">报告卡片</p>
              <div class="action-list">
                <div><i class="fa-solid fa-file-lines"></i><span>生成本周增长复盘：转粉、粘性、内容结构三类指标。</span></div>
                <div><i class="fa-solid fa-chart-simple"></i><span>生成视频表现复盘：高转粉视频和低效泛流量视频。</span></div>
                <div><i class="fa-solid fa-bell"></i><span>保留增长机会、异常风险、内容复盘和授权状态提醒。</span></div>
              </div>
            </article>
          </section>
        </section>

        <section v-show="activeTab === 'bindings'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Authorization Health</p><h1>授权健康检查</h1></div>
            <p class="page-copy">查看绑定状态、同步延迟、授权风险和需要刷新项。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in bindingsDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span><strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">平台授权状态</p>
              <div v-for="account in accounts" :key="account.accountId" class="form-row">
                <span>{{ platformLabel(account.platform) }}</span>
                <span class="tag hot">{{ account.bindingStatus === "BOUND" ? "已绑定" : "需刷新授权" }}</span>
                <span>{{ account.syncLatencySeconds }}s</span>
              </div>
            </article>
            <article class="card">
              <p class="section-label">处理建议</p>
              <div class="action-list">
                <div v-for="item in actionsFrom(tabInsights('bindings'), 3)" :key="item.actionId"><i class="fa-solid fa-rotate"></i><span>{{ item.description }}</span></div>
                <div v-if="!actionsFrom(tabInsights('bindings'), 1).length"><i class="fa-solid fa-shield-halved"></i><span>每周检查一次授权状态，减少数据断点。</span></div>
              </div>
            </article>
          </section>
        </section>

        <section v-show="activeTab === 'settings'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Collection Strategy</p><h1>采集策略配置</h1></div>
            <p class="page-copy">按数据价值设置采集频率，让实时页面够快，复盘页面够稳，不浪费采集资源。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in settingsDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span><strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">采集频率</p>
              <div class="form-row"><span>视频数据</span><span>5s</span><span class="tag hot">实时增长</span></div>
              <div class="form-row"><span>粉丝数据</span><span>30s</span><span class="tag purple">趋势稳定</span></div>
              <div class="form-row"><span>话题数据</span><span>60s</span><span class="tag">机会识别</span></div>
              <div class="form-row"><span>评论情绪</span><span>30s</span><span class="tag">建议提高</span></div>
            </article>
            <article class="card">
              <p class="section-label">策略说明</p>
              <div class="action-list">
                <div v-for="item in actionsFrom(tabInsights('settings'), 3)" :key="item.actionId"><i class="fa-solid fa-gauge-high"></i><span>{{ item.description }}</span></div>
                <div v-if="!actionsFrom(tabInsights('settings'), 1).length"><i class="fa-solid fa-bell"></i><span>负面评论提醒需要 30s 以内采集，否则异常提示会滞后。</span></div>
              </div>
            </article>
          </section>
        </section>

        <section v-show="activeTab === 'notify'" class="tab-panel active">
          <section class="page-title">
            <div><p class="eyebrow">Action Rules</p><h1>行动提醒规则</h1></div>
            <p class="page-copy">只保留能触发明确行动的提醒，把增长机会、异常风险、复盘任务和授权状态分开管理。</p>
          </section>
          <section class="diagnosis-strip">
            <article v-for="item in notifyDiagnosis" :key="item.key" class="diagnosis-card" :class="item.className">
              <span>{{ item.label }}</span><strong>{{ item.title }}</strong>
            </article>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">提醒规则</p>
              <div class="form-row"><span>增长机会</span><span>话题适配度超过 85 时提醒</span><span class="switch"></span></div>
              <div class="form-row"><span>异常流量</span><span>播放突增或暴跌时提醒</span><span class="switch"></span></div>
              <div class="form-row"><span>掉粉异常</span><span>掉粉超过日均 2 倍时提醒</span><span class="switch"></span></div>
              <div class="form-row"><span>负面评论</span><span>负面占比突增时提醒</span><span class="switch"></span></div>
            </article>
            <article class="card">
              <p class="section-label">通知分层</p>
              <div class="insight-list">
                <div class="insight-item"><div><strong>立即处理</strong><span>异常流量、掉粉异常、授权过期</span></div><span class="tag hot">高</span></div>
                <div class="insight-item"><div><strong>当天处理</strong><span>热点机会、负面评论趋势</span></div><span class="tag purple">中</span></div>
                <div class="insight-item"><div><strong>周报处理</strong><span>内容结构复盘、平台投入调整</span></div><span class="tag">低</span></div>
              </div>
            </article>
          </section>
        </section>
      </template>
    </div>
  </main>
</template>
