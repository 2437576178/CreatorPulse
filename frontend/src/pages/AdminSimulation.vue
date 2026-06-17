<script setup>
import { computed, onMounted, ref } from "vue";
import { fetchSimulationCreators, fetchSimulationEvents, fetchSimulationStatus } from "../services/api";

const emit = defineEmits(["navigate"]);

const loading = ref(true);
const error = ref("");
const status = ref(null);
const creators = ref([]);
const events = ref([]);

const activeCreators = computed(() => creators.value.filter((creator) => creator.platforms.length > 0).length);
const recentCreatorIds = computed(() => new Set(events.value.slice(0, 12).map((event) => event.creatorId)).size);

async function loadSimulation() {
  loading.value = true;
  error.value = "";
  try {
    const [statusPayload, creatorsPayload, eventsPayload] = await Promise.all([
      fetchSimulationStatus(),
      fetchSimulationCreators(),
      fetchSimulationEvents(40)
    ]);
    status.value = statusPayload;
    creators.value = creatorsPayload.creators;
    events.value = eventsPayload.events;
  } catch (loadError) {
    error.value = loadError.message;
  } finally {
    loading.value = false;
  }
}

onMounted(loadSimulation);
</script>

<template>
  <main class="admin-shell">
    <section class="admin-header">
      <div>
        <p class="eyebrow">Simulation Monitor</p>
        <h1>链路健康与模拟控制台</h1>
        <p class="page-copy">只读 MySQL 的第一版监控页，用来确认多达人绑定、Spark 写入批次和最近数据流动情况。</p>
      </div>
      <div class="admin-actions">
        <button type="button" class="ghost-button" @click="emit('navigate', 'growth')">
          <i class="fa-solid fa-chart-line"></i>
          <span>返回增长总览</span>
        </button>
        <button type="button" class="login-button" :disabled="loading" @click="loadSimulation">
          <i class="fa-solid fa-rotate"></i>
          <span>{{ loading ? "刷新中" : "刷新" }}</span>
        </button>
      </div>
    </section>

    <section v-if="loading" class="card app-state-card">
      <p class="section-label">Loading</p>
      <strong class="value">正在读取模拟链路状态</strong>
    </section>

    <section v-else-if="error" class="card app-state-card">
      <p class="section-label">Error</p>
      <strong class="value">{{ error }}</strong>
    </section>

    <template v-else>
      <section class="admin-kpi-grid">
        <article class="metric-card">
          <span>达人总数</span>
          <strong>{{ status.creatorCount }}</strong>
          <small>{{ activeCreators }} 个达人已有平台绑定</small>
        </article>
        <article class="metric-card">
          <span>绑定平台数</span>
          <strong>{{ status.boundPlatformCount }}</strong>
          <small>来自 platform_accounts</small>
        </article>
        <article class="metric-card">
          <span>视频模板数</span>
          <strong>{{ status.videoCount }}</strong>
          <small>mock_generator 会从这里抽样</small>
        </article>
        <article class="metric-card">
          <span>最新 Spark 批次</span>
          <strong>{{ status.latestSparkBatch || "暂无" }}</strong>
          <small>{{ status.latestWriteAt || "尚未写入" }}</small>
        </article>
      </section>

      <section class="grid-2 admin-grid">
        <article class="card">
          <div class="section-head">
            <div>
              <p class="section-label">Creators</p>
              <h2>达人与平台绑定</h2>
            </div>
            <span class="tag">{{ creators.length }} creators</span>
          </div>
          <div class="admin-creator-list">
            <div v-for="creator in creators" :key="creator.creatorId" class="admin-creator-row">
              <div>
                <strong>{{ creator.displayName }}</strong>
                <span>{{ creator.creatorId }}</span>
              </div>
              <div class="admin-platforms">
                <span v-for="platform in creator.platforms" :key="platform.platform" class="tag">
                  {{ platform.label }} · {{ platform.bindingStatus }}
                </span>
              </div>
              <small>最近写入：{{ creator.latestWriteAt || "暂无" }}</small>
            </div>
          </div>
        </article>

        <article class="card">
          <div class="section-head">
            <div>
              <p class="section-label">Recent Flow</p>
              <h2>最近 Spark 写入</h2>
            </div>
            <span class="tag">{{ recentCreatorIds }} creators</span>
          </div>
          <table class="table compact-table">
            <thead>
              <tr>
                <th>达人</th>
                <th>平台</th>
                <th>涨粉</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="event in events.slice(0, 16)" :key="`${event.runId}-${event.creatorId}-${event.platform}`">
                <td>
                  <strong>{{ event.displayName }}</strong>
                  <small>{{ event.creatorId }}</small>
                </td>
                <td>{{ event.platformLabel }}</td>
                <td>{{ event.newFollowers }}</td>
                <td>{{ event.calculatedAt }}</td>
              </tr>
            </tbody>
          </table>
        </article>
      </section>
    </template>
  </main>
</template>
