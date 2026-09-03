from decimal import Decimal

from domain.base import FrozenModel
from domain.business.sku import SKUDailyMetric
from domain.common import BusinessPolicyConfig


class ProfitBreakdown(FrozenModel):
    revenue: Decimal
    cogs: Decimal
    ad_spend: Decimal
    refund_loss: Decimal
    profit: Decimal
    profit_margin: float


def as_money(value: Decimal | int | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def compute_cogs(unit_cost: Decimal, units_sold: int) -> Decimal:
    return as_money(unit_cost) * units_sold


def compute_refund_loss(revenue: Decimal, refund_rate: float) -> Decimal:
    return (as_money(revenue) * Decimal(str(refund_rate))).quantize(Decimal("0.01"))


def compute_profit(
    revenue: Decimal,
    cogs: Decimal,
    ad_spend: Decimal,
    refund_loss: Decimal,
    policy: BusinessPolicyConfig | None = None,
) -> Decimal:
    _ = policy
    return as_money(revenue) - as_money(cogs) - as_money(ad_spend) - as_money(refund_loss)


def profit_margin(profit: Decimal, revenue: Decimal) -> float:
    if as_money(revenue) == 0:
        return 0.0
    return float(as_money(profit) / as_money(revenue))


def decompose_profit(rows: list[SKUDailyMetric]) -> ProfitBreakdown:
    revenue = sum((r.revenue for r in rows), Decimal("0"))
    cogs = sum((r.cogs for r in rows), Decimal("0"))
    ad_spend = sum((r.ad_spend for r in rows), Decimal("0"))
    refund_loss = sum((r.refund_loss for r in rows), Decimal("0"))
    profit = compute_profit(revenue, cogs, ad_spend, refund_loss)
    return ProfitBreakdown(
        revenue=revenue,
        cogs=cogs,
        ad_spend=ad_spend,
        refund_loss=refund_loss,
        profit=profit,
        profit_margin=profit_margin(profit, revenue),
    )
