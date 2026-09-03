from datetime import datetime
from decimal import Decimal

from domain.base import FrozenModel


class TimeRange(FrozenModel):
    start: datetime
    end: datetime


class DataQualityReport(FrozenModel):
    completeness_score: float
    freshness_score: float
    consistency_score: float
    missing_sources: list[str]
    warnings: list[str]


class StoreState(FrozenModel):
    store_id: str
    seller_id: str | None = None
    name: str
    cash_balance: Decimal
    daily_ad_budget_cap: Decimal | None = None
    currency: str = "BRL"


class BusinessPolicyConfig(FrozenModel):
    include_platform_fee: bool = False
    include_logistics_fee: bool = False
    include_holding_cost: bool = False
    profit_margin_drop_threshold: float = 0.05
    gmv_up_threshold: float = 0.05
    roas_min: float = 2.0
    roas_drop_ratio: float = 0.25
    ad_spend_up_threshold: float = 0.20
    attributed_revenue_match_threshold: float = 0.05
    stockout_safety_days: int = 7
    excess_cover_days: int = 60
    sales_decline_threshold: float = -0.15
    target_cover_days_min: int = 21
    target_cover_days_max: int = 45
    cost_ratio_min: float = 0.35
    cost_ratio_max: float = 0.55
    default_target_acos: float = 0.25
    paid_revenue_share: float = 0.40
    base_cvr: float = 0.03
    impact_horizon_days: int = 14
    ad_budget_change_min: float = -0.30
    ad_budget_change_max: float = 0.30
    price_change_min: float = -0.15
    price_change_max: float = 0.10
    synthetic_seed: int = 42
