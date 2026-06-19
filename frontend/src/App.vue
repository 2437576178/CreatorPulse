<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import AdminSimulation from "./pages/AdminSimulation.vue";
import ContentDistribution from "./pages/ContentDistribution.vue";
import CreatorOpportunities from "./pages/CreatorOpportunities.vue";
import CreatorProfile from "./pages/CreatorProfile.vue";
import FansAnalysis from "./pages/FansAnalysis.vue";
import GrowthDashboard from "./pages/GrowthDashboard.vue";
import LoginPage from "./pages/LoginPage.vue";
import VideoAnalysis from "./pages/VideoAnalysis.vue";
import { fetchMe, logout, uploadAvatar } from "./services/api";

const isAdminSimulationPath = () => window.location.pathname === "/admin/simulation";
const page = ref(isAdminSimulationPath() ? "adminSimulation" : new URLSearchParams(window.location.search).get("page") || "growth");
const checkingSession = ref(true);
const currentUser = ref(null);
const loggingOut = ref(false);
const avatarInput = ref(null);
const uploadingAvatar = ref(false);
const avatarObjectUrl = ref("");

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

const avatarStyle = computed(() => {
  const avatarUrl = currentUser.value?.avatarUrl || "";
  return avatarUrl ? { backgroundImage: `url("${avatarUrl}")` } : {};
});

function decoratePageAvatar() {
  nextTick(() => {
    const avatar = document.querySelector(".board-header .user-avatar");
    if (!avatar) return;
    avatar.classList.add("avatar-upload-trigger");
    avatar.setAttribute("role", "button");
    avatar.setAttribute("tabindex", "0");
    avatar.setAttribute("title", "上传头像");
    avatar.setAttribute("aria-label", "上传头像");
    Object.assign(avatar.style, avatarStyle.value);
    avatar.onclick = openAvatarPicker;
    avatar.onkeydown = (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openAvatarPicker();
      }
    };
  });
}

function updateActiveTabSlider() {
  const tabs = document.querySelector(".top-pills-tabs");
  if (!tabs) return;

  let slider = tabs.querySelector(".tab-slider");
  if (!slider) {
    slider = document.createElement("span");
    slider.className = "tab-slider";
    tabs.prepend(slider);
  }

  const activeTab = tabs.querySelector(".top-pill.active");
  if (!activeTab) return;

  const tabsRect = tabs.getBoundingClientRect();
  const activeRect = activeTab.getBoundingClientRect();
  slider.style.width = `${activeRect.width}px`;
  slider.style.left = `${activeRect.left - tabsRect.left}px`;
}

function decorateTopNavigation() {
  nextTick(() => {
    decoratePageAvatar();
    updateActiveTabSlider();
  });
}

function handleHashChange() {
  window.requestAnimationFrame(updateActiveTabSlider);
}

onMounted(async () => {
  window.addEventListener("hashchange", handleHashChange);
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
    decorateTopNavigation();
  }
});

onUnmounted(() => {
  window.removeEventListener("hashchange", handleHashChange);
});

watch([currentPage, avatarStyle], decorateTopNavigation, { flush: "post" });

function setAuthenticatedUser(user) {
  currentUser.value = user;
  if (isAdminSimulationPath()) {
    page.value = "adminSimulation";
  } else {
    resetToHome();
  }
}

function openAvatarPicker() {
  if (uploadingAvatar.value) return;
  avatarInput.value?.click();
}

async function handleAvatarFileChange(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    window.alert("请选择图片文件");
    return;
  }
  if (file.size > 2 * 1024 * 1024) {
    window.alert("头像图片不能超过 2MB");
    return;
  }

  if (avatarObjectUrl.value) {
    URL.revokeObjectURL(avatarObjectUrl.value);
  }
  avatarObjectUrl.value = URL.createObjectURL(file);
  currentUser.value = { ...currentUser.value, avatarUrl: avatarObjectUrl.value };
  uploadingAvatar.value = true;

  try {
    const payload = await uploadAvatar(file);
    currentUser.value = payload.user;
  } catch (error) {
    window.alert(error.message || "头像上传失败");
    const payload = await fetchMe();
    currentUser.value = payload.user;
  } finally {
    uploadingAvatar.value = false;
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
    <input ref="avatarInput" class="avatar-upload-input" type="file" accept="image/png,image/jpeg,image/webp" @change="handleAvatarFileChange" />
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
