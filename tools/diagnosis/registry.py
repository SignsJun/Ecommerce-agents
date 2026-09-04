from collections.abc import Callable

from tools.diagnosis.base import ToolContext, ToolResult, fail
from tools.diagnosis.handlers import (
    analyze_reviews,
    compare_peer_skus,
    decompose_profit_tool,
    get_campaign_breakdown,
    get_campaign_trend,
    get_conversion_funnel,
    get_inventory_projection,
    get_issue_context,
    get_metric_trend,
    get_price_history,
    get_promotion_history,
    get_refund_breakdown,
    get_sku_summary,
)

TOOL_NAMES = (
    "get_issue_context",
    "get_sku_summary",
    "get_metric_trend",
    "decompose_profit",
    "get_conversion_funnel",
    "get_campaign_breakdown",
    "get_campaign_trend",
    "get_inventory_projection",
    "get_refund_breakdown",
    "analyze_reviews",
    "compare_peer_skus",
    "get_price_history",
    "get_promotion_history",
)

_HANDLERS: dict[str, Callable[..., ToolResult]] = {
    "get_issue_context": get_issue_context,
    "get_sku_summary": get_sku_summary,
    "get_metric_trend": get_metric_trend,
    "decompose_profit": decompose_profit_tool,
    "get_conversion_funnel": get_conversion_funnel,
    "get_campaign_breakdown": get_campaign_breakdown,
    "get_campaign_trend": get_campaign_trend,
    "get_inventory_projection": get_inventory_projection,
    "get_refund_breakdown": get_refund_breakdown,
    "analyze_reviews": analyze_reviews,
    "compare_peer_skus": compare_peer_skus,
    "get_price_history": get_price_history,
    "get_promotion_history": get_promotion_history,
}


def invoke(ctx: ToolContext, name: str, **kwargs) -> ToolResult:
    handler = _HANDLERS.get(name)
    if handler is None:
        return fail(ctx, name, "not_found", f"unknown tool: {name}", {"name": name})
    return handler(ctx, **kwargs)
