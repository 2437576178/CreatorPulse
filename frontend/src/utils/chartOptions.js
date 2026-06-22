const palette = {
  green: "#bcff00",
  purple: "#9a8eff",
  cyan: "#61f4ff",
  muted: "rgba(255,255,255,0.28)",
  whiteText: "rgba(255,255,255,0.86)",
  darkText: "#111"
};

function isNumericDisplayText(value) {
  if (value === undefined || value === null) return false;
  return /^-?[\d,]+(?:\.\d+)?[万亿]?%?$/.test(String(value).trim());
}

function parseNumericDisplayText(value) {
  const text = String(value ?? "").trim();
  const match = text.match(/^(-?[\d,]+(?:\.\d+)?)([万亿]?%?)$/);
  if (!match) return null;
  return {
    number: Number(match[1].replace(/,/g, "")),
    suffix: match[2] || "",
    decimals: match[1].includes(".") ? match[1].split(".")[1].length : 0
  };
}

export function horizontalBarOption(items, options = {}) {
  const values = items.map((item) => Number(item.value || 0));
  const max = Math.max(...values, 1);
  const formatNumericLabel = (value) => {
    const numericValue = Number(value || 0);
    if (options.labelFormatter) return options.labelFormatter(numericValue);
    if (options.labelSuffix) return `${Math.round(numericValue)}${options.labelSuffix}`;
    return Math.round(numericValue).toLocaleString("zh-CN");
  };
  const shouldCountUpLabels = options.countUpLabels ?? items.every((item) => item.detail === undefined && (item.text === undefined || isNumericDisplayText(item.text)));
  const formatItemNumericLabel = (value, item) => {
    if (options.labelFormatter) return options.labelFormatter(Number(value || 0), item);
    const finalText = parseNumericDisplayText(item?.text);
    if (finalText && Number(item?.value || 0) > 0) {
      const progress = Math.max(0, Math.min(1, Number(value || 0) / Number(item.value)));
      const currentValue = finalText.number * progress;
      return `${currentValue.toFixed(finalText.decimals)}${finalText.suffix}`;
    }
    const suffix = options.labelSuffix || "";
    return `${Math.round(Number(value || 0)).toLocaleString("zh-CN")}${suffix}`;
  };
  return {
    animationDuration: options.duration || 1600,
    animationDurationUpdate: options.duration || 1600,
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter(params) {
        const item = params[0];
        const source = items[item.dataIndex];
        return `${source.label}<br/>${source.detail || item.value}`;
      }
    },
    grid: { left: 0, right: 0, top: 4, bottom: 4, containLabel: false },
    xAxis: { type: "value", show: false, max },
    yAxis: {
      type: "category",
      inverse: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      data: items.map((item) => item.label)
    },
    series: [
      {
        type: "bar",
        barWidth: options.barWidth || 34,
        itemStyle: {
          borderRadius: 8,
          color(params) {
            return items[params.dataIndex]?.color || [palette.green, palette.purple, palette.cyan, palette.green][params.dataIndex % 4];
          }
        },
        label: {
          show: true,
          position: "insideLeft",
          color: options.labelColor || palette.darkText,
          fontSize: 11,
          fontWeight: 850,
          formatter(params) {
            const source = items[params.dataIndex];
            const displayValue = shouldCountUpLabels
              ? formatItemNumericLabel(params.value, source)
              : source.text || source.detail || formatNumericLabel(params.value);
            return `${source.label} ${displayValue}`;
          }
        },
        data: values
      }
    ]
  };
}

export function verticalBarOption(items, options = {}) {
  const values = items.map((item) => Number(item.value || 0));
  const max = Math.max(...values, 1);
  const formatNumericLabel = (value) => {
    const numericValue = Number(value || 0);
    if (options.labelFormatter) return options.labelFormatter(numericValue);
    if (options.labelSuffix) return `${Math.round(numericValue)}${options.labelSuffix}`;
    return Math.round(numericValue).toLocaleString("zh-CN");
  };
  return {
    animationDuration: options.duration || 1600,
    animationDurationUpdate: options.duration || 1600,
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter(params) {
        const item = params[0];
        const source = items[item.dataIndex];
        return `${source.label}<br/>${source.detail || item.value}`;
      }
    },
    grid: { left: 0, right: 0, top: 8, bottom: 0, containLabel: false },
    xAxis: { type: "category", show: false, data: items.map((item) => item.label) },
    yAxis: { type: "value", show: false, max },
    series: [
      {
        type: "bar",
        barWidth: options.barWidth || 52,
        itemStyle: {
          borderRadius: 6,
          color(params) {
            return items[params.dataIndex]?.color || [palette.muted, palette.purple, palette.green, palette.purple, palette.muted][params.dataIndex % 5];
          }
        },
        label: {
          show: options.showLabels || false,
          position: "insideTop",
          color: options.labelColor || palette.darkText,
          fontSize: 11,
          fontWeight: 850,
          formatter(params) {
            return formatNumericLabel(params.value);
          }
        },
        data: values
      }
    ]
  };
}

export function heatmapOption(xLabels, yLabels, values, options = {}) {
  const max = Math.max(...values.map((item) => Number(item[2] || 0)), 1);
  const min = Math.min(...values.map((item) => Number(item[2] || 0)), 0);
  const labelSuffix = options.labelSuffix || "";
  return {
    animationDuration: options.duration || 1600,
    animationDurationUpdate: options.duration || 1600,
    tooltip: {
      formatter(params) {
        const [x, y, value] = params.value;
        return `${yLabels[y]} ${xLabels[x]}<br/>score ${Math.round(Number(value || 0))}${labelSuffix}`;
      }
    },
    grid: { left: 8, right: 8, top: 8, bottom: 8, containLabel: false },
    xAxis: {
      type: "category",
      data: xLabels,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: palette.whiteText, fontSize: 10 }
    },
    yAxis: {
      type: "category",
      data: yLabels,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: palette.whiteText, fontSize: 10 }
    },
    visualMap: {
      show: false,
      min,
      max,
      inRange: {
        color: options.colors || ["rgba(204, 156, 60, 0.22)", "rgba(204, 156, 60, 0.62)", "rgb(204, 156, 60)"]
      }
    },
    series: [
      {
        type: "heatmap",
        countUpDimension: 2,
        data: values,
        itemStyle: { borderRadius: 8, borderColor: "rgba(255,255,255,0.08)", borderWidth: 2 },
        label: {
          show: true,
          color: palette.darkText,
          fontSize: 10,
          fontWeight: 800,
          formatter(params) {
            const value = Number(params.value[2] || 0);
            if (options.countUpLabels) return `${Math.round(value)}${labelSuffix}`;
            return value >= max * (options.labelThreshold ?? 0.45) ? `${Math.round(value)}${labelSuffix}` : "";
          }
        }
      }
    ]
  };
}

export function bubbleOption(items, options = {}) {
  const max = Math.max(...items.map((item) => Number(item.value || 0)), 1);
  return {
    animationDuration: options.duration || 1600,
    animationDurationUpdate: options.duration || 1600,
    tooltip: {
      formatter(params) {
        const item = items[params.dataIndex];
        return `${item.label}<br/>适配度 ${item.value}<br/>热度 ${item.heat || "--"}`;
      }
    },
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: "value", show: false, min: 0, max: 100 },
    yAxis: { type: "value", show: false, min: 0, max: 100 },
    series: [
      {
        type: "scatter",
        countUpDimension: 2,
        symbolSize(value) {
          return Math.max(36, Math.min(96, value[2] / max * 96));
        },
        itemStyle: {
          color(params) {
            return items[params.dataIndex]?.color || (params.dataIndex === 0 ? palette.green : palette.purple);
          },
          opacity: 0.92
        },
        label: {
          show: true,
          color: palette.darkText,
          fontSize: 11,
          fontWeight: 850,
          formatter(params) {
            const item = items[params.dataIndex];
            if (options.countUpLabels) return `${item?.label || ""} ${Math.round(Number(params.value?.[2] || 0))}`;
            return item?.label || "";
          }
        },
        data: items.map((item, index) => [
          item.x ?? ((index % 3) * 32 + 18),
          item.y ?? (74 - Math.floor(index / 3) * 34),
          Number(item.value || 0)
        ])
      }
    ]
  };
}
