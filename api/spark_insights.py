"""Rule-based insights derived from unified metric tables."""

from __future__ import annotations

from typing import Any


GENERATED_BY = "SPARK_RULE_ENGINE"


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def latest_creator_snapshot(data: dict[str, Any]) -> dict[str, Any] | None:
    rows = data.get("creatorMetricSnapshots") or []
    if not rows:
        return None
    return sorted(rows, key=lambda item: item.get("date") or "")[-1]


def insight(
    *,
    insight_id: str,
    creator_id: str,
    insight_type: str,
    scope: str,
    target_id: str,
    title: str,
    summary: str,
    priority: str,
    evidence: list[dict[str, Any]],
    action_id: str,
    action_title: str,
    action_description: str,
    expected_impact: str,
    related_page: str,
    generated_at: str,
    page_targets: list[str],
) -> dict[str, Any]:
    return {
        "insightId": insight_id,
        "creatorId": creator_id,
        "type": insight_type,
        "scope": scope,
        "targetId": target_id,
        "title": title,
        "summary": summary,
        "priority": priority,
        "evidenceMetrics": evidence,
        "recommendedActions": [
            {
                "actionId": action_id,
                "title": action_title,
                "description": action_description,
                "expectedImpact": expected_impact,
                "relatedPage": related_page,
            }
        ],
        "generatedBy": GENERATED_BY,
        "generatedAt": generated_at,
        "pageTargets": page_targets,
    }


def metric(label: str, value: Any, unit: str, direction: str = "UP") -> dict[str, Any]:
    return {"label": label, "value": value, "unit": unit, "direction": direction}


def platform_name(platform: str) -> str:
    return {
        "DOUYIN": "抖音",
        "BILIBILI": "B站",
        "XIAOHONGSHU": "小红书",
        "KUAISHOU": "快手",
        "WEIBO": "微博",
    }.get(platform, platform)


def build_spark_insights(data: dict[str, Any]) -> list[dict[str, Any]]:
    outputs = data.get("sparkOutputs") or {}
    platform_rows = outputs.get("platformMetricSummaries") or []
    contribution_rows = outputs.get("videoFollowerContributions") or []
    video_rows = data.get("videoMetricSnapshots") or []
    creator_snapshot = latest_creator_snapshot(data)
    generated_at = data.get("meta", {}).get("generatedAt") or ""
    creator_id = data.get("creator", {}).get("creatorId") or "creator_001"

    insights: list[dict[str, Any]] = []

    if creator_snapshot:
        health = number(creator_snapshot.get("growthHealthScore"))
        stickiness = number(creator_snapshot.get("stickinessScore"))
        view_to_follow = number(creator_snapshot.get("viewToFollowerRate"))
        new_followers = int(number(creator_snapshot.get("newFollowers")))
        total_views = int(number(creator_snapshot.get("totalViews")))
        priority = "HIGH" if health >= 70 else "MEDIUM"
        insights.append(
            insight(
                insight_id="insight_spark_growth_health",
                creator_id=creator_id,
                insight_type="DIAGNOSIS",
                scope="GROWTH_HEALTH",
                target_id=creator_id,
                title=f"你的账号健康度为 {health:.0f}，增长主要由转粉效率和粘性共同决定",
                summary=f"今天累计播放 {total_views}，新增粉丝 {new_followers}，播放转粉率 {view_to_follow:.2%}，粘性指数 {stickiness:.1f}。",
                priority=priority,
                evidence=[
                    metric("账号健康度", round(health, 2), "score"),
                    metric("播放转粉率", round(view_to_follow, 6), "rate"),
                    metric("粘性指数", round(stickiness, 2), "score"),
                ],
                action_id="action_spark_growth_health_01",
                action_title="先优化转粉链路",
                action_description="优先检查高播放视频的主页承接和关注引导，把转粉率最高的视频结构复用到下一条内容。",
                expected_impact="提升账号增长健康度",
                related_page="growth.overview",
                generated_at=generated_at,
                page_targets=["growth.overview", "growth.conversion", "fans.growth", "profile.reports"],
            )
        )

        insights.append(
            insight(
                insight_id="insight_spark_fan_stickiness",
                creator_id=creator_id,
                insight_type="DIAGNOSIS",
                scope="FAN_STICKINESS",
                target_id=creator_id,
                title=f"你的粉丝粘性指数为 {stickiness:.1f}，互动质量需要和转粉一起看",
                summary=f"当前总互动 {int(number(creator_snapshot.get('totalInteractions')))}，主页访问 {int(number(creator_snapshot.get('profileVisits')))}，说明内容需要继续强化收藏、评论和复访理由。",
                priority="HIGH" if stickiness >= 60 else "MEDIUM",
                evidence=[
                    metric("粘性指数", round(stickiness, 2), "score"),
                    metric("总互动", int(number(creator_snapshot.get("totalInteractions"))), "count"),
                    metric("主页访问", int(number(creator_snapshot.get("profileVisits"))), "count"),
                ],
                action_id="action_spark_fan_stickiness_01",
                action_title="提高高价值互动",
                action_description="在教程和测评内容里增加收藏提示、评论提问和系列预告，让粉丝有再次回看的理由。",
                expected_impact="提升粉丝留存质量",
                related_page="fans.stickiness",
                generated_at=generated_at,
                page_targets=["fans.stickiness", "growth.stickiness", "profile.reports", "profile.notify"],
            )
        )

    if platform_rows:
        top_platform = max(platform_rows, key=lambda item: (number(item.get("newFollowers")), number(item.get("conversionRate"))))
        platform = top_platform["platform"]
        platform_label = platform_name(platform)
        insights.append(
            insight(
                insight_id="insight_spark_platform_efficiency",
                creator_id=creator_id,
                insight_type="OPPORTUNITY",
                scope="PLATFORM_EFFICIENCY",
                target_id=platform,
                title=f"{platform_label} 是当前最值得加码的平台",
                summary=f"{platform_label} 当前贡献 {top_platform['newFollowers']} 个新粉，转粉率 {number(top_platform.get('conversionRate')):.2%}，适合作为下周内容配比的优先参考。",
                priority="HIGH",
                evidence=[
                    metric("平台新粉", top_platform["newFollowers"], "followers"),
                    metric("平台转粉率", number(top_platform.get("conversionRate")), "rate"),
                    metric("平台播放", top_platform["totalViews"], "views"),
                ],
                action_id="action_spark_platform_efficiency_01",
                action_title="调整下周平台配比",
                action_description=f"把 {platform_label} 的高转粉内容排到主发布窗口，减少低转粉泛流量内容占用。",
                expected_impact="提升平台投入效率",
                related_page="content.platform",
                generated_at=generated_at,
                page_targets=["content.platform", "growth.distribution", "fans.source"],
            )
        )

    if contribution_rows:
        top_video = max(contribution_rows, key=lambda item: (number(item.get("newFollowers")), number(item.get("conversionRate"))))
        insights.append(
            insight(
                insight_id="insight_spark_video_contribution",
                creator_id=creator_id,
                insight_type="ACTION",
                scope="VIDEO_CONTRIBUTION",
                target_id=top_video["videoId"],
                title="这条视频最值得复刻为下一条内容",
                summary=f"《{top_video['title']}》带来 {top_video['newFollowers']} 个新粉，转粉率 {number(top_video.get('conversionRate')):.2%}。",
                priority="HIGH",
                evidence=[
                    metric("视频新粉", top_video["newFollowers"], "followers"),
                    metric("视频转粉率", number(top_video.get("conversionRate")), "rate"),
                    metric("视频播放", top_video["views"], "views"),
                ],
                action_id="action_spark_video_contribution_01",
                action_title="复刻高转粉结构",
                action_description="保留这条视频的选题、开头承诺和主页承接方式，做一条同系列内容测试复现。",
                expected_impact="提升下一条内容的关注转化",
                related_page="video.contribution",
                generated_at=generated_at,
                page_targets=["video.contribution", "growth.conversion", "opportunities.reference"],
            )
        )

    if video_rows:
        high_play_low_conversion = [
            item
            for item in video_rows
            if number(item.get("views")) >= max(number(row.get("views")) for row in video_rows) * 0.6
            and number(item.get("conversionRate")) < 0.003
        ]
        if high_play_low_conversion:
            target = sorted(high_play_low_conversion, key=lambda item: number(item.get("views")), reverse=True)[0]
            insights.append(
                insight(
                    insight_id="insight_spark_conversion_bottleneck",
                    creator_id=creator_id,
                    insight_type="RISK",
                    scope="CONVERSION_BOTTLENECK",
                    target_id=target["videoId"],
                    title="有高播放内容没有把流量转成关注",
                    summary=f"该视频播放 {target['views']}，但转粉率只有 {number(target.get('conversionRate')):.2%}，说明主页承接或关注理由需要加强。",
                    priority="MEDIUM",
                    evidence=[
                        metric("视频播放", target["views"], "views"),
                        metric("视频转粉率", number(target.get("conversionRate")), "rate", "DOWN"),
                    ],
                    action_id="action_spark_conversion_bottleneck_01",
                    action_title="补强关注理由",
                    action_description="把结尾 CTA、主页首屏介绍和合集入口统一成同一个承诺，减少看完即走的流量浪费。",
                    expected_impact="减少高播放低转粉浪费",
                    related_page="growth.conversion",
                    generated_at=generated_at,
                    page_targets=["growth.conversion", "video.quality"],
                )
            )

    return insights


def merge_spark_insights(data: dict[str, Any]) -> dict[str, Any]:
    existing = data.get("insights") or []
    generated = build_spark_insights(data)
    if generated:
        return {**data, "insights": generated}
    return {**data, "insights": existing}
