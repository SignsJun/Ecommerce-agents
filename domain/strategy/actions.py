from typing import Annotated, Literal

from pydantic import Field

from domain.base import FrozenModel


class AdjustAdBudget(FrozenModel):
    action_type: Literal["adjust_ad_budget"]
    campaign_id: str
    change_pct: float = Field(ge=-0.30, le=0.30)


class PauseCampaign(FrozenModel):
    action_type: Literal["pause_campaign"]
    campaign_id: str


class ReplenishInventory(FrozenModel):
    action_type: Literal["replenish"]
    sku_id: str
    quantity: int = Field(gt=0)


class AdjustPrice(FrozenModel):
    action_type: Literal["adjust_price"]
    sku_id: str
    change_pct: float = Field(ge=-0.15, le=0.10)


class UpdateListing(FrozenModel):
    action_type: Literal["update_listing"]
    sku_id: str
    target_issue: str


BusinessAction = Annotated[
    AdjustAdBudget | PauseCampaign | ReplenishInventory | AdjustPrice | UpdateListing,
    Field(discriminator="action_type"),
]
