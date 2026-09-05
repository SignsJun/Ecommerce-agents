from decimal import Decimal

from domain.simulation.envelope import PolicyEnvelope, RolloutObservation
from services.profit.engine import as_money


def _ad_budget(state) -> Decimal:
    if not state.campaigns:
        return Decimal("0.00")
    total = Decimal("0.00")
    for camp in state.campaigns.values():
        if camp.paused:
            continue
        total += (camp.daily_budget * Decimal(str(1 + camp.change_pct))).quantize(Decimal("0.01"))
    return as_money(total)


def observe(
    state,
    envelope: PolicyEnvelope,
    day: int,
    last_intervention_day: int | None,
    remaining: int,
    previous_actions: tuple[str, ...],
) -> RolloutObservation:
    if state.last_sales > 0:
        cover = state.inventory / state.last_sales
    elif state.base_daily_demand > 0:
        cover = state.inventory / state.base_daily_demand
    else:
        cover = 999.0
    since = None if last_intervention_day is None else day - last_intervention_day
    can_act = remaining > 0 and (since is None or since >= envelope.min_intervention_interval_days)
    return RolloutObservation(
        day=day,
        profit_margin=state.last_margin,
        roas=state.last_roas,
        inventory_cover=cover,
        refund_rate=state.applied_refund_rate if state.applied_refund_rate else state.refund_rate,
        current_price=state.price,
        current_ad_budget=_ad_budget(state),
        inventory=state.inventory,
        previous_actions=previous_actions,
        days_since_last_action=since,
        remaining_interventions=remaining,
        allowed_actions=envelope.allowed_actions,
        allowed_targets=envelope.allowed_targets,
        can_act=can_act,
    )
