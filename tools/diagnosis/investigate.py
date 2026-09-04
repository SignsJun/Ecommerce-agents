from services.daily_run import DailyRunResult
from tools.diagnosis.base import ToolContext, ToolResult
from tools.diagnosis.handlers import project_horizon_dates
from tools.diagnosis.registry import TOOL_NAMES, invoke


def context_from_run(result: DailyRunResult) -> ToolContext:
    return ToolContext(
        snapshot_id=result.snapshot.snapshot_id,
        snapshot_repo=result.snapshot_repo,
        issue_repo=result.issue_repo,
        business_repo=result.business_repo,
        policy=result.policy,
        as_of=result.as_of,
        tz=result.tz,
        now=result.now,
    )


def investigate_issue(ctx: ToolContext, issue_id: str) -> list[ToolResult]:
    issue = ctx.issue_repo.get_issue(issue_id)
    if issue is None:
        return [invoke(ctx, "get_issue_context", issue_id=issue_id)]
    sku_id = issue.entity_id
    campaigns = ctx.business_repo.list_campaigns_for_sku(sku_id)
    campaign_id = campaigns[0] if campaigns else ""
    a0, a1, b0, b1 = project_horizon_dates(ctx.as_of)
    calls: list[tuple[str, dict]] = [
        ("get_issue_context", {"issue_id": issue_id}),
        ("get_sku_summary", {"sku_id": sku_id}),
        ("get_metric_trend", {"entity_type": "sku", "entity_id": sku_id, "metric": "profit_margin", "window_name": "7d"}),
        (
            "decompose_profit",
            {
                "sku_id": sku_id,
                "period_a_start": a0,
                "period_a_end": a1,
                "period_b_start": b0,
                "period_b_end": b1,
            },
        ),
        ("get_conversion_funnel", {"sku_id": sku_id}),
        ("get_campaign_breakdown", {"sku_id": sku_id}),
        ("get_campaign_trend", {"campaign_id": campaign_id}),
        ("get_inventory_projection", {"sku_id": sku_id}),
        ("get_refund_breakdown", {"sku_id": sku_id}),
        ("analyze_reviews", {"sku_id": sku_id, "window_name": "7d"}),
        ("compare_peer_skus", {"sku_id": sku_id, "metrics": "profit_margin,roas,days_of_cover"}),
        ("get_price_history", {"sku_id": sku_id}),
        ("get_promotion_history", {"sku_id": sku_id}),
    ]
    return [invoke(ctx, name, **kwargs) for name, kwargs in calls]


def all_tool_names() -> tuple[str, ...]:
    return TOOL_NAMES
