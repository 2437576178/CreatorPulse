<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  texts: {
    type: Array,
    default: () => []
  },
  rotationInterval: {
    type: Number,
    default: 2200
  }
});

const currentIndex = ref(0);
let timer = null;

const currentText = computed(() => props.texts[currentIndex.value] || "");

const characters = computed(() => {
  if (typeof Intl !== "undefined" && Intl.Segmenter) {
    const segmenter = new Intl.Segmenter("zh", { granularity: "grapheme" });
    return Array.from(segmenter.segment(currentText.value), (item) => item.segment);
  }
  return Array.from(currentText.value);
});

function startRotation() {
  window.clearInterval(timer);
  if (props.texts.length < 2) return;
  timer = window.setInterval(() => {
    currentIndex.value = (currentIndex.value + 1) % props.texts.length;
  }, props.rotationInterval);
}

watch(
  () => props.texts,
  () => {
    currentIndex.value = 0;
    startRotation();
  },
  { deep: true }
);

onMounted(startRotation);
onBeforeUnmount(() => window.clearInterval(timer));
</script>

<template>
  <span class="rotating-text" aria-live="polite">
    <span class="rotating-text-sr">{{ currentText }}</span>
    <span :key="currentText" class="rotating-text-line" aria-hidden="true">
      <span
        v-for="(character, index) in characters"
        :key="`${currentText}-${index}`"
        class="rotating-text-char"
        :style="{ animationDelay: `${index * 26}ms` }"
      >
        {{ character }}
      </span>
    </span>
  </span>
</template>
