<script setup>
defineProps({
  logos: {
    type: Array,
    default: () => []
  }
});
</script>

<template>
  <div class="logo-loop" role="region" aria-label="可绑定平台与常见 App">
    <div class="logo-loop-track">
      <div v-for="copy in 3" :key="copy" class="logo-loop-list" :aria-hidden="copy > 1">
        <div v-for="logo in logos" :key="`${copy}-${logo.name}`" class="app-logo-item" :title="logo.name">
          <img class="app-logo-icon" :src="logo.src" :alt="logo.name" loading="lazy" draggable="false" />
        </div>
      </div>
    </div>
  </div>
</template>
