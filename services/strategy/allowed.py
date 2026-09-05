from domain.enums import IssueType

ALLOWED_ACTIONS: dict[IssueType, tuple[str, ...]] = {
    IssueType.PROFIT_EROSION: ("adjust_ad_budget", "pause_campaign", "update_listing"),
    IssueType.AD_INEFFICIENCY: ("adjust_ad_budget", "pause_campaign"),
    IssueType.STOCKOUT_RISK: ("replenish",),
    IssueType.EXCESS_INVENTORY: ("adjust_ad_budget", "pause_campaign", "adjust_price"),
}


def allowed_actions(issue_type: IssueType) -> tuple[str, ...]:
    return ALLOWED_ACTIONS.get(issue_type, ())
