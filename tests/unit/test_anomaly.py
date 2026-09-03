from datetime import UTC, datetime
from decimal import Decimal

from domain.business.metrics import MetricState
from domain.business.snapshot import BusinessStateSnapshot
from domain.common import BusinessPolicyConfig, DataQualityReport, StoreState
from domain.business.campaign import CampaignState
from domain.business.sku import SKUState
from domain.enums import DataProvenance, IssueType
from services.anomaly.engine import detect_issues


NOW = datetime(2018, 3, 16, tzinfo=UTC)


def _metric(name: str, sku_id: str, current: float, baseline_7d: float | None, baseline_30d: float | None, trend_7d: float | None) -> MetricState:
    return MetricState(
        metric_name=name,
        entity_type="sku",
        entity_id=sku_id,
        current_value=current,
        baseline_7d=baseline_7d,
        baseline_30d=baseline_30d,
        trend_7d=trend_7d,
        provenance=DataProvenance.DERIVED,
        calculated_at=NOW,
    )


def _sku(**kwargs) -> SKUState:
    base = dict(
        sku_id="S1",
        category="x",
        price=Decimal("10"),
        unit_cost=Decimal("4"),
        inventory_on_hand=100,
        inventory_available=100,
        incoming_inventory=0,
        lead_time_days=10,
        units_sold_7d=70,
        units_sold_30d=300,
        revenue_7d=Decimal("700"),
        profit_7d=Decimal("100"),
        profit_margin_7d=0.2,
        refund_rate_7d=0.05,
    )
    base.update(kwargs)
    return SKUState(**base)


def _snap(sku: SKUState, campaign: CampaignState | None = None) -> BusinessStateSnapshot:
    campaigns = {}
    if campaign:
        campaigns[campaign.campaign_id] = campaign
    return BusinessStateSnapshot(
        snapshot_id="SNAP_1",
        version=1,
        created_at=NOW,
        data_freshness_at=NOW,
        store=StoreState(store_id="ST", name="n", cash_balance=Decimal("1")),
        skus={sku.sku_id: sku},
        campaigns=campaigns,
        data_quality=DataQualityReport(
            completeness_score=1,
            freshness_score=1,
            consistency_score=1,
            missing_sources=[],
            warnings=[],
        ),
    )


def test_detect_profit_erosion():
    sku = _sku()
    metrics = [
        _metric("profit_margin", "S1", 0.20, 0.30, 0.31, -0.3),
        _metric("revenue", "S1", 800, 700, 700, 0.14),
        _metric("profit", "S1", 50, 200, 200, -0.75),
        _metric("roas", "S1", 3.0, 3.0, 3.0, 0.0),
        _metric("ad_spend", "S1", 100, 100, 100, 0.0),
        _metric("units_sold", "S1", 70, 70, 70, 0.0),
        _metric("days_of_cover", "S1", 20, None, None, None),
    ]
    issues, ev = detect_issues(_snap(sku), metrics, BusinessPolicyConfig(), NOW)
    assert any(i.issue_type == IssueType.PROFIT_EROSION for i in issues)
    assert ev and issues[0].evidence_ids


def test_detect_ad_stockout_excess():
    sku = _sku(inventory_available=20, units_sold_7d=70, lead_time_days=14)
    camp = CampaignState(
        campaign_id="C1",
        sku_id="S1",
        status="active",
        daily_budget=Decimal("50"),
        spend_7d=Decimal("400"),
        attributed_revenue_7d=Decimal("300"),
        impressions_7d=1,
        clicks_7d=1,
        conversions_7d=1,
        roas_7d=0.75,
        acos_7d=1.3,
    )
    metrics = [
        _metric("profit_margin", "S1", 0.30, 0.30, 0.30, 0.0),
        _metric("revenue", "S1", 700, 700, 700, 0.0),
        _metric("profit", "S1", 100, 100, 100, 0.0),
        _metric("roas", "S1", 0.75, 3.0, 3.0, -0.75),
        _metric("ad_spend", "S1", 400, 100, 100, 3.0),
        _metric("units_sold", "S1", 70, 70, 70, 0.0),
        _metric("days_of_cover", "S1", 2.0, None, None, None),
    ]
    issues, _ = detect_issues(_snap(sku, camp), metrics, BusinessPolicyConfig(), NOW)
    types = {i.issue_type for i in issues}
    assert IssueType.AD_INEFFICIENCY in types
    assert IssueType.STOCKOUT_RISK in types

    excess_sku = _sku(sku_id="S2", inventory_available=900, units_sold_7d=21)
    excess_metrics = [
        _metric("profit_margin", "S2", 0.30, 0.30, 0.30, 0.0),
        _metric("revenue", "S2", 100, 200, 200, -0.5),
        _metric("profit", "S2", 30, 60, 60, -0.5),
        _metric("roas", "S2", 3.0, 3.0, 3.0, 0.0),
        _metric("ad_spend", "S2", 10, 10, 10, 0.0),
        _metric("units_sold", "S2", 21, 70, 70, -0.7),
        _metric("days_of_cover", "S2", 300, None, None, None),
    ]
    issues2, _ = detect_issues(_snap(excess_sku), excess_metrics, BusinessPolicyConfig(), NOW)
    assert any(i.issue_type == IssueType.EXCESS_INVENTORY for i in issues2)
