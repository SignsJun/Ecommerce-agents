from domain.common import BusinessPolicyConfig
from domain.simulation.envelope import PolicyEnvelope, RolloutObservation
from domain.strategy.actions import AdjustAdBudget, AdjustPrice, BusinessAction, PauseCampaign, ReplenishInventory, UpdateListing


def ad_pct(intensity: str, policy: BusinessPolicyConfig) -> float:
    if intensity == "strong":
        return policy.ad_budget_change_min
    if intensity == "mild":
        return max(policy.ad_budget_change_min, -0.05)
    return max(policy.ad_budget_change_min, -0.10)


def price_pct(intensity: str, policy: BusinessPolicyConfig) -> float:
    if intensity == "strong":
        return policy.price_change_min
    if intensity == "mild":
        return max(policy.price_change_min, -0.03)
    return max(policy.price_change_min, -0.08)


def replenish_qty(state, intensity: str, policy: BusinessPolicyConfig) -> int:
    daily = state.base_daily_demand
    if intensity == "mild":
        days = policy.target_cover_days_min
    elif intensity == "strong":
        days = policy.target_cover_days_max
    else:
        days = (policy.target_cover_days_min + policy.target_cover_days_max) // 2
    incoming = sum(q for _, q in state.incoming)
    needed = int(daily * days) - state.inventory - incoming
    qty = max(1, needed)
    if state.unit_cost > 0:
        cap = int(state.cash / state.unit_cost)
        if cap <= 0:
            return 0
        qty = min(qty, cap)
    return qty


def materialize_decision(
    action: str,
    target_id: str | None,
    intensity: str | None,
    state,
    policy: BusinessPolicyConfig,
) -> BusinessAction | None:
    if action in {"noop", None, ""}:
        return None
    level = intensity or "standard"
    target = target_id or ""
    if action == "adjust_ad_budget":
        return AdjustAdBudget(action_type="adjust_ad_budget", campaign_id=target, change_pct=ad_pct(level, policy))
    if action == "pause_campaign":
        return PauseCampaign(action_type="pause_campaign", campaign_id=target)
    if action == "replenish":
        qty = replenish_qty(state, level, policy)
        if qty <= 0:
            return None
        return ReplenishInventory(action_type="replenish", sku_id=target or state.sku_id, quantity=qty)
    if action == "adjust_price":
        return AdjustPrice(action_type="adjust_price", sku_id=target or state.sku_id, change_pct=price_pct(level, policy))
    if action == "update_listing":
        return UpdateListing(action_type="update_listing", sku_id=target or state.sku_id, target_issue="listing")
    return None


def validate_intervention(
    action: BusinessAction,
    state,
    envelope: PolicyEnvelope,
    obs: RolloutObservation,
) -> bool:
    if not obs.can_act:
        return False
    if action.action_type not in envelope.allowed_actions:
        return False
    target = getattr(action, "campaign_id", None) or getattr(action, "sku_id", None)
    if target not in envelope.allowed_targets:
        return False
    if isinstance(action, AdjustPrice) and envelope.price_locked:
        return False
    if isinstance(action, ReplenishInventory) and not envelope.replenish_allowed:
        return False
    if isinstance(action, AdjustAdBudget):
        camp = state.campaigns.get(action.campaign_id)
        if camp is None or camp.paused:
            return False
        if camp.change_pct <= envelope.ad_change_min + 1e-12:
            return False
    if isinstance(action, PauseCampaign):
        camp = state.campaigns.get(action.campaign_id)
        if camp is None or camp.paused:
            return False
    if isinstance(action, UpdateListing) and state.listing:
        return False
    if isinstance(action, AdjustPrice) and action.sku_id != state.sku_id:
        return False
    if isinstance(action, ReplenishInventory) and action.sku_id != state.sku_id:
        return False
    return True
