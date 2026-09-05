from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RolloutAction = Literal[
    "noop",
    "adjust_ad_budget",
    "pause_campaign",
    "replenish",
    "adjust_price",
    "update_listing",
]
Intensity = Literal["mild", "standard", "strong"]


class RolloutDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    action: RolloutAction = "noop"
    target_id: str | None = None
    intensity: Intensity | None = None
    reason: str = ""
