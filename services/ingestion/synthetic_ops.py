import hashlib
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from domain.base import FrozenModel
from domain.business.campaign import CampaignDailyMetric
from domain.business.review import ReviewRecord
from domain.business.sku import SKUDailyMetric
from domain.common import BusinessPolicyConfig, StoreState
from domain.enums import DataProvenance
from services.ingestion.olist_loader import RawOrderLine
from services.profit.engine import compute_cogs, compute_profit, compute_refund_loss


class SkuOpsProfile(FrozenModel):
    sku_id: str
    category: str
    price: Decimal
    base_price: Decimal
    unit_cost: Decimal
    lead_time_days: int
    inventory_available: int
    inventory_on_hand: int
    incoming_inventory: int
    scenario: str


class SyntheticOpsResult(FrozenModel):
    store: StoreState
    profiles: dict[str, SkuOpsProfile]
    sku_daily: list[SKUDailyMetric]
    campaign_daily: list[CampaignDailyMetric]
    reviews: list[ReviewRecord]
    missing_sources: list[str]
    warnings: list[str]


_KNOWN = {
    "sku_profit_erosion": "profit_erosion",
    "sku_ad_inefficiency": "ad_inefficiency",
    "sku_stockout_risk": "stockout_risk",
    "sku_excess_inventory": "excess_inventory",
    "sku_healthy": "normal",
}


def resolve_scenario(sku_id: str) -> str:
    if sku_id in _KNOWN:
        return _KNOWN[sku_id]
    bucket = int(hashlib.sha256(sku_id.encode()).hexdigest()[:8], 16) % 10
    return {
        0: "stockout_risk",
        1: "excess_inventory",
        2: "ad_inefficiency",
        3: "profit_erosion",
    }.get(bucket, "normal")


def _ratio(sku_id: str, policy: BusinessPolicyConfig) -> Decimal:
    span = policy.cost_ratio_max - policy.cost_ratio_min
    n = int(hashlib.sha256(sku_id.encode()).hexdigest()[:8], 16)
    value = policy.cost_ratio_min + (n % 1000) / 1000 * span
    return Decimal(str(round(value, 4)))


def _lead_time(sku_id: str, scenario: str) -> int:
    if scenario == "stockout_risk":
        return 14
    n = int(hashlib.sha256(f"{sku_id}:lt".encode()).hexdigest()[:8], 16)
    return 7 + n % 15


def _cover_days(sku_id: str, scenario: str, policy: BusinessPolicyConfig) -> int:
    if scenario == "stockout_risk":
        return 3
    if scenario == "excess_inventory":
        return 90
    n = int(hashlib.sha256(f"{sku_id}:cover".encode()).hexdigest()[:8], 16)
    span = policy.target_cover_days_max - policy.target_cover_days_min
    return policy.target_cover_days_min + n % (span + 1)


def _day(ts: datetime) -> date:
    return ts.date()


def _midnight(d: date, tz: ZoneInfo) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=tz)


def apply_synthetic(
    lines: list[RawOrderLine],
    policy: BusinessPolicyConfig,
    tz: ZoneInfo,
    store_id: str,
    store_name: str,
    as_of: date,
) -> SyntheticOpsResult:
    by_sku: dict[str, list[RawOrderLine]] = defaultdict(list)
    for line in lines:
        by_sku[line.sku_id].append(line)

    profiles: dict[str, SkuOpsProfile] = {}
    sku_daily: list[SKUDailyMetric] = []
    campaign_daily: list[CampaignDailyMetric] = []
    reviews: list[ReviewRecord] = []

    for sku_id, sku_lines in by_sku.items():
        sku_lines = sorted(sku_lines, key=lambda x: x.purchased_at)
        scenario = resolve_scenario(sku_id)
        category = sku_lines[0].category
        prices = [ln.price for ln in sku_lines]
        price = prices[-1]
        base_price = prices[0]
        unit_cost = (price * _ratio(sku_id, policy)).quantize(Decimal("0.01"))
        lead_time_days = _lead_time(sku_id, scenario)

        by_date: dict[date, list[RawOrderLine]] = defaultdict(list)
        for ln in sku_lines:
            by_date[_day(ln.purchased_at)].append(ln)
            if ln.review_score is not None:
                reviews.append(
                    ReviewRecord(
                        sku_id=sku_id,
                        reviewed_at=ln.purchased_at,
                        score=ln.review_score,
                        provenance=DataProvenance.OBSERVED,
                    )
                )
        first = min(by_date)
        last = max(as_of, max(by_date))
        cursor = first
        while cursor <= last:
            by_date.setdefault(cursor, [])
            cursor += timedelta(days=1)

        campaign_id = f"CMP_{sku_id}_MAIN"
        recent_start = as_of - timedelta(days=6)
        units_7d = 0
        daily_rows: list[SKUDailyMetric] = []

        for day in sorted(by_date):
            day_lines = by_date[day]
            units = len(day_lines)
            revenue = sum((ln.price for ln in day_lines), Decimal("0"))
            scores = [ln.review_score for ln in day_lines if ln.review_score is not None]
            refund_units = sum(1 for s in scores if s <= 2)
            refund_rate = (refund_units / units) if units else 0.0
            is_recent = day >= recent_start
            if scenario == "profit_erosion" and is_recent:
                refund_rate = max(refund_rate, 0.13)
                refund_units = max(refund_units, int(round(units * refund_rate)))
            refund_loss = compute_refund_loss(revenue, refund_rate)
            target_roas = 3.0
            if scenario == "ad_inefficiency":
                target_roas = 1.0
            if scenario == "profit_erosion" and is_recent:
                target_roas = 0.8
            attributed = (revenue * Decimal(str(policy.paid_revenue_share))).quantize(Decimal("0.01"))
            spend = (
                (attributed / Decimal(str(target_roas))).quantize(Decimal("0.01")) if target_roas else Decimal("0")
            )
            cogs = compute_cogs(unit_cost, units)
            profit = compute_profit(revenue, cogs, spend, refund_loss, policy)
            conversions = units
            sessions = int(conversions / policy.base_cvr) if policy.base_cvr else conversions
            clicks = max(conversions * 12, 1 if spend > 0 else 0)
            impressions = max(conversions * 400, clicks)
            avg_rating = (sum(scores) / len(scores)) if scores else None
            daily_rows.append(
                SKUDailyMetric(
                    sku_id=sku_id,
                    metric_date=_midnight(day, tz),
                    units_sold=units,
                    revenue=revenue,
                    cogs=cogs,
                    ad_spend=spend,
                    refund_loss=refund_loss,
                    profit=profit,
                    refund_units=refund_units,
                    sessions=sessions,
                    conversions=conversions,
                    avg_rating=avg_rating,
                    inventory_eod=0,
                    provenance=DataProvenance.DERIVED,
                )
            )
            campaign_daily.append(
                CampaignDailyMetric(
                    campaign_id=campaign_id,
                    sku_id=sku_id,
                    metric_date=_midnight(day, tz),
                    spend=spend,
                    attributed_revenue=attributed,
                    impressions=impressions,
                    clicks=clicks,
                    conversions=conversions,
                    provenance=DataProvenance.DERIVED,
                )
            )
            if is_recent:
                units_7d += units

        cover_days = _cover_days(sku_id, scenario, policy)
        daily_rate = units_7d / 7 if units_7d else 1.0
        inventory = max(1, int(round(daily_rate * cover_days)))
        remaining = inventory
        for row in reversed(daily_rows):
            eod = remaining
            remaining = remaining + row.units_sold
            sku_daily.append(
                SKUDailyMetric(
                    sku_id=row.sku_id,
                    metric_date=row.metric_date,
                    units_sold=row.units_sold,
                    revenue=row.revenue,
                    cogs=row.cogs,
                    ad_spend=row.ad_spend,
                    refund_loss=row.refund_loss,
                    profit=row.profit,
                    refund_units=row.refund_units,
                    sessions=row.sessions,
                    conversions=row.conversions,
                    avg_rating=row.avg_rating,
                    inventory_eod=eod,
                    provenance=row.provenance,
                )
            )
        profiles[sku_id] = SkuOpsProfile(
            sku_id=sku_id,
            category=category,
            price=price,
            base_price=base_price,
            unit_cost=unit_cost,
            lead_time_days=lead_time_days,
            inventory_available=inventory,
            inventory_on_hand=inventory,
            incoming_inventory=0,
            scenario=scenario,
        )

    sku_daily.sort(key=lambda r: (r.sku_id, r.metric_date))
    campaign_daily.sort(key=lambda r: (r.campaign_id, r.metric_date))
    return SyntheticOpsResult(
        store=StoreState(
            store_id=store_id,
            seller_id=lines[0].seller_id if lines else None,
            name=store_name,
            cash_balance=Decimal("100000.00"),
        ),
        profiles=profiles,
        sku_daily=sku_daily,
        campaign_daily=campaign_daily,
        reviews=reviews,
        missing_sources=["product_cost", "inventory", "ads", "traffic"],
        warnings=["operational fields generated by synthetic_ops"],
    )
