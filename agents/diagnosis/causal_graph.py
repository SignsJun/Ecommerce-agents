from domain.enums import IssueType

ALWAYS_TOOLS = ("get_issue_context", "get_sku_summary")

NEIGHBORHOOD: dict[IssueType, tuple[str, ...]] = {
    IssueType.PROFIT_EROSION: (
        "decompose_profit",
        "get_metric_trend",
        "get_campaign_breakdown",
        "get_refund_breakdown",
        "analyze_reviews",
    ),
    IssueType.AD_INEFFICIENCY: (
        "get_campaign_breakdown",
        "get_campaign_trend",
        "get_metric_trend",
    ),
    IssueType.STOCKOUT_RISK: (
        "get_inventory_projection",
        "get_metric_trend",
    ),
    IssueType.EXCESS_INVENTORY: (
        "get_inventory_projection",
        "get_metric_trend",
        "compare_peer_skus",
        "get_sku_summary",
    ),
}

CAUSE_TYPES: dict[IssueType, tuple[str, ...]] = {
    IssueType.PROFIT_EROSION: ("revenue", "cogs", "ad_efficiency", "refunds", "price", "conversion"),
    IssueType.AD_INEFFICIENCY: ("ad_efficiency", "campaign_mix"),
    IssueType.STOCKOUT_RISK: ("inventory",),
    IssueType.EXCESS_INVENTORY: ("excess_inventory", "demand_decline"),
}

SCREEN_FAMILIES: dict[IssueType, tuple[str, ...]] = {
    IssueType.PROFIT_EROSION: ("revenue", "cogs", "ad_efficiency", "refunds"),
    IssueType.AD_INEFFICIENCY: ("ad_efficiency", "campaign_mix"),
    IssueType.STOCKOUT_RISK: ("inventory",),
    IssueType.EXCESS_INVENTORY: ("excess_inventory", "demand_decline"),
}

PREFLIGHT_TOOLS: dict[IssueType, tuple[str, ...]] = {
    IssueType.PROFIT_EROSION: ("get_issue_context", "decompose_profit"),
    IssueType.AD_INEFFICIENCY: ("get_issue_context", "get_campaign_breakdown"),
    IssueType.STOCKOUT_RISK: ("get_issue_context", "get_inventory_projection"),
    IssueType.EXCESS_INVENTORY: ("get_issue_context", "get_inventory_projection"),
}

CAUSAL_NODES = (
    "Profit",
    "Revenue",
    "Traffic",
    "Organic",
    "Paid",
    "Conversion",
    "Price",
    "Listing",
    "Reviews",
    "Promotion",
    "Availability",
    "Inventory",
    "ProductCost",
    "AdCost",
    "CPC",
    "CTR",
    "CVR",
    "CampaignMix",
    "Refund",
    "Quality",
    "Size",
    "Description",
    "Logistics",
    "Service",
    "PromotionCost",
)


def allowed_tools(issue_type: IssueType) -> tuple[str, ...]:
    extra = NEIGHBORHOOD.get(issue_type, ())
    seen: list[str] = []
    for name in (*ALWAYS_TOOLS, *extra):
        if name not in seen:
            seen.append(name)
    return tuple(seen)


def is_allowed_tool(issue_type: IssueType, tool_name: str) -> bool:
    return tool_name in allowed_tools(issue_type)
