from datetime import date, datetime, timedelta
from decimal import Decimal

from domain.business.campaign import CampaignDailyMetric, CampaignState
from domain.business.inventory import days_of_cover
from domain.business.metrics import MetricState
from domain.business.sku import SKUDailyMetric, SKUState
from domain.enums import DataProvenance
from services.profit.engine import decompose_profit


def window(as_of: date, days: int, offset_end: int = 0) -> tuple[date, date]:
    end = as_of - timedelta(days=offset_end)
    start = end - timedelta(days=days - 1)
    return start, end


def in_window(metric_date: datetime, start: date, end: date) -> bool:
    d = metric_date.date()
    return start <= d <= end


def filter_sku(rows: list[SKUDailyMetric], sku_id: str, start: date, end: date) -> list[SKUDailyMetric]:
    return [r for r in rows if r.sku_id == sku_id and in_window(r.metric_date, start, end)]


def filter_campaign(
    rows: list[CampaignDailyMetric], campaign_id: str, start: date, end: date
) -> list[CampaignDailyMetric]:
    return [r for r in rows if r.campaign_id == campaign_id and in_window(r.metric_date, start, end)]


def _trend(current: float, baseline: float | None) -> float | None:
    if baseline is None or baseline == 0:
        return None
    return (current - baseline) / abs(baseline)


def _metric(
    name: str,
    entity_type: str,
    entity_id: str,
    current: float,
    baseline_7d: float | None,
    baseline_30d: float | None,
    calculated_at: datetime,
    trend_30d: float | None = None,
) -> MetricState:
    return MetricState(
        metric_name=name,
        entity_type=entity_type,
        entity_id=entity_id,
        current_value=current,
        baseline_7d=baseline_7d,
        baseline_30d=baseline_30d,
        trend_7d=_trend(current, baseline_7d),
        trend_30d=trend_30d if trend_30d is not None else _trend(current, baseline_30d),
        provenance=DataProvenance.DERIVED,
        calculated_at=calculated_at,
    )


def _units(rows: list[SKUDailyMetric]) -> int:
    return sum(r.units_sold for r in rows)


def _refund_rate(rows: list[SKUDailyMetric]) -> float:
    units = _units(rows)
    if units == 0:
        return 0.0
    return sum(r.refund_units for r in rows) / units


def _avg_rating(rows: list[SKUDailyMetric]) -> float | None:
    vals = [r.avg_rating for r in rows if r.avg_rating is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _cvr(rows: list[SKUDailyMetric]) -> float | None:
    sessions = sum(r.sessions for r in rows)
    conversions = sum(r.conversions for r in rows)
    if sessions == 0:
        return None
    return conversions / sessions


def _roas(rows: list[CampaignDailyMetric]) -> float | None:
    spend = sum((r.spend for r in rows), Decimal("0"))
    revenue = sum((r.attributed_revenue for r in rows), Decimal("0"))
    if spend == 0:
        return None
    return float(revenue / spend)


def _ad_spend(rows: list[CampaignDailyMetric] | list[SKUDailyMetric]) -> float:
    return float(sum((r.spend if isinstance(r, CampaignDailyMetric) else r.ad_spend for r in rows), Decimal("0")))


def build_sku_state(
    sku_id: str,
    category: str,
    price: Decimal,
    base_price: Decimal,
    unit_cost: Decimal,
    inventory_on_hand: int,
    inventory_available: int,
    incoming_inventory: int,
    lead_time_days: int,
    rows: list[SKUDailyMetric],
    as_of: date,
) -> SKUState:
    cur_start, cur_end = window(as_of, 7)
    long_start, long_end = window(as_of, 30)
    cur = filter_sku(rows, sku_id, cur_start, cur_end)
    long = filter_sku(rows, sku_id, long_start, long_end)
    br = decompose_profit(cur)
    return SKUState(
        sku_id=sku_id,
        category=category,
        price=price,
        base_price=base_price,
        unit_cost=unit_cost,
        inventory_on_hand=inventory_on_hand,
        inventory_available=inventory_available,
        incoming_inventory=incoming_inventory,
        lead_time_days=lead_time_days,
        units_sold_7d=_units(cur),
        units_sold_30d=_units(long),
        revenue_7d=br.revenue,
        profit_7d=br.profit,
        profit_margin_7d=br.profit_margin,
        conversion_rate_7d=_cvr(cur),
        refund_rate_7d=_refund_rate(cur),
        avg_rating_30d=_avg_rating(long),
    )


def build_campaign_state(
    campaign_id: str,
    sku_id: str,
    rows: list[CampaignDailyMetric],
    as_of: date,
    status: str = "active",
) -> CampaignState:
    cur_start, cur_end = window(as_of, 7)
    cur = filter_campaign(rows, campaign_id, cur_start, cur_end)
    spend = sum((r.spend for r in cur), Decimal("0"))
    attributed = sum((r.attributed_revenue for r in cur), Decimal("0"))
    impressions = sum(r.impressions for r in cur)
    clicks = sum(r.clicks for r in cur)
    conversions = sum(r.conversions for r in cur)
    return CampaignState(
        campaign_id=campaign_id,
        sku_id=sku_id,
        status=status,
        daily_budget=(spend / 7).quantize(Decimal("0.01")),
        spend_7d=spend,
        attributed_revenue_7d=attributed,
        impressions_7d=impressions,
        clicks_7d=clicks,
        conversions_7d=conversions,
        cpc_7d=(spend / clicks).quantize(Decimal("0.01")) if clicks else None,
        cvr_7d=(conversions / clicks) if clicks else None,
        roas_7d=float(attributed / spend) if spend else None,
        acos_7d=float(spend / attributed) if attributed else None,
    )


def build_sku_metric_states(
    sku: SKUState,
    rows: list[SKUDailyMetric],
    campaign_rows: list[CampaignDailyMetric],
    as_of: date,
    calculated_at: datetime,
) -> list[MetricState]:
    cur_s, cur_e = window(as_of, 7)
    prior7_s, prior7_e = window(as_of, 7, offset_end=7)
    prior30_s, prior30_e = window(as_of, 30, offset_end=7)
    cur = filter_sku(rows, sku.sku_id, cur_s, cur_e)
    prior7 = filter_sku(rows, sku.sku_id, prior7_s, prior7_e)
    prior30 = filter_sku(rows, sku.sku_id, prior30_s, prior30_e)
    cur_p = decompose_profit(cur)
    p7 = decompose_profit(prior7)
    p30 = decompose_profit(prior30)
    sku_campaigns = [r for r in campaign_rows if r.sku_id == sku.sku_id]
    cur_c = [r for r in sku_campaigns if in_window(r.metric_date, cur_s, cur_e)]
    prior7_c = [r for r in sku_campaigns if in_window(r.metric_date, prior7_s, prior7_e)]
    prior30_c = [r for r in sku_campaigns if in_window(r.metric_date, prior30_s, prior30_e)]
    cover = days_of_cover(sku.inventory_available, sku.units_sold_7d)
    return [
        _metric("profit_margin", "sku", sku.sku_id, cur_p.profit_margin, p7.profit_margin, p30.profit_margin, calculated_at),
        _metric("revenue", "sku", sku.sku_id, float(cur_p.revenue), float(p7.revenue), float(p30.revenue), calculated_at),
        _metric("profit", "sku", sku.sku_id, float(cur_p.profit), float(p7.profit), float(p30.profit), calculated_at),
        _metric("units_sold", "sku", sku.sku_id, float(_units(cur)), float(_units(prior7)), float(_units(prior30)), calculated_at),
        _metric("refund_rate", "sku", sku.sku_id, _refund_rate(cur), _refund_rate(prior7), _refund_rate(prior30), calculated_at),
        _metric("ad_spend", "sku", sku.sku_id, _ad_spend(cur), _ad_spend(prior7), _ad_spend(prior30), calculated_at),
        _metric("roas", "sku", sku.sku_id, _roas(cur_c) or 0.0, _roas(prior7_c), _roas(prior30_c), calculated_at),
        _metric("days_of_cover", "sku", sku.sku_id, cover, None, None, calculated_at),
    ]


def build_campaign_metric_states(
    campaign: CampaignState,
    rows: list[CampaignDailyMetric],
    as_of: date,
    calculated_at: datetime,
) -> list[MetricState]:
    cur_s, cur_e = window(as_of, 7)
    prior7_s, prior7_e = window(as_of, 7, offset_end=7)
    prior30_s, prior30_e = window(as_of, 30, offset_end=7)
    cur = filter_campaign(rows, campaign.campaign_id, cur_s, cur_e)
    prior7 = filter_campaign(rows, campaign.campaign_id, prior7_s, prior7_e)
    prior30 = filter_campaign(rows, campaign.campaign_id, prior30_s, prior30_e)
    return [
        _metric("roas", "campaign", campaign.campaign_id, _roas(cur) or 0.0, _roas(prior7), _roas(prior30), calculated_at),
        _metric("ad_spend", "campaign", campaign.campaign_id, _ad_spend(cur), _ad_spend(prior7), _ad_spend(prior30), calculated_at),
        _metric(
            "attributed_revenue",
            "campaign",
            campaign.campaign_id,
            float(sum((r.attributed_revenue for r in cur), Decimal("0"))),
            float(sum((r.attributed_revenue for r in prior7), Decimal("0"))),
            float(sum((r.attributed_revenue for r in prior30), Decimal("0"))),
            calculated_at,
        ),
    ]
