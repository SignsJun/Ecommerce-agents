from datetime import UTC, date, datetime
from decimal import Decimal

from domain.business.sku import SKUDailyMetric, SKUState
from domain.enums import DataProvenance
from services.metrics.aggregate import build_sku_metric_states, window


def _row(day: date, units: int, revenue: str, profit: str) -> SKUDailyMetric:
    return SKUDailyMetric(
        sku_id="S1",
        metric_date=datetime(day.year, day.month, day.day, tzinfo=UTC),
        units_sold=units,
        revenue=Decimal(revenue),
        cogs=Decimal("0"),
        ad_spend=Decimal("0"),
        refund_loss=Decimal("0"),
        profit=Decimal(profit),
        refund_units=0,
        sessions=100,
        conversions=units,
        inventory_eod=10,
        provenance=DataProvenance.DERIVED,
    )


def test_windows():
    as_of = date(2018, 3, 15)
    assert window(as_of, 7) == (date(2018, 3, 9), date(2018, 3, 15))
    assert window(as_of, 7, offset_end=7) == (date(2018, 3, 2), date(2018, 3, 8))


def test_metric_baselines():
    as_of = date(2018, 3, 15)
    rows = []
    d = date(2018, 2, 1)
    while d <= as_of:
        recent = d >= date(2018, 3, 9)
        rows.append(_row(d, 12 if recent else 10, "120" if recent else "100", "20" if recent else "40"))
        d = date.fromordinal(d.toordinal() + 1)
    sku = SKUState(
        sku_id="S1",
        category="x",
        price=Decimal("10"),
        unit_cost=Decimal("4"),
        inventory_on_hand=30,
        inventory_available=30,
        incoming_inventory=0,
        lead_time_days=7,
        units_sold_7d=84,
        units_sold_30d=300,
        revenue_7d=Decimal("840"),
        profit_7d=Decimal("140"),
        profit_margin_7d=0.16,
        refund_rate_7d=0.0,
    )
    metrics = {m.metric_name: m for m in build_sku_metric_states(sku, rows, [], as_of, datetime(2018, 3, 15, tzinfo=UTC))}
    assert metrics["units_sold"].current_value == 84
    assert metrics["units_sold"].baseline_7d == 70
    assert metrics["units_sold"].trend_7d and metrics["units_sold"].trend_7d > 0
    assert metrics["days_of_cover"].current_value == 2.5
