<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import bilibiliIcon from "../assets/app-icons/bilibili.png";
import douyinIcon from "../assets/app-icons/douyin.png";
import kuaishouIcon from "../assets/app-icons/kuaishou.png";
import weiboIcon from "../assets/app-icons/weibo.png";
import xiaohongshuIcon from "../assets/app-icons/xiaohongshu.png";
import { fetchProfile, fetchReports } from "../services/api";
import { platformLabel } from "../utils/format";
import {
  applyNotificationPreferenceState,
  loadNotificationPreferenceState,
  saveNotificationPreferenceState
} from "../utils/notificationPreferences";
import { actionsFrom, diagnosisItems, groupInsights } from "../utils/pageModels";

defineProps({
  activePage: {
    type: String,
    default: "profile"
  }
});

const emit = defineEmits(["navigate"]);

const platformIconMap = {
  DOUYIN: douyinIcon,
  BILIBILI: bilibiliIcon,
  XIAOHONGSHU: xiaohongshuIcon,
  KUAISHOU: kuaishouIcon,
  WEIBO: weiboIcon
};

const bindingStatusTextMap = {
  BOUND: "已授权",
  EXPIRED: "授权过期",
  PENDING: "待授权",
  UNBOUND: "未绑定"
};

const reportStatusTextMap = {
  GENERATED: "已生成",
  PENDING: "待生成",
  RUNNING: "生成中",
  FAILED: "生成失败"
};

const tabs = [
  { id: "reports", label: "数据报告" },
  { id: "notify", label: "通知偏好" }
];

const activeTab = ref(window.location.hash?.replace("#", "") || "reports");
const loading = ref(true);
const error = ref("");
const payload = ref(null);
const reportsPayload = ref({ items: [], total: 0 });
const selectedReport = ref(null);
const flippedProfileStat = ref("");
const heartbeatAt = ref(Date.now());
const heartbeatTick = ref(Date.now());
let heartbeatTimer = null;
let syncPollTimer = null;
const defaultNotificationRules = [
  { id: "growth", name: "增长机会", description: "话题适配度超过 85 时提醒", enabled: true },
  { id: "traffic", name: "异常流量", description: "播放突增或暴跌时提醒", enabled: true },
  { id: "followerLoss", name: "掉粉异常", description: "掉粉超过日均 2 倍时提醒", enabled: true },
  { id: "negativeComment", name: "负面评论", description: "负面占比突增时提醒", enabled: true }
];
const notificationRules = ref(
  applyNotificationPreferenceState(defaultNotificationRules, loadNotificationPreferenceState())
);

onMounted(async () => {
  window.addEventListener("hashchange", syncHash);
  syncHash();
  await loadData();
  heartbeatTimer = window.setInterval(() => {
    heartbeatTick.value = Date.now();
  }, 1000);
  syncPollTimer = window.setInterval(refreshSyncHeartbeat, 5000);
});

onUnmounted(() => {
  window.removeEventListener("hashchange", syncHash);
  if (heartbeatTimer) window.clearInterval(heartbeatTimer);
  if (syncPollTimer) window.clearInterval(syncPollTimer);
});

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    const [profileData, reportsData] = await Promise.all([fetchProfile(), fetchReports()]);
    payload.value = profileData;
    reportsPayload.value = reportsData;
    heartbeatAt.value = Date.now();
    heartbeatTick.value = heartbeatAt.value;
  } catch (apiError) {
    error.value = apiError.message;
  } finally {
    loading.value = false;
  }
}

async function refreshSyncHeartbeat() {
  try {
    const profileData = await fetchProfile();
    payload.value = profileData;
    heartbeatAt.value = Date.now();
    heartbeatTick.value = heartbeatAt.value;
  } catch {
    heartbeatTick.value = Date.now();
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

function openReport(report) {
  if (!report) return;
  selectedReport.value = report;
}

function closeReport() {
  selectedReport.value = null;
}

function toggleProfileStat(label) {
  flippedProfileStat.value = flippedProfileStat.value === label ? "" : label;
}

function toggleNotificationRule(ruleId) {
  const rule = notificationRules.value.find((item) => item.id === ruleId);
  if (rule) {
    rule.enabled = !rule.enabled;
    saveNotificationPreferenceState(notificationRules.value);
  }
}

function platformIcon(platform) {
  return platformIconMap[platform] || "";
}

function bindingStatusText(status) {
  return bindingStatusTextMap[status] || "需检查授权";
}

function formatReportStatus(status) {
  return reportStatusTextMap[status] || "待生成";
}

const model = computed(() => payload.value?.data);
const creator = computed(() => payload.value?.creator);
const accounts = computed(() => model.value?.platformAccounts || []);
const insights = computed(() => model.value?.insights || []);
const reports = computed(() => reportsPayload.value?.items || []);
const latestReportByType = computed(() => {
  const mapped = {};
  for (const report of reports.value) {
    if (!mapped[report.reportType]) {
      mapped[report.reportType] = report;
    }
  }
  return mapped;
});
const dailyReport = computed(() => latestReportByType.value.DAILY);
const weeklyReport = computed(() => latestReportByType.value.WEEKLY);
const monthlyReport = computed(() => latestReportByType.value.MONTHLY);
const reportCards = computed(() => [
  {
    type: "DAILY",
    label: "个人日报",
    title: dailyReport.value?.title || "日报待生成",
    report: dailyReport.value,
    icon: "fa-calendar-day",
    tagClass: "hot",
    hint: dailyReport.value ? `净增 ${dailyReport.value.metrics?.netFollowers ?? 0} 粉丝` : "等待离线任务",
    metric: dailyReport.value?.metrics?.views ? `${dailyReport.value.metrics.views.toLocaleString()} 播放` : "暂无指标"
  },
  {
    type: "WEEKLY",
    label: "个人周报",
    title: weeklyReport.value?.title || "周报待生成",
    report: weeklyReport.value,
    icon: "fa-calendar-week",
    tagClass: "purple",
    hint: weeklyReport.value ? `净增 ${weeklyReport.value.metrics?.netFollowers ?? 0} 粉丝` : "等待周期数据",
    metric: weeklyReport.value?.metrics?.bestPlatform ? `${weeklyReport.value.metrics.bestPlatform} 贡献最高` : "暂无判断"
  },
  {
    type: "MONTHLY",
    label: "个人月报",
    title: monthlyReport.value?.title || "月报待生成",
    report: monthlyReport.value,
    icon: "fa-calendar-days",
    tagClass: "",
    hint: monthlyReport.value ? `净增 ${monthlyReport.value.metrics?.netFollowers ?? 0} 粉丝` : "等待月度生成",
    metric: monthlyReport.value?.metrics?.bestContentType ? `${monthlyReport.value.metrics.bestContentType} 最值得投入` : "暂无策略"
  }
]);
const insightByTab = computed(() => groupInsights(insights.value, tabs, "profile"));
const reportInsights = computed(() => insightByTab.value.reports || []);
const hasMetricReports = computed(() => reports.value.some((report) => report.status === "GENERATED") || reportInsights.value.length > 0);
const isProfileOnly = computed(() => accounts.value.length === 0);
const maxLatency = computed(() => Math.max(...accounts.value.map((item) => item.syncLatencySeconds), 0));
const boundCount = computed(() => accounts.value.filter((item) => item.bindingStatus === "BOUND").length);
const heartbeatSecondsAgo = computed(() => Math.max(0, Math.floor((heartbeatTick.value - heartbeatAt.value) / 1000)));
const heartbeatHealthy = computed(() => heartbeatSecondsAgo.value <= 8 && !error.value);
const reportStatusText = computed(() => (hasMetricReports.value ? "已生成" : "待生成"));
const reportIntroText = computed(() =>
  hasMetricReports.value
    ? "集中管理你的个人报告和通知偏好。报告区用于复盘，通知区用于保留高价值提醒。"
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
const profileQuickStats = computed(() => [
  {
    label: "绑定平台",
    value: boundCount.value,
    suffix: "",
    icon: "fa-link",
    tone: "cyan",
    note: `${accounts.value.length || 0} 个账号档案`,
    backValue: accounts.value.filter((item) => item.bindingStatus === "BOUND").map((item) => platformLabel(item.platform)).join(" / ") || "暂无绑定",
    detail: accounts.value.length
      ? `已绑定 ${boundCount.value} / ${accounts.value.length} 个平台，未授权平台不会进入报告统计。`
      : "注册时选择平台后，这里会显示每个平台的授权状态。",
    progress: Math.min(100, Math.round((boundCount.value / Math.max(accounts.value.length || 1, 1)) * 100))
  },
  {
    label: "当前同步",
    value: heartbeatHealthy.value ? "心跳正常" : "心跳异常",
    displayValue: heartbeatHealthy.value ? `${heartbeatSecondsAgo.value}s 前检测` : `${heartbeatSecondsAgo.value}s 未响应`,
    displayNote: heartbeatHealthy.value ? "心跳正常" : "心跳异常",
    suffix: "",
    icon: "fa-heart-pulse",
    tone: "green",
    heartbeat: true,
    note: heartbeatHealthy.value ? `${heartbeatSecondsAgo.value}s 前检测` : `${heartbeatSecondsAgo.value}s 未响应`,
    backValue: `最大延迟 ${maxLatency.value}s`,
    detail: heartbeatHealthy.value
      ? `心跳检测：${heartbeatSecondsAgo.value}s 前成功；平台同步：当前账号里最慢的平台延迟 ${maxLatency.value}s。`
      : `心跳检测：已 ${heartbeatSecondsAgo.value}s 未成功；平台同步延迟保留最近一次数据 ${maxLatency.value}s。`,
    progress: Math.max(8, Math.min(100, 100 - Math.round((maxLatency.value / 60) * 100)))
  },
  {
    label: "报告净增",
    value: weeklyReportMetric.value,
    suffix: "",
    icon: "fa-chart-line",
    tone: "purple",
    note: hasMetricReports.value ? "来自最新复盘" : "等待离线报告",
    backValue: weeklyReportMetric.value,
    detail: hasMetricReports.value
      ? `最新报告净增 ${weeklyReportMetric.value} 粉丝，用于判断本周期内容是否值得复刻。`
      : "离线日报、周报生成后，这里会显示最新净增结果。",
    progress: hasMetricReports.value ? 78 : 18
  },
  {
    label: "通知",
    value: `${notificationRules.value.filter((item) => item.enabled).length} 项`,
    suffix: "开启",
    icon: "fa-bell",
    tone: "warm",
    note: "只保留高价值提醒",
    backValue: `${notificationRules.value.filter((item) => item.enabled).length}/${notificationRules.value.length}`,
    detail: `当前开启 ${notificationRules.value.filter((item) => item.enabled).length} / ${notificationRules.value.length} 条规则，优先提醒增长机会和异常风险。`,
    progress: Math.round((notificationRules.value.filter((item) => item.enabled).length / Math.max(notificationRules.value.length, 1)) * 100)
  }
]);
const dailyReportTitle = computed(() => dailyReport.value?.title || "暂无日报");
const dailyReportCopy = computed(() =>
  dailyReport.value?.summary || "模拟事件写入后，这里会生成你的单日新增、播放转粉和异常变化。"
);
const weeklyReportTitle = computed(() => weeklyReport.value?.title || "暂无周报");
const weeklyReportCopy = computed(() =>
  weeklyReport.value?.summary || "等待至少一段连续事件后，系统会汇总本周内容结构和涨粉来源。"
);
const monthlyReportTitle = computed(() => monthlyReport.value?.title || "暂无月报");
const monthlyReportCopy = computed(() =>
  monthlyReport.value?.summary || "月报会在累计足够事件指标后生成，现在只保留账号档案和绑定状态。"
);
const weeklyReportMetric = computed(() => weeklyReport.value?.metrics?.netFollowers ?? dailyReport.value?.metrics?.netFollowers ?? "待生成");
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
            <article class="diagnosis-card strong weekly-review-card"><span>{{ isProfileOnly ? "等待数据" : "本周复盘" }}</span><strong>{{ weeklyReviewText }}</strong></article>
            <article class="diagnosis-card warning"><span>待处理</span><strong>授权状态需要定期检查，否则同步会继续延迟</strong></article>
            <article class="diagnosis-card reminder-strategy-card"><span>提醒策略</span><strong>当前保留高价值提醒，未启用低价值噪声通知</strong></article>
          </section>
          <section class="profile-band">
            <article class="card green profile-status-card">
              <p class="label" style="color:#111">{{ creatorName }}</p>
              <strong class="value large">{{ profileFollowerText }}</strong>
              <span style="font-size:12px;font-weight:800">{{ profileFollowerSubText }}</span>
              <p style="margin-top:18px;font-size:12px;line-height:1.6">领域标签：{{ creatorTags }}</p>
            </article>
            <div class="grid-4 profile-metric-grid">
              <button
                v-for="stat in profileQuickStats"
                :key="stat.label"
                class="profile-metric-card"
                :class="[`tone-${stat.tone}`, { flipped: flippedProfileStat === stat.label, 'heartbeat-card': stat.heartbeat, 'heartbeat-online': stat.heartbeat && heartbeatHealthy }]"
                type="button"
                :aria-pressed="flippedProfileStat === stat.label"
                @click="toggleProfileStat(stat.label)"
              >
                <span class="profile-metric-inner">
                  <span class="profile-metric-face profile-metric-front">
                    <span class="profile-metric-top">
                      <span>{{ stat.label }}</span>
                      <span class="profile-metric-icon" :class="{ heartbeat: stat.heartbeat, online: stat.heartbeat && heartbeatHealthy }"><i class="fa-solid" :class="stat.icon"></i></span>
                    </span>
                    <span class="profile-metric-value-row">
                      <strong>{{ stat.displayValue || stat.value }}<small>{{ stat.suffix }}</small></strong>
                      <span v-if="stat.heartbeat" class="profile-ecg-wave" aria-hidden="true">
                        <svg viewBox="0 0 160 40" preserveAspectRatio="none" focusable="false">
                          <polyline class="profile-ecg-line profile-ecg-line-ghost" points="0,22 18,22 24,22 31,8 38,34 47,22 68,22 76,15 86,28 96,22 116,22 124,18 132,25 140,22 160,22" />
                          <polyline class="profile-ecg-line profile-ecg-line-live" points="0,22 18,22 24,22 31,8 38,34 47,22 68,22 76,15 86,28 96,22 116,22 124,18 132,25 140,22 160,22" />
                        </svg>
                      </span>
                    </span>
                    <em>{{ stat.displayNote || stat.note }}</em>
                    <span class="profile-metric-track"><span :style="{ width: `${stat.progress}%` }"></span></span>
                  </span>
                  <span class="profile-metric-face profile-metric-back">
                    <span class="profile-metric-back-title">{{ stat.label }}详情</span>
                    <strong>{{ stat.backValue }}</strong>
                    <em>{{ stat.detail }}</em>
                    <span class="profile-metric-hint">点击返回</span>
                  </span>
                </span>
              </button>
            </div>
          </section>

          <section class="report-launch-grid">
            <button v-for="card in reportCards" :key="card.type" class="report-launch-card" type="button" :disabled="!card.report" @click="openReport(card.report)">
              <span class="report-launch-icon"><i class="fa-solid" :class="card.icon"></i></span>
              <span class="report-launch-body">
                <span class="section-label">{{ card.label }}</span>
                <strong>{{ card.title }}</strong>
                <em>{{ card.hint }}</em>
              </span>
              <span class="report-launch-side">
                <span class="tag" :class="card.tagClass">{{ formatReportStatus(card.report?.status) }}</span>
                <small>{{ card.metric }}</small>
                <i class="fa-solid fa-chevron-right"></i>
              </span>
            </button>
          </section>
          <section class="grid-2">
            <article class="card">
              <p class="section-label">平台绑定</p>
              <table class="table">
                <tr><th>平台</th><th>账号</th><th>授权</th><th>采集频率</th><th>延迟</th></tr>
                <tr v-for="account in accounts" :key="account.accountId">
                  <td>
                    <span class="platform-cell">
                      <img v-if="platformIcon(account.platform)" :src="platformIcon(account.platform)" :alt="platformLabel(account.platform)" />
                      <span>{{ platformLabel(account.platform) }}</span>
                    </span>
                  </td>
                  <td>{{ account.platformDisplayName }}</td>
                  <td><span class="tag hot">{{ bindingStatusText(account.bindingStatus) }}</span></td>
                  <td>{{ account.collectionIntervalSeconds }} 秒</td>
                  <td>{{ account.syncLatencySeconds }} 秒</td>
                </tr>
              </table>
            </article>
            <article class="card">
              <p class="section-label">报告卡片</p>
              <div class="action-list">
                <div v-for="action in (dailyReport?.actions || weeklyReport?.actions || monthlyReport?.actions || []).slice(0, 3)" :key="action"><i class="fa-solid fa-file-lines"></i><span>{{ action }}</span></div>
                <div v-if="!(dailyReport?.actions || weeklyReport?.actions || monthlyReport?.actions || []).length"><i class="fa-solid fa-chart-simple"></i><span>等待离线任务生成后，这里会展示日报、周报和月报的行动建议。</span></div>
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
              <div v-for="rule in notificationRules" :key="rule.id" class="form-row">
                <span>{{ rule.name }}</span>
                <span>{{ rule.description }}</span>
                <button
                  class="switch"
                  :class="{ off: !rule.enabled }"
                  type="button"
                  role="switch"
                  :aria-checked="rule.enabled"
                  :aria-label="`${rule.name}提醒`"
                  @click="toggleNotificationRule(rule.id)"
                ></button>
              </div>
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

    <div v-if="selectedReport" class="report-detail-layer" role="dialog" aria-modal="true" @click.self="closeReport">
      <article class="report-detail-modal">
        <header class="report-detail-header">
          <div>
            <p class="section-label">{{ selectedReport.reportType }} Report</p>
            <h2>{{ selectedReport.title }}</h2>
          </div>
          <button class="report-close-button" type="button" aria-label="关闭报告详情" @click="closeReport">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </header>
        <p class="report-detail-summary">{{ selectedReport.summary }}</p>
        <div class="report-detail-metrics">
          <div><span>净增粉丝</span><strong>{{ selectedReport.metrics?.netFollowers ?? 0 }}</strong></div>
          <div><span>播放量</span><strong>{{ selectedReport.metrics?.views?.toLocaleString?.() || selectedReport.metrics?.views || 0 }}</strong></div>
          <div><span>互动量</span><strong>{{ selectedReport.metrics?.interactions?.toLocaleString?.() || selectedReport.metrics?.interactions || 0 }}</strong></div>
          <div><span>健康度</span><strong>{{ selectedReport.metrics?.growthHealthScore ?? "-" }}</strong></div>
        </div>
        <div class="grid-3 report-detail-sections">
          <section>
            <p class="section-label">关键亮点</p>
            <ul><li v-for="item in selectedReport.highlights" :key="item">{{ item }}</li></ul>
          </section>
          <section>
            <p class="section-label">风险提醒</p>
            <ul><li v-for="item in selectedReport.risks" :key="item">{{ item }}</li></ul>
          </section>
          <section>
            <p class="section-label">下一步动作</p>
            <ul><li v-for="item in selectedReport.actions" :key="item">{{ item }}</li></ul>
          </section>
        </div>
      </article>
    </div>
  </main>
</template>
