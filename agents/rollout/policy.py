from agents.rollout.schema import RolloutDecision
from domain.simulation.envelope import RolloutObservation


def _first_target(obs: RolloutObservation, action: str) -> str | None:
    if action in {"adjust_ad_budget", "pause_campaign"}:
        for t in obs.allowed_targets:
            if t.startswith("CMP") or t.startswith("CAMP"):
                return t
        return obs.allowed_targets[0] if obs.allowed_targets else None
    for t in obs.allowed_targets:
        if not t.startswith("CMP") and not t.startswith("CAMP"):
            return t
    return obs.allowed_targets[-1] if obs.allowed_targets else None


def rule_decide(obs: RolloutObservation, *, roas_min: float = 2.0, cover_min: float = 7.0, refund_base: float | None = None) -> RolloutDecision:
    if not obs.can_act:
        return RolloutDecision(action="noop", reason="budget")
    allowed = set(obs.allowed_actions)
    if obs.inventory_cover is not None and obs.inventory_cover < cover_min and "replenish" in allowed:
        return RolloutDecision(
            action="replenish",
            target_id=_first_target(obs, "replenish"),
            intensity="standard",
            reason="cover",
        )
    if obs.roas is not None and obs.roas < roas_min and "adjust_ad_budget" in allowed:
        return RolloutDecision(
            action="adjust_ad_budget",
            target_id=_first_target(obs, "adjust_ad_budget"),
            intensity="mild",
            reason="roas",
        )
    if refund_base and obs.refund_rate > refund_base * 1.25 and "update_listing" in allowed:
        return RolloutDecision(
            action="update_listing",
            target_id=_first_target(obs, "update_listing"),
            intensity="standard",
            reason="refund",
        )
    return RolloutDecision(action="noop", reason="stable")
