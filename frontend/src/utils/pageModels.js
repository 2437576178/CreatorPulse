export function groupInsights(insights, tabs, prefix) {
  const grouped = Object.fromEntries(tabs.map((tab) => [tab.id, []]));
  for (const insight of insights || []) {
    for (const target of insight.pageTargets || []) {
      for (const tab of tabs) {
        if (target === `${prefix}.${tab.id}`) {
          grouped[tab.id].push(insight);
        }
      }
    }
  }
  return grouped;
}

export function firstAction(insight) {
  return insight?.recommendedActions?.[0]?.description || insight?.summary || "";
}

export function actionsFrom(insights, limit = 4) {
  return (insights || []).flatMap((insight) => insight.recommendedActions || []).slice(0, limit);
}

export function diagnosisItems(insights, fallbackItems = []) {
  const normalized = (insights || []).slice(0, 3).map((insight, index) => ({
    key: insight.insightId || `${insight.title}-${index}`,
    label: insight.scope || insight.type || fallbackItems[index]?.label || "判断",
    title: insight.title,
    className: index === 0 ? "strong" : index === 1 ? "warning" : ""
  }));

  for (let index = normalized.length; index < 3; index += 1) {
    const fallback = fallbackItems[index] || {};
    normalized.push({
      key: fallback.key || `fallback-${index}`,
      label: fallback.label || "判断",
      title: fallback.title || "继续按当前高价值内容结构执行",
      className: fallback.className ?? (index === 0 ? "strong" : index === 1 ? "warning" : "")
    });
  }

  return normalized;
}

export function pairVideosWithSnapshots(videos = [], snapshots = []) {
  const videosById = Object.fromEntries(videos.map((video) => [video.videoId, video]));
  return snapshots.map((snapshot) => ({
    ...snapshot,
    ...(videosById[snapshot.videoId] || {})
  }));
}

export function aggregateBy(rows, key, metrics) {
  const result = {};
  for (const row of rows || []) {
    const group = row[key] || "UNKNOWN";
    result[group] ||= { key: group };
    for (const metric of metrics) {
      result[group][metric] = (result[group][metric] || 0) + Number(row[metric] || 0);
    }
  }
  return Object.values(result);
}

export function topRows(rows, key, limit = 5) {
  return [...(rows || [])].sort((a, b) => Number(b[key] || 0) - Number(a[key] || 0)).slice(0, limit);
}
