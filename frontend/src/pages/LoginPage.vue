<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import bilibiliIcon from "../assets/app-icons/bilibili.png";
import douyinIcon from "../assets/app-icons/douyin.png";
import kuaishouIcon from "../assets/app-icons/kuaishou.png";
import neteaseCloudMusicIcon from "../assets/app-icons/netease-cloud-music.png";
import qqIcon from "../assets/app-icons/qq.png";
import wechatIcon from "../assets/app-icons/wechat.png";
import weiboIcon from "../assets/app-icons/weibo.png";
import xiaohongshuIcon from "../assets/app-icons/xiaohongshu.png";
import zuiyouIcon from "../assets/app-icons/zuiyou.png";
import LogoLoop from "../components/LogoLoop.vue";
import RotatingText from "../components/RotatingText.vue";
import { fetchPlatforms, login, registerAccount } from "../services/api";

const emit = defineEmits(["authenticated"]);

const mode = ref("login");
const email = ref("");
const password = ref("");
const displayName = ref("");
const selectedPlatforms = ref(["DOUYIN", "BILIBILI", "XIAOHONGSHU"]);
const loading = ref(false);
const error = ref("");
const successMessage = ref("");
let toastTimer = null;

const toastMessage = computed(() => successMessage.value || error.value);
const toastType = computed(() => (successMessage.value ? "success" : "error"));

const fallbackPlatformOptions = [
  { value: "DOUYIN", label: "抖音", iconSrc: douyinIcon },
  { value: "BILIBILI", label: "B站", iconSrc: bilibiliIcon },
  { value: "XIAOHONGSHU", label: "小红书", iconSrc: xiaohongshuIcon }
];
const platformOptions = ref([...fallbackPlatformOptions]);
const platformIconMap = {
  DOUYIN: douyinIcon,
  BILIBILI: bilibiliIcon,
  XIAOHONGSHU: xiaohongshuIcon,
  KUAISHOU: kuaishouIcon,
  WEIBO: weiboIcon
};
const appLogos = [
  { name: "小红书", src: xiaohongshuIcon },
  { name: "抖音", src: douyinIcon },
  { name: "快手", src: kuaishouIcon },
  { name: "微博", src: weiboIcon },
  { name: "哔哩哔哩", src: bilibiliIcon },
  { name: "最右", src: zuiyouIcon },
  { name: "QQ", src: qqIcon },
  { name: "微信", src: wechatIcon },
  { name: "网易云", src: neteaseCloudMusicIcon }
];

const isRegister = computed(() => mode.value === "register");
const allPlatformsSelected = computed(
  () => platformOptions.value.length > 0 && selectedPlatforms.value.length === platformOptions.value.length
);
const heroLead = computed(() => (isRegister.value ? "创建你的" : "登录你的"));
const heroRotatingTexts = computed(() =>
  isRegister.value
    ? ["达人数据空间"]
    : ["达人账号"]
);

function clearAccountFields() {
  email.value = "";
  password.value = "";
}

function clearToastTimer() {
  window.clearTimeout(toastTimer);
  toastTimer = null;
}

function hideToast() {
  clearToastTimer();
  error.value = "";
  successMessage.value = "";
}

function scheduleToastDismiss() {
  clearToastTimer();
  toastTimer = window.setTimeout(hideToast, 15000);
}

onMounted(() => {
  clearAccountFields();
  window.setTimeout(clearAccountFields, 150);
  loadPlatforms();
});

onBeforeUnmount(clearToastTimer);

async function loadPlatforms() {
  try {
    const payload = await fetchPlatforms();
    const enabledPlatforms = (payload.platforms || []).filter((platform) => platform.enabled);
    if (enabledPlatforms.length) {
      platformOptions.value = enabledPlatforms.map((platform) => ({
        ...platform,
        iconSrc: platformIconMap[platform.value]
      }));
      selectedPlatforms.value = enabledPlatforms.map((platform) => platform.value);
    }
  } catch {
    platformOptions.value = [...fallbackPlatformOptions];
    selectedPlatforms.value = fallbackPlatformOptions.map((platform) => platform.value);
  }
}

function switchMode(nextMode) {
  mode.value = nextMode;
  hideToast();
  if (nextMode === "login") {
    clearAccountFields();
  } else {
    clearAccountFields();
    displayName.value = "";
    selectedPlatforms.value = platformOptions.value.map((platform) => platform.value);
  }
}

function togglePlatform(platform) {
  if (selectedPlatforms.value.includes(platform)) {
    selectedPlatforms.value = selectedPlatforms.value.filter((item) => item !== platform);
    return;
  }
  selectedPlatforms.value = [...selectedPlatforms.value, platform];
}

function toggleAllPlatforms() {
  selectedPlatforms.value = allPlatformsSelected.value ? [] : platformOptions.value.map((platform) => platform.value);
}

function toChineseAuthMessage(message) {
  const normalizedMessage = String(message || "").toLowerCase();
  if (normalizedMessage.includes("already registered")) {
    return "该邮箱已注册，请直接登录或更换邮箱。";
  }
  if (normalizedMessage.includes("invalid email or password")) {
    return "邮箱或密码错误，请重新输入。";
  }
  if (normalizedMessage.includes("email and password are required")) {
    return "请输入邮箱和密码。";
  }
  if (normalizedMessage.includes("platforms must be a list")) {
    return "平台选择异常，请重新选择绑定平台。";
  }
  if (normalizedMessage.includes("register failed")) {
    return "注册失败，请稍后重试。";
  }
  if (normalizedMessage.includes("login failed")) {
    return "登录失败，请稍后重试。";
  }
  if (normalizedMessage.includes("failed to fetch") || normalizedMessage.includes("network")) {
    return "网络连接失败，请确认后端服务已启动。";
  }
  return message || "操作失败，请稍后重试。";
}

async function submitAccount() {
  loading.value = true;
  hideToast();
  try {
    if (isRegister.value) {
      await registerAccount({
        email: email.value,
        password: password.value,
        displayName: displayName.value,
        platforms: selectedPlatforms.value
      });
      mode.value = "login";
      displayName.value = "";
      password.value = "";
      successMessage.value = "注册成功，请使用刚创建的账号登录。";
      scheduleToastDismiss();
      return;
    }

    const payload = await login(email.value, password.value);
    emit("authenticated", payload.user);
  } catch (accountError) {
    error.value = toChineseAuthMessage(accountError.message);
    scheduleToastDismiss();
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="login-shell">
    <section class="login-panel" :class="{ register: isRegister }">
      <article class="login-hero">
        <div>
          <div class="brand-logo"><i class="fa-solid fa-circle-notch"></i> CreatorPulse</div>
          <p class="eyebrow">Creator Account</p>
          <h1 class="login-title">
            <span>{{ heroLead }}</span>
            <RotatingText :texts="heroRotatingTexts" />
          </h1>
          <p class="page-copy">
            平台开放 API 实时采集播放、点赞、评论、分享、收藏、粉丝变化、弹幕，您的私人账号智能分析推荐平台。
          </p>
        </div>
        <LogoLoop :logos="appLogos" />
        <div class="login-signal">
          <span></span>
          <strong>多平台数据 · 粉丝增长 · 热点推荐</strong>
          <em>评估您的账号健康度并提供专属建议</em>
        </div>
      </article>

      <form class="login-card" autocomplete="off" @submit.prevent="submitAccount">
        <input class="autofill-decoy" type="text" name="username" autocomplete="username" tabindex="-1" aria-hidden="true" />
        <input class="autofill-decoy" type="password" name="password" autocomplete="current-password" tabindex="-1" aria-hidden="true" />
        <div class="login-mode-toggle" role="tablist" aria-label="账号模式">
          <button type="button" :class="{ active: !isRegister }" @click="switchMode('login')">登录</button>
          <button type="button" :class="{ active: isRegister }" @click="switchMode('register')">注册</button>
        </div>

        <p class="section-label">{{ isRegister ? "新账号注册" : "账号登录" }}</p>
        <div class="mode-collapse" :class="{ open: isRegister }">
          <div class="mode-collapse-inner">
            <label>
            <span>达人名称</span>
            <input v-model="displayName" :class="{ filled: displayName }" type="text" autocomplete="name" :required="isRegister" />
            </label>
          </div>
        </div>
        <label>
          <span>邮箱</span>
          <input v-model="email" :class="{ filled: email }" type="email" autocomplete="off" name="creatorpulse-email" required />
        </label>
        <label>
          <span>密码</span>
          <input v-model="password" :class="{ filled: password }" type="password" autocomplete="new-password" name="creatorpulse-password" required />
        </label>


        <div class="mode-collapse" :class="{ open: isRegister }">
          <div class="mode-collapse-inner">
            <div class="platform-picker" aria-label="选择模拟绑定平台">
              <div class="platform-picker-head">
                <span>绑定平台</span>
                <label class="select-all-platforms">
                  <input type="checkbox" :checked="allPlatformsSelected" @change="toggleAllPlatforms" />
                </label>
              </div>
              <small>当前 MVP 只开放已打通数据链路的平台。</small>
              <div class="platform-picker-grid">
                <button
                  v-for="platform in platformOptions"
                  :key="platform.value"
                  type="button"
                  :class="{ active: selectedPlatforms.includes(platform.value) }"
                  @click="togglePlatform(platform.value)"
                >
                  <span class="platform-icon-wrap">
                    <img v-if="platform.iconSrc" :src="platform.iconSrc" :alt="platform.label" draggable="false" />
                    <i v-else class="fa-solid" :class="platform.icon"></i>
                    <span class="platform-check"><i class="fa-solid fa-check"></i></span>
                  </span>
                  <strong>{{ platform.label }}</strong>
                </button>
              </div>
            </div>
          </div>
        </div>

        <button class="login-button" type="submit" :disabled="loading">
          <i class="fa-solid" :class="isRegister ? 'fa-user-plus' : 'fa-arrow-right-to-bracket'"></i>
          <span>{{ loading ? "处理中" : isRegister ? "创建账号" : "登录" }}</span>
        </button>
      </form>
    </section>
    <Teleport to="body">
      <Transition name="login-toast">
        <div v-if="toastMessage" class="login-toast" :class="toastType" role="status">
          <span class="login-toast-glow" aria-hidden="true"></span>
          <i class="fa-solid" :class="toastType === 'success' ? 'fa-circle-check' : 'fa-circle-exclamation'"></i>
          <span class="login-toast-text">{{ toastMessage }}</span>
          <button type="button" class="login-toast-close" aria-label="关闭提示" @click="hideToast">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>
      </Transition>
    </Teleport>
  </main>
</template>
