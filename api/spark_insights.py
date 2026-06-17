"""Rule-based insights derived from Spark aggregate outputs."""

from __future__ import annotations

from typing import Any


def build_spark_insights(data: dict[str, Any]) -> list[dict[str, Any]]:
    outputs = data.get("sparkOutputs") or {}
    platform_rows = outputs.get("platformMetricSummaries") or []
    contribution_rows = outputs.get("videoFollowerContributions") or []
    generated_at = data.get("meta", {}).get("generatedAt") or ""
    creator_id = data.get("creator", {}).get("creatorId") or "creator_001"

    insights: list[dict[str, Any]] = []

    if platform_rows:
        top_platform = max(platform_rows, key=lambda item: item.get("newFollowers", 0))
        insights.append(
            {
                "insightId": "insight_spark_platform_efficiency",
                "creatorId": creator_id,
                "type": "OPPORTUNITY",
                "scope": "SPARK_PLATFORM",
                "targetId": top_platform["platform"],
                "title": "Spark 聚合显示一个平台正在贡献最多新粉",
                "summary": f"{top_platform['platform']} 当前贡献 {top_platform['newFollowers']} 个新粉，转粉率 {top_platform['conversionRate']:.2%}，适合作为下周内容配比的优先参考。",
                "priority": "HIGH",
                "evidenceMetrics": [
                    {
                        "label": "平台新粉",
                        "value": top_platform["newFollowers"],
                        "unit": "followers",
                        "direction": "UP",
                    },
                    {
                        "label": "平台转粉率",
                        "value": top_platform["conversionRate"],
                        "unit": "rate",
                        "direction": "UP",
                    },
                ],
                "recommendedActions": [
                    {
                        "actionId": "action_spark_platform_efficiency_01",
                        "title": "调整下周平台配比",
                        "description": "把高转粉平台的教程和测评内容排到主发布窗口，减少低转粉泛流量内容占用。",
                        "expectedImpact": "提升平台投入效率",
                        "relatedPage": "content.platform",
                    }
                ],
                "generatedBy": "SPARK_RULE_ENGINE",
                "generatedAt": generated_at,
                "pageTargets": ["content.platform", "growth.distribution"],
            }
        )

    if contribution_rows:
        top_video = min(contribution_rows, key=lambda item: item.get("rankPosition", 9999))
        insights.append(
            {
                "insightId": "insight_spark_video_contribution",
                "creatorId": creator_id,
                "type": "ACTION",
                "scope": "SPARK_VIDEO",
                "targetId": top_video["videoId"],
                "title": "Spark 排名识别出最值得复刻的涨粉视频",
                "summary": f"《{top_video['title']}》排名第 {top_video['rankPosition']}，带来 {top_video['newFollowers']} 个新粉，转粉率 {top_video['conversionRate']:.2%}。",
                "priority": "HIGH",
                "evidenceMetrics": [
                    {
                        "label": "视频新粉",
                        "value": top_video["newFollowers"],
                        "unit": "followers",
                        "direction": "UP",
                    },
                    {
                        "label": "视频转粉率",
                        "value": top_video["conversionRate"],
                        "unit": "rate",
                        "direction": "UP",
                    },
                ],
                "recommendedActions": [
                    {
                        "actionId": "action_spark_video_contribution_01",
                        "title": "复刻高转粉结构",
                        "description": "保留这条视频的选题、开头承诺和主页承接方式，做一条同系列内容测试复现。",
                        "expectedImpact": "提升下一条内容的关注转化",
                        "relatedPage": "video.contribution",
                    }
                ],
                "generatedBy": "SPARK_RULE_ENGINE",
                "generatedAt": generated_at,
                "pageTargets": ["video.contribution", "opportunities.reference"],
            }
        )

    return insights


def merge_spark_insights(data: dict[str, Any]) -> dict[str, Any]:
    existing = data.get("insights") or []
    generated = build_spark_insights(data)
    generated_ids = {item["insightId"] for item in generated}
    without_stale_generated = [item for item in existing if item.get("insightId") not in generated_ids]
    return {**data, "insights": [*without_stale_generated, *generated]}
