export function formatNumber(value) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return "--";
  if (Number(value) >= 10000) return `${(Number(value) / 10000).toFixed(1)}万`;
  return Number(value).toLocaleString("zh-CN");
}

export function formatPercent(value) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return "--";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

export function contentLabel(type) {
  return {
    TUTORIAL: "教程",
    REVIEW: "测评",
    SEEDING: "种草",
    VLOG: "Vlog",
    LIVE_CLIP: "直播切片"
  }[type] || type;
}

export function priorityClass(priority) {
  if (priority === "HIGH") return "strong";
  if (priority === "LOW") return "";
  return "warning";
}

export function sum(rows, key) {
  return rows.reduce((value, row) => value + Number(row[key] || 0), 0);
}
