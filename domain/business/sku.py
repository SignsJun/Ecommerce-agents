from datetime import datetime
from decimal import Decimal

from domain.base import FrozenModel
from domain.enums import DataProvenance


class SKUState(FrozenModel):
    sku_id: str
    category: str
    lifecycle_stage: str | None = None
    price: Decimal
    base_price: Decimal | None = None
    unit_cost: Decimal
    inventory_on_hand: int
    inventory_available: int
    incoming_inventory: int
    lead_time_days: int
    units_sold_7d: int
    units_sold_30d: int
    revenue_7d: Decimal
    profit_7d: Decimal
    profit_margin_7d: float
    conversion_rate_7d: float | None = None
    refund_rate_7d: float
    avg_rating_30d: float | None = None
    ad_spend_7d: Decimal = Decimal("0")
    roas_7d: float | None = None
    roas_prev_7d: float | None = None
    roas_30d: float | None = None
    paid_traffic_7d: int = 0
    ad_conversions_7d: int = 0


class SKUDailyMetric(FrozenModel):
    sku_id: str
    metric_date: datetime
    units_sold: int
    revenue: Decimal
    cogs: Decimal
    ad_spend: Decimal
    refund_loss: Decimal
    profit: Decimal
    refund_units: int
    sessions: int
    conversions: int
    avg_rating: float | None = None
    inventory_eod: int
    provenance: DataProvenance
