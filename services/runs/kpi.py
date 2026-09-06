from decimal import Decimal

from domain.business.snapshot import BusinessStateSnapshot
from domain.enums import IssueType
from domain.issue.models import Issue
from domain.runs.manifest import RunKPI

_INV = {IssueType.STOCKOUT_RISK, IssueType.EXCESS_INVENTORY}


def compute_kpi(snapshot: BusinessStateSnapshot, issues: list[Issue]) -> RunKPI:
    gmv = sum((s.revenue_7d for s in snapshot.skus.values()), Decimal("0"))
    profit = sum((s.profit_7d for s in snapshot.skus.values()), Decimal("0"))
    spend = sum((c.spend_7d for c in snapshot.campaigns.values()), Decimal("0"))
    rev = sum((c.attributed_revenue_7d for c in snapshot.campaigns.values()), Decimal("0"))
    roas = float(rev / spend) if spend else None
    sku_ids = set(snapshot.skus)
    bad = {i.entity_id for i in issues if i.issue_type in _INV} & sku_ids
    n = len(sku_ids)
    health = (n - len(bad)) / n if n else 1.0
    return RunKPI(gmv=gmv, profit=profit, roas=roas, inventory_health=health, ad_spend=spend)


def kpi_delta(cur: RunKPI, prev: RunKPI) -> dict[str, float | None]:
    def pct(a: object, b: object) -> float | None:
        if a is None or b is None:
            return None
        base = float(b)
        if base == 0:
            return None
        return (float(a) - base) / abs(base)

    return {
        "gmv": pct(cur.gmv, prev.gmv),
        "profit": pct(cur.profit, prev.profit),
        "roas": pct(cur.roas, prev.roas),
        "inventory_health": pct(cur.inventory_health, prev.inventory_health),
    }
