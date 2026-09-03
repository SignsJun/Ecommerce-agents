from datetime import datetime
from decimal import Decimal

from domain.base import FrozenModel
from domain.enums import DataProvenance


class CampaignState(FrozenModel):
    campaign_id: str
    sku_id: str
    status: str
    daily_budget: Decimal
    spend_7d: Decimal
    attributed_revenue_7d: Decimal
    impressions_7d: int
    clicks_7d: int
    conversions_7d: int
    cpc_7d: Decimal | None = None
    cvr_7d: float | None = None
    roas_7d: float | None = None
    acos_7d: float | None = None


class CampaignDailyMetric(FrozenModel):
    campaign_id: str
    sku_id: str
    metric_date: datetime
    spend: Decimal
    attributed_revenue: Decimal
    impressions: int
    clicks: int
    conversions: int
    provenance: DataProvenance
