<script setup>
import * as echarts from "echarts/core";
import { BarChart, GaugeChart, HeatmapChart, LineChart, RadarChart, ScatterChart } from "echarts/charts";
import { GridComponent, LegendComponent, RadarComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

echarts.use([BarChart, GaugeChart, HeatmapChart, LineChart, RadarChart, ScatterChart, GridComponent, LegendComponent, RadarComponent, TooltipComponent, VisualMapComponent, CanvasRenderer]);

const props = defineProps({
  option: {
    type: Object,
    required: true
  }
});

const chartRef = ref(null);
const replayEventName = "creatorpulse:replay-visible-charts";
let chart = null;
let resizeObserver = null;
let renderToken = 0;
let animationTimer = null;
let animationFrame = null;
let lastPaintTime = 0;
let wasVisible = false;
let pendingRender = false;

function smoothProgress(progress) {
  return progress;
}

function interpolateArrayValue(values, progress, dimension) {
  if (dimension === "all") {
    return values.map((value) => (Number.isFinite(Number(value)) ? Number(value) * progress : value));
  }
  return values.map((value, index) => {
    if (index !== dimension || !Number.isFinite(Number(value))) return value;
    return Number(value) * progress;
  });
}

function interpolateValue(item, progress, series) {
  if (typeof item === "number") return item * progress;
  if (Array.isArray(item)) {
    return interpolateArrayValue(item, progress, series.countUpDimension ?? item.length - 1);
  }
  if (item && typeof item === "object" && Number.isFinite(Number(item.value))) {
    return { ...item, value: Number(item.value) * progress };
  }
  if (item && typeof item === "object" && Array.isArray(item.value)) {
    return {
      ...item,
      value: interpolateArrayValue(item.value, progress, series.countUpDimension ?? item.value.length - 1)
    };
  }
  return item;
}

function createFrameOption(option, progress) {
  return {
    ...option,
    animation: false,
    series: (option.series || []).map((series, index) => ({
      ...series,
      id: series.id || `series-${index}`,
      animation: false,
      data: Array.isArray(series.data) ? series.data.map((item) => interpolateValue(item, progress, series)) : series.data
    }))
  };
}

function renderChart() {
  if (!chartRef.value) return;
  if (!chart) {
    chart = echarts.init(chartRef.value, null, { renderer: "canvas" });
  }
  const token = ++renderToken;
  pendingRender = false;
  const duration = Math.max(Number(props.option.animationDurationUpdate || props.option.animationDuration || 0), 1500);
  chart.setOption(createFrameOption(props.option, 0), { notMerge: true, lazyUpdate: false });
  chart.resize();

  if (animationTimer) {
    window.clearTimeout(animationTimer);
  }
  if (animationFrame) {
    window.cancelAnimationFrame(animationFrame);
  }

  animationTimer = window.setTimeout(() => {
    const startTime = performance.now();

    function tick(now) {
      if (token !== renderToken || !chart) return;
      const rawProgress = Math.min((now - startTime) / duration, 1);
      const easedProgress = smoothProgress(rawProgress);
      if (now - lastPaintTime > 32 || rawProgress >= 1) {
        chart.setOption(createFrameOption(props.option, easedProgress), { notMerge: false, lazyUpdate: false });
        lastPaintTime = now;
      }

      if (rawProgress < 1) {
        animationFrame = window.requestAnimationFrame(tick);
        return;
      }

      chart.setOption(createFrameOption(props.option, 1), { notMerge: false, lazyUpdate: false });
      animationFrame = null;
    }

    if (token === renderToken && chart) {
      lastPaintTime = 0;
      animationFrame = window.requestAnimationFrame(tick);
    }
  }, 260);
}

function isChartVisible() {
  const element = chartRef.value;
  if (!element) return false;
  const rect = element.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

function replayIfVisible() {
  nextTick(() => {
    if (isChartVisible()) {
      renderChart();
    } else {
      pendingRender = true;
    }
  });
}

onMounted(() => {
  nextTick(() => {
    wasVisible = isChartVisible();
    if (wasVisible) {
      renderChart();
    } else {
      pendingRender = true;
    }
  });
  window.addEventListener(replayEventName, replayIfVisible);
  resizeObserver = new ResizeObserver(() => {
    nextTick(() => {
      const visible = isChartVisible();
      if (visible && (!wasVisible || pendingRender)) {
        renderChart();
      } else if (visible) {
        chart?.resize();
      }
      wasVisible = visible;
    });
  });
  resizeObserver.observe(chartRef.value);
});

watch(
  () => props.option,
  () => nextTick(() => {
    if (isChartVisible()) {
      renderChart();
    } else {
      pendingRender = true;
    }
  }),
  { deep: true }
);

onBeforeUnmount(() => {
  if (animationTimer) {
    window.clearTimeout(animationTimer);
  }
  if (animationFrame) {
    window.cancelAnimationFrame(animationFrame);
  }
  window.removeEventListener(replayEventName, replayIfVisible);
  resizeObserver?.disconnect();
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div ref="chartRef" class="chart-panel"></div>
</template>
