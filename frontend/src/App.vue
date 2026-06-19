<script setup>
import { computed, onMounted, ref } from "vue";
import AdminSimulation from "./pages/AdminSimulation.vue";
import ContentDistribution from "./pages/ContentDistribution.vue";
import CreatorOpportunities from "./pages/CreatorOpportunities.vue";
import CreatorProfile from "./pages/CreatorProfile.vue";
import FansAnalysis from "./pages/FansAnalysis.vue";
import GrowthDashboard from "./pages/GrowthDashboard.vue";
import LoginPage from "./pages/LoginPage.vue";
import VideoAnalysis from "./pages/VideoAnalysis.vue";
import { fetchMe, logout } from "./services/api";

const isAdminSimulationPath = () => window.location.pathname === "/admin/simulation";
const page = ref(isAdminSimulationPath() ? "adminSimulation" : new URLSearchParams(window.location.search).get("page") || "growth");
const checkingSession = ref(true);
const currentUser = ref(null);
const loggingOut = ref(false);

const defaultHashByPage = {
  growth: "overview",
  fans: "growth",
  video: "latest",
  content: "platform",
  opportunities: "hot",
  profile: "reports"
};

function setPage(nextPage) {
  page.value = nextPage;
  const url = new URL(window.location.href);
  url.pathname = "/";
  url.hash = defaultHashByPage[nextPage] || "overview";
  if (nextPage === "growth") {
    url.searchParams.delete("page");
  } else {
    url.searchParams.set("page", nextPage);
  }
  window.history.pushState({}, "", url);
}

function resetToHome() {
  page.value = "growth";
  const url = new URL(window.location.href);
  url.pathname = "/";
  url.searchParams.delete("page");
  url.hash = defaultHashByPage.growth;
  window.history.replaceState({}, "", url);
}

const currentPage = computed(() => {
  if (page.value === "adminSimulation") {
    return page.value;
  }
  if (["growth", "fans", "video", "content", "opportunities", "profile"].includes(page.value)) {
    return page.value;
  }
  return "growth";
});

onMounted(async () => {
  try {
    const payload = await fetchMe();
    currentUser.value = payload.user;
  } catch {
    currentUser.value = null;
    if (!isAdminSimulationPath()) {
      resetToHome();
    }
  } finally {
    checkingSession.value = false;
  }
});

function setAuthenticatedUser(user) {
  currentUser.value = user;
  if (isAdminSimulationPath()) {
    page.value = "adminSimulation";
  } else {
    resetToHome();
  }
}

async function handleLogout() {
  loggingOut.value = true;
  try {
    await logout();
  } finally {
    currentUser.value = null;
    resetToHome();
    loggingOut.value = false;
  }
}
</script>

<template>
  <section v-if="checkingSession" class="card app-state-card"><p class="section-label">Loading</p><strong class="value">正在确认登录状态</strong></section>
  <LoginPage v-else-if="!currentUser" @authenticated="setAuthenticatedUser" />
  <template v-else>
    <AdminSimulation v-if="currentPage === 'adminSimulation'" @navigate="setPage" />
    <GrowthDashboard v-else-if="currentPage === 'growth'" :active-page="currentPage" @navigate="setPage" />
    <FansAnalysis v-else-if="currentPage === 'fans'" :active-page="currentPage" @navigate="setPage" />
    <VideoAnalysis v-else-if="currentPage === 'video'" :active-page="currentPage" @navigate="setPage" />
    <ContentDistribution v-else-if="currentPage === 'content'" :active-page="currentPage" @navigate="setPage" />
    <CreatorOpportunities v-else-if="currentPage === 'opportunities'" :active-page="currentPage" @navigate="setPage" />
    <CreatorProfile v-else :active-page="currentPage" @navigate="setPage" />
    <Teleport v-if="currentPage !== 'adminSimulation'" :key="currentPage" defer to=".glass-board">
      <div class="session-bar" aria-label="当前登录账号">
        <span>{{ currentUser.displayName }}</span>
        <button type="button" :disabled="loggingOut" @click="handleLogout">
          <i class="fa-solid fa-arrow-right-from-bracket"></i>
          <span>{{ loggingOut ? "退出中" : "退出" }}</span>
        </button>
      </div>
    </Teleport>
  </template>
</template>
