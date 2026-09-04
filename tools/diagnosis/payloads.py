from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field

from domain.base import FrozenModel
from domain.business.metrics import MetricState
from domain.business.sku import SKUState
from domain.issue.evidence import Evidence
from domain.issue.models import Issue
from services.profit.engine import ProfitBreakdown


class IssueContextPayload(FrozenModel):
    kind: Literal["issue_context"] = "issue_context"
    issue: Issue
    evidence: list[Evidence]
    sku: SKUState | None


class SkuSummaryPayload(FrozenModel):
    kind: Literal["sku_summary"] = "sku_summary"
    sku: SKUState


class SeriesPoint(FrozenModel):
    metric_date: date
    value: float


class MetricTrendPayload(FrozenModel):
    kind: Literal["metric_trend"] = "metric_trend"
    metric: MetricState
    series: list[SeriesPoint]


class ProfitDecomposePayload(FrozenModel):
    kind: Literal["profit_decompose"] = "profit_decompose"
    sku_id: str
    period_a: ProfitBreakdown
    period_b: ProfitBreakdown
    delta_revenue: Decimal
    delta_cogs: Decimal
    delta_ad_spend: Decimal
    delta_refund_loss: Decimal
    delta_profit: Decimal


class ConversionFunnelPayload(FrozenModel):
    kind: Literal["conversion_funnel"] = "conversion_funnel"
    sku_id: str
    impressions: int
    clicks: int
    sessions: int
    conversions: int
    units_sold: int
    click_through_rate: float | None
    session_cvr: float | None
    purchase_rate: float | None


class CampaignShare(FrozenModel):
    campaign_id: str
    spend: Decimal
    attributed_revenue: Decimal
    roas: float | None
    acos: float | None
    spend_share: float


class CampaignBreakdownPayload(FrozenModel):
    kind: Literal["campaign_breakdown"] = "campaign_breakdown"
    sku_id: str
    campaigns: list[CampaignShare]


class CampaignTrendPoint(FrozenModel):
    metric_date: date
    spend: Decimal
    attributed_revenue: Decimal
    roas: float | None


class CampaignTrendPayload(FrozenModel):
    kind: Literal["campaign_trend"] = "campaign_trend"
    campaign_id: str
    sku_id: str
    points: list[CampaignTrendPoint]


class InventoryDay(FrozenModel):
    day_offset: int
    inventory_eod: float
    expected_sales: float
    arrival: int
    stockout: bool


class InventoryProjectionPayload(FrozenModel):
    kind: Literal["inventory_projection"] = "inventory_projection"
    sku_id: str
    horizon_days: int
    daily_demand: float
    days: list[InventoryDay]
    first_stockout_day: int | None


class RefundBreakdownPayload(FrozenModel):
    kind: Literal["refund_breakdown"] = "refund_breakdown"
    sku_id: str
    refund_units: int
    refund_loss: Decimal
    refund_rate: float
    low_score_share: float | None


class ReviewAnalysisPayload(FrozenModel):
    kind: Literal["review_analysis"] = "review_analysis"
    sku_id: str
    n: int
    score_counts: list[int]
    avg_score: float | None
    low_score_share: float


class PeerRow(FrozenModel):
    sku_id: str
    profit_margin: float | None
    roas: float | None
    days_of_cover: float | None


class PeerComparePayload(FrozenModel):
    kind: Literal["peer_compare"] = "peer_compare"
    sku_id: str
    category: str
    peers: list[PeerRow]


class PricePoint(FrozenModel):
    metric_date: date
    price: Decimal
    units_sold: int


class PriceHistoryPayload(FrozenModel):
    kind: Literal["price_history"] = "price_history"
    sku_id: str
    points: list[PricePoint]


class PromotionHistoryPayload(FrozenModel):
    kind: Literal["promotion_history"] = "promotion_history"
    sku_id: str
    promotions: list[str]
    missing_sources: list[str]


ToolPayload = Annotated[
    IssueContextPayload
    | SkuSummaryPayload
    | MetricTrendPayload
    | ProfitDecomposePayload
    | ConversionFunnelPayload
    | CampaignBreakdownPayload
    | CampaignTrendPayload
    | InventoryProjectionPayload
    | RefundBreakdownPayload
    | ReviewAnalysisPayload
    | PeerComparePayload
    | PriceHistoryPayload
    | PromotionHistoryPayload,
    Field(discriminator="kind"),
]
