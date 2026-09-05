from domain.common import BusinessPolicyConfig
from domain.simulation.envelope import PolicyEnvelope, RolloutObservation
from services.simulation.params import SimulatorParameterSet


def is_checkpoint(
    day: int,
    obs: RolloutObservation,
    policy: BusinessPolicyConfig,
    params: SimulatorParameterSet,
    envelope: PolicyEnvelope,
    baseline_refund: float,
) -> bool:
    if (day - 1) % max(envelope.decision_interval_days, 1) == 0:
        return True
    if obs.roas is not None and obs.roas < policy.roas_min:
        return True
    if obs.inventory_cover is not None and obs.inventory_cover < policy.stockout_safety_days:
        return True
    if obs.profit_margin is not None and obs.profit_margin < params.min_margin:
        return True
    if baseline_refund > 0 and obs.refund_rate > baseline_refund * 1.25:
        return True
    return False
