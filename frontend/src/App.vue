<script setup>
import { computed, ref } from "vue";
import FansAnalysis from "./pages/FansAnalysis.vue";
import GrowthDashboard from "./pages/GrowthDashboard.vue";

const page = ref(new URLSearchParams(window.location.search).get("page") || "growth");

function setPage(nextPage) {
  page.value = nextPage;
  const url = new URL(window.location.href);
  url.hash = nextPage === "fans" ? "growth" : "overview";
  if (nextPage === "growth") {
    url.searchParams.delete("page");
  } else {
    url.searchParams.set("page", nextPage);
  }
  window.history.pushState({}, "", url);
}

const currentPage = computed(() => (page.value === "fans" ? "fans" : "growth"));
</script>

<template>
  <GrowthDashboard v-if="currentPage === 'growth'" :active-page="currentPage" @navigate="setPage" />
  <FansAnalysis v-else :active-page="currentPage" @navigate="setPage" />
</template>
