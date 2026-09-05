from domain.common import BusinessPolicyConfig
from domain.simulation.envelope import PolicyEnvelope
from domain.strategy.models import Strategy


def _target(action) -> str | None:
    return getattr(action, "campaign_id", None) or getattr(action, "sku_id", None)


def build_envelope(strategy: Strategy, policy: BusinessPolicyConfig) -> PolicyEnvelope:
    types = {a.action_type for a in strategy.actions}
    if "adjust_ad_budget" in types:
        types.add("pause_campaign")
    targets = tuple(dict.fromkeys(t for a in strategy.actions if (t := _target(a))))
    if not strategy.actions:
        types = set()
        targets = ()
    return PolicyEnvelope(
        strategy_id=strategy.strategy_id,
        strategy_family=strategy.strategy_type,
        allowed_actions=tuple(sorted(types)),
        allowed_targets=targets,
        ad_change_min=policy.ad_budget_change_min,
        price_locked="adjust_price" not in {a.action_type for a in strategy.actions},
        replenish_allowed="replenish" in {a.action_type for a in strategy.actions},
    )
