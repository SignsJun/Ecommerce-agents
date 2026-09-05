from decimal import Decimal
from typing import Literal

from domain.base import FrozenModel

ActionName = Literal[
    "noop",
    "adjust_ad_budget",
    "pause_campaign",
    "replenish",
    "adjust_price",
    "update_listing",
]


class PolicyEnvelope(FrozenModel):
    strategy_id: str
    strategy_family: str
    allowed_actions: tuple[str, ...]
    allowed_targets: tuple[str, ...]
    ad_change_min: float
    price_locked: bool
    replenish_allowed: bool
    max_interventions: int = 3
    min_intervention_interval_days: int = 3
    decision_interval_days: int = 3


class RolloutObservation(FrozenModel):
    day: int
    profit_margin: float | None
    roas: float | None
    inventory_cover: float | None
    refund_rate: float
    current_price: Decimal
    current_ad_budget: Decimal
    inventory: int
    previous_actions: tuple[str, ...]
    days_since_last_action: int | None
    remaining_interventions: int
    allowed_actions: tuple[str, ...]
    allowed_targets: tuple[str, ...]
    can_act: bool


class RolloutActionRecord(FrozenModel):
    day: int
    action: str
    target_id: str | None = None
    intensity: str | None = None
    accepted: bool = False
