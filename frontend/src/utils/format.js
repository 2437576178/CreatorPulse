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

export function platformLabel(platform) {
  return {
    DOUYIN: "抖音",
    BILIBILI: "B站",
    XIAOHONGSHU: "小红书",
    KUAISHOU: "快手",
    WEIBO: "微博",
    ZUIYOU: "最右",
    QQ: "QQ",
    WECHAT: "微信",
    NETEASE_CLOUD_MUSIC: "网易云",
    ALL: "全平台",
    MULTI: "多平台"
  }[platform] || platform;
}

export function lifecycleLabel(stage) {
  return {
    BURST: "爆发期",
    STABLE: "稳定期",
    LONG_TAIL: "长尾期",
    SECONDARY_BOOST: "二次推荐",
    DECLINING: "衰退期"
  }[stage] || stage;
}

export function priorityClass(priority) {
  if (priority === "HIGH") return "strong";
  if (priority === "LOW") return "";
  return "warning";
}

export function sum(rows, key) {
  return rows.reduce((value, row) => value + Number(row[key] || 0), 0);
}

export function average(rows, key) {
  if (!rows.length) return 0;
  return sum(rows, key) / rows.length;
}
