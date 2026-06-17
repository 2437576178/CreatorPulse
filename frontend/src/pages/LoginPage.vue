<script setup>
import { computed, ref } from "vue";
import { login, registerAccount } from "../services/api";

const emit = defineEmits(["authenticated"]);

const mode = ref("login");
const email = ref("demo@creatorpulse.local");
const password = ref("demo123456");
const displayName = ref("");
const selectedPlatforms = ref(["DOUYIN", "BILIBILI", "XIAOHONGSHU"]);
const loading = ref(false);
const error = ref("");

const platformOptions = [
  { value: "DOUYIN", label: "抖音", icon: "fa-music" },
  { value: "BILIBILI", label: "B站", icon: "fa-play" },
  { value: "XIAOHONGSHU", label: "小红书", icon: "fa-book-open" }
];

const isRegister = computed(() => mode.value === "register");

function switchMode(nextMode) {
  mode.value = nextMode;
  error.value = "";
  if (nextMode === "login") {
    email.value = "demo@creatorpulse.local";
    password.value = "demo123456";
  } else {
    email.value = "";
    password.value = "";
    displayName.value = "";
    selectedPlatforms.value = ["DOUYIN", "BILIBILI", "XIAOHONGSHU"];
  }
}

function togglePlatform(platform) {
  if (selectedPlatforms.value.includes(platform)) {
    selectedPlatforms.value = selectedPlatforms.value.filter((item) => item !== platform);
    return;
  }
  selectedPlatforms.value = [...selectedPlatforms.value, platform];
}

async function submitAccount() {
  loading.value = true;
  error.value = "";
  try {
    const payload = isRegister.value
      ? await registerAccount({
          email: email.value,
          password: password.value,
          displayName: displayName.value,
          platforms: selectedPlatforms.value
        })
      : await login(email.value, password.value);
    emit("authenticated", payload.user);
  } catch (accountError) {
    error.value = accountError.message;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="login-shell">
    <section class="login-panel">
      <article class="login-hero">
        <div>
          <div class="brand-logo"><i class="fa-solid fa-circle-notch"></i> CreatorPulse</div>
          <p class="eyebrow">Creator Account</p>
          <h1>{{ isRegister ? "创建你的达人数据空间" : "登录你的达人账号" }}</h1>
          <p class="page-copy">
            每个账号只读取自己的 creator_id。注册时选择要模拟绑定的平台，系统会自动生成初始数据，并进入同一条 Flume、Kafka、Spark 数据链路。
          </p>
        </div>
        <div class="login-signal">
          <span></span>
          <strong>User -> Creator ID -> Platform Bindings</strong>
          <em>登录后页面只展示你的账号数据</em>
        </div>
      </article>

      <form class="login-card" @submit.prevent="submitAccount">
        <div class="login-mode-toggle" role="tablist" aria-label="账号模式">
          <button type="button" :class="{ active: !isRegister }" @click="switchMode('login')">登录</button>
          <button type="button" :class="{ active: isRegister }" @click="switchMode('register')">注册</button>
        </div>

        <p class="section-label">{{ isRegister ? "新账号注册" : "账号登录" }}</p>
        <label v-if="isRegister">
          <span>达人名称</span>
          <input v-model="displayName" type="text" autocomplete="name" required />
        </label>
        <label>
          <span>邮箱</span>
          <input v-model="email" type="email" autocomplete="username" required />
        </label>
        <label>
          <span>密码</span>
          <input v-model="password" type="password" :autocomplete="isRegister ? 'new-password' : 'current-password'" required />
        </label>

        <div v-if="isRegister" class="platform-picker" aria-label="选择模拟绑定平台">
          <span>绑定平台</span>
          <div class="platform-picker-grid">
            <button
              v-for="platform in platformOptions"
              :key="platform.value"
              type="button"
              :class="{ active: selectedPlatforms.includes(platform.value) }"
              @click="togglePlatform(platform.value)"
            >
              <i class="fa-solid" :class="platform.icon"></i>
              <strong>{{ platform.label }}</strong>
            </button>
          </div>
        </div>

        <button class="login-button" type="submit" :disabled="loading">
          <i class="fa-solid" :class="isRegister ? 'fa-user-plus' : 'fa-arrow-right-to-bracket'"></i>
          <span>{{ loading ? "处理中" : isRegister ? "创建账号" : "登录" }}</span>
        </button>
        <p v-if="error" class="login-error">{{ error }}</p>
        <div class="login-demo">
          <span>Demo 账号</span>
          <strong>demo@creatorpulse.local</strong>
          <em>demo123456</em>
        </div>
      </form>
    </section>
  </main>
</template>
