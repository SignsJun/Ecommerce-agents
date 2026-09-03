from decimal import Decimal

from domain.common import BusinessPolicyConfig
from services.profit.engine import (
    compute_cogs,
    compute_profit,
    compute_refund_loss,
    decompose_profit,
    profit_margin,
)
from domain.business.sku import SKUDailyMetric
from domain.enums import DataProvenance
from datetime import UTC, datetime


def test_profit_formula():
    revenue = Decimal("1000.00")
    cogs = compute_cogs(Decimal("40.00"), 10)
    ad = Decimal("133.33")
    refund = compute_refund_loss(revenue, 0.1)
    profit = compute_profit(revenue, cogs, ad, refund, BusinessPolicyConfig())
    assert cogs == Decimal("400.00")
    assert refund == Decimal("100.00")
    assert profit == Decimal("366.67")
    assert abs(profit_margin(profit, revenue) - 0.36667) < 1e-4


def test_decompose_profit_sums_rows():
    row = SKUDailyMetric(
        sku_id="S1",
        metric_date=datetime(2018, 3, 15, tzinfo=UTC),
        units_sold=2,
        revenue=Decimal("20.00"),
        cogs=Decimal("8.00"),
        ad_spend=Decimal("2.00"),
        refund_loss=Decimal("1.00"),
        profit=Decimal("9.00"),
        refund_units=0,
        sessions=100,
        conversions=2,
        inventory_eod=10,
        provenance=DataProvenance.DERIVED,
    )
    br = decompose_profit([row, row])
    assert br.revenue == Decimal("40.00")
    assert br.profit == Decimal("18.00")
    assert br.profit_margin == 0.45
