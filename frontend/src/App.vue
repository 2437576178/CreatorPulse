<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import AdminSimulation from "./pages/AdminSimulation.vue";
import ContentDistribution from "./pages/ContentDistribution.vue";
import CreatorOpportunities from "./pages/CreatorOpportunities.vue";
import CreatorProfile from "./pages/CreatorProfile.vue";
import FansAnalysis from "./pages/FansAnalysis.vue";
import GrowthDashboard from "./pages/GrowthDashboard.vue";
import LoginPage from "./pages/LoginPage.vue";
import { fetchMe, logout, uploadAvatar } from "./services/api";

const isAdminSimulationPath = () => window.location.pathname === "/admin/simulation";
const page = ref(isAdminSimulationPath() ? "adminSimulation" : new URLSearchParams(window.location.search).get("page") || "growth");
const checkingSession = ref(true);
const currentUser = ref(null);
const loggingOut = ref(false);
const avatarInput = ref(null);
const uploadingAvatar = ref(false);
const avatarObjectUrl = ref("");
let countUpRunId = 0;
let countUpObserver = null;
let visualLoadRunId = 0;
let chartReplayTimer = null;

const defaultHashByPage = {
  growth: "overview",
  fans: "growth",
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
  if (["growth", "fans", "content", "opportunities", "profile"].includes(page.value)) {
    return page.value;
  }
  return "growth";
});

const avatarStyle = computed(() => {
  const avatarUrl = currentUser.value?.avatarUrl || "";
  return avatarUrl ? { "--current-avatar-url": `url("${avatarUrl}")` } : {};
});

function decoratePageAvatar() {
  nextTick(() => {
    const shells = document.querySelectorAll(".page-transition-shell");
    const activeShell = shells[shells.length - 1];
    activeShell?.querySelectorAll(".board-header .user-avatar").forEach((avatar) => {
      avatar.classList.add("avatar-upload-trigger");
      avatar.setAttribute("role", "button");
      avatar.setAttribute("tabindex", "0");
      avatar.setAttribute("title", "Upload avatar");
      avatar.setAttribute("aria-label", "Upload avatar");
      avatar.onclick = openAvatarPicker;
      avatar.onkeydown = (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openAvatarPicker();
        }
      };
    });
  });
}

function updateActiveTabSlider() {
  const shells = document.querySelectorAll(".page-transition-shell");
  const activeShell = shells[shells.length - 1];
  const tabs = activeShell?.querySelector(".top-pills-tabs");
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

const countUpSelectors = [
  ".metric-card strong",
  ".value",
  ".path-step strong",
  ".bar > span",
  ".table td",
  ".tag",
  ".delta",
  ".heat-cell",
  ".bubble"
].join(",");

function getActivePageShell() {
  const shells = document.querySelectorAll(".page-transition-shell");
  return shells[shells.length - 1] || null;
}

function isCountUpCandidateVisible(element) {
  return Boolean(element.offsetWidth || element.offsetHeight || element.getClientRects().length);
}

function parseCountUpText(text) {
  const original = text.trim();
  if (!/\d/.test(original)) return null;
  if (/\d{1,2}:\d{2}/.test(original) || /\d+\s*-\s*\d+/.test(original) || /[\\/]/.test(original)) return null;
  if (original.length > 18 && !/^[\u4e00-\u9fa5]{1,6}\s*[+-]?\d/.test(original)) return null;

  const matches = [...original.matchAll(/[+-]?\d[\d,]*(?:\.\d+)?/g)];
  if (matches.length !== 1) return null;

  const match = matches[0];
  const numericText = match[0];
  const start = match.index;
  const end = start + numericText.length;
  const rawValue = Number(numericText.replace(/[+,]/g, ""));
  if (!Number.isFinite(rawValue)) return null;

  const decimals = numericText.includes(".") ? numericText.split(".")[1].length : 0;
  const hasPlus = numericText.startsWith("+");
  const before = original.slice(0, start);
  const after = original.slice(end);

  return {
    target: rawValue,
    decimals,
    hasPlus,
    before,
    after,
    original
  };
}

function formatCountUpValue(current, descriptor) {
  const value = descriptor.target < 0 ? -current : current;
  const absText = descriptor.decimals > 0
    ? Math.abs(value).toFixed(descriptor.decimals)
    : Math.round(Math.abs(value)).toLocaleString("zh-CN");
  const sign = descriptor.target < 0 ? "-" : descriptor.hasPlus ? "+" : "";
  return `${descriptor.before}${sign}${absText}${descriptor.after}`;
}

function animateCountUpElement(element, descriptor) {
  if (element.dataset.countUpTarget === descriptor.original || element.dataset.countUpAnimating === "true") {
    return;
  }

  element.dataset.countUpTarget = descriptor.original;
  element.dataset.countUpAnimating = "true";
  element.classList.add("count-up-number");

  const target = Math.abs(descriptor.target);
  const duration = 980;
  const startTime = performance.now();

  function tick(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    element.textContent = formatCountUpValue(target * eased, descriptor);

    if (progress < 1) {
      window.requestAnimationFrame(tick);
      return;
    }

    element.textContent = descriptor.original;
    element.dataset.countUpAnimating = "false";
  }

  element.textContent = formatCountUpValue(0, descriptor);
  window.requestAnimationFrame(tick);
}

function animateNumericStyle(element, propertyName, targetValue, unit = "") {
  const target = Number(targetValue);
  if (!Number.isFinite(target)) return;
  const targetKey = `${propertyName}:${target}${unit}`;
  if (element.dataset.visualLoadTarget === targetKey) return;

  element.dataset.visualLoadTarget = targetKey;
  element.classList.add("visual-load-number");
  element.style[propertyName] = `0${unit}`;

  window.requestAnimationFrame(() => {
    element.style[propertyName] = `${target}${unit}`;
  });
}

function animateDashArray(circle) {
  const dashArray = circle.getAttribute("stroke-dasharray") || "";
  const match = dashArray.match(/^([+-]?\d+(?:\.\d+)?)\s+(.+)$/);
  if (!match) return;

  const target = Number(match[1]);
  if (!Number.isFinite(target)) return;
  const rest = match[2];
  const targetKey = `dash:${target} ${rest}`;
  if (circle.dataset.visualLoadTarget === targetKey) return;

  circle.dataset.visualLoadTarget = targetKey;
  circle.classList.add("visual-load-stroke");
  circle.setAttribute("stroke-dasharray", `0 ${rest}`);

  window.requestAnimationFrame(() => {
    circle.setAttribute("stroke-dasharray", `${target} ${rest}`);
  });
}

function animateDecorativeVisual(element, targetKey) {
  if (element.dataset.visualLoadTarget === targetKey) return;
  element.dataset.visualLoadTarget = targetKey;
  element.classList.add("visual-load-pop");
  element.style.opacity = "0";
  element.style.transform = "scale(0.72)";

  window.requestAnimationFrame(() => {
    element.style.opacity = "";
    element.style.transform = "";
  });
}

function runVisualLoadScan(shell) {
  const activeShell = shell || getActivePageShell();
  if (!activeShell) return;

  activeShell.querySelectorAll(".bar > span").forEach((bar) => {
    const targetWidth = bar.style.width;
    const match = targetWidth.match(/^([+-]?\d+(?:\.\d+)?)%$/);
    if (match) {
      animateNumericStyle(bar, "width", match[1], "%");
    }
  });

  activeShell.querySelectorAll(".mini-bars span").forEach((bar) => {
    const targetHeight = bar.style.height;
    const match = targetHeight.match(/^([+-]?\d+(?:\.\d+)?)px$/);
    if (match) {
      animateNumericStyle(bar, "height", match[1], "px");
    }
  });

  activeShell.querySelectorAll("circle[stroke-dasharray]").forEach(animateDashArray);

  activeShell.querySelectorAll(".bubble").forEach((bubble) => {
    animateDecorativeVisual(bubble, `bubble:${bubble.textContent.trim()}:${bubble.style.getPropertyValue("--s")}`);
  });

  activeShell.querySelectorAll(".heat-cell.hot, .heat-cell.mid").forEach((cell) => {
    animateDecorativeVisual(cell, `heat:${cell.textContent.trim()}:${cell.className}`);
  });
}

function runCountUpScan(shell) {
  const activeShell = shell || getActivePageShell();
  if (!activeShell) return 0;

  let animatedCount = 0;
  activeShell.querySelectorAll(countUpSelectors).forEach((element) => {
    if (animatedCount >= 80) return;
    if (!isCountUpCandidateVisible(element)) return;
    const descriptor = parseCountUpText(element.textContent || "");
    if (!descriptor) return;
    animateCountUpElement(element, descriptor);
    animatedCount += 1;
  });
  return animatedCount;
}

function scheduleCountUpNumbers() {
  const shell = getActivePageShell();
  const runId = ++countUpRunId;
  const visualRunId = ++visualLoadRunId;
  if (countUpObserver) {
    countUpObserver.disconnect();
    countUpObserver = null;
  }

  nextTick(() => {
    const activeShell = shell || getActivePageShell();
    if (!activeShell || runId !== countUpRunId) return;

    [80, 220, 480, 860, 1320].forEach((delay) => {
      window.setTimeout(() => {
        if (runId === countUpRunId) {
          runCountUpScan(activeShell);
        }
        if (visualRunId === visualLoadRunId) {
          runVisualLoadScan(activeShell);
        }
      }, delay);
    });

    countUpObserver = new MutationObserver(() => {
      if (runId === countUpRunId) {
        window.requestAnimationFrame(() => {
          runCountUpScan(activeShell);
          if (visualRunId === visualLoadRunId) {
            runVisualLoadScan(activeShell);
          }
        });
      }
    });
    countUpObserver.observe(activeShell, { childList: true, subtree: true, characterData: true });

    window.setTimeout(() => {
      if (runId === countUpRunId && countUpObserver) {
        countUpObserver.disconnect();
        countUpObserver = null;
      }
    }, 1800);
  });
}

function scheduleVisibleChartReplay() {
  if (chartReplayTimer) {
    window.clearTimeout(chartReplayTimer);
  }

  chartReplayTimer = window.setTimeout(() => {
    window.dispatchEvent(new CustomEvent("creatorpulse:replay-visible-charts"));
    chartReplayTimer = null;
  }, 120);
}

function decorateTopNavigation() {
  nextTick(() => {
    decoratePageAvatar();
    updateActiveTabSlider();
    scheduleCountUpNumbers();
  });
}

function handleHashChange() {
  window.requestAnimationFrame(updateActiveTabSlider);
  scheduleCountUpNumbers();
  scheduleVisibleChartReplay();
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
  if (countUpObserver) {
    countUpObserver.disconnect();
    countUpObserver = null;
  }
  if (chartReplayTimer) {
    window.clearTimeout(chartReplayTimer);
    chartReplayTimer = null;
  }
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
    window.alert("Please choose an image file.");
    return;
  }
  if (file.size > 2 * 1024 * 1024) {
    window.alert("Avatar image must be 2MB or smaller.");
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
    window.alert(error.message || "Avatar upload failed.");
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
    <div v-else class="page-transition-stage" :style="avatarStyle">
      <Transition name="page-fade-slide">
        <div :key="currentPage" class="page-transition-shell">
          <GrowthDashboard v-if="currentPage === 'growth'" :active-page="currentPage" @navigate="setPage" />
          <FansAnalysis v-else-if="currentPage === 'fans'" :active-page="currentPage" @navigate="setPage" />
          <ContentDistribution v-else-if="currentPage === 'content'" :active-page="currentPage" @navigate="setPage" />
          <CreatorOpportunities v-else-if="currentPage === 'opportunities'" :active-page="currentPage" @navigate="setPage" />
          <CreatorProfile v-else :active-page="currentPage" @navigate="setPage" />
          <div class="session-bar" aria-label="当前登录账号">
            <span>{{ currentUser.displayName }}</span>
            <button type="button" :disabled="loggingOut" @click="handleLogout">
              <i class="fa-solid fa-arrow-right-from-bracket"></i>
              <span>{{ loggingOut ? "退出中" : "退出" }}</span>
            </button>
          </div>
        </div>
      </Transition>
    </div>
  </template>
</template>
