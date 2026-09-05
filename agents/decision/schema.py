from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ActionType = Literal["adjust_ad_budget", "pause_campaign", "replenish", "adjust_price", "update_listing"]
Intensity = Literal["mild", "standard", "strong"]
StrategyKind = Literal["conservative", "balanced", "growth"]


class LLMModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class LLMActionDraft(LLMModel):
    action_type: ActionType
    target_id: str
    intensity: Intensity = "standard"


class LLMStrategyDraft(LLMModel):
    name: str
    strategy_type: StrategyKind
    objective: str = ""
    actions: list[LLMActionDraft] = Field(default_factory=list)


class StrategyPlanDraft(LLMModel):
    strategies: list[LLMStrategyDraft] = Field(default_factory=list)
