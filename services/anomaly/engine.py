from datetime import datetime
from decimal import Decimal

from domain.business.inventory import days_of_cover, excess_units, inventory_value
from domain.business.metrics import MetricState
from domain.business.snapshot import BusinessStateSnapshot
from domain.common import BusinessPolicyConfig, TimeRange
from domain.enums import DataProvenance, IssueType
from domain.issue.evidence import Evidence
from domain.issue.models import Issue


def _idx(metrics: list[MetricState]) -> dict[tuple[str, str, str], MetricState]:
    return {(m.entity_type, m.entity_id, m.metric_name): m for m in metrics}


def _get(index: dict[tuple[str, str, str], MetricState], entity_type: str, entity_id: str, name: str) -> MetricState | None:
    return index.get((entity_type, entity_id, name))


def _severity(high: bool) -> str:
    return "high" if high else "medium"


def _priority(severity: str, impact: Decimal, urgency: float, confidence: float) -> float:
    score = {"high": 1.0, "medium": 0.6, "low": 0.3}[severity]
    return score * abs(float(impact)) * urgency * confidence


def _evidence(
    evidence_id: str,
    *,
    snapshot_id: str,
    entity_id: str,
    metric: str,
    value: float,
    comparison: str,
    description: str,
    created_at: datetime,
    period: TimeRange | None = None,
    reliability: float = 0.85,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source_type="metric_state",
        source_ref="anomaly_engine",
        entity_type="sku",
        entity_id=entity_id,
        metric=metric,
        value=value,
        comparison=comparison,
        period=period,
        description=description,
        reliability=reliability,
        provenance=DataProvenance.DERIVED,
        tool_name="anomaly_engine",
        tool_version="v1",
        snapshot_id=snapshot_id,
        created_at=created_at,
    )


def detect_issues(
    snapshot: BusinessStateSnapshot,
    metrics: list[MetricState],
    policy: BusinessPolicyConfig,
    detected_at: datetime,
) -> tuple[list[Issue], list[Evidence]]:
    index = _idx(metrics)
    issues: list[Issue] = []
    evidence: list[Evidence] = []
    horizon = policy.impact_horizon_days

    for sku_id, sku in snapshot.skus.items():
        ev_chunk: list[Evidence] = []

        margin = _get(index, "sku", sku_id, "profit_margin")
        revenue = _get(index, "sku", sku_id, "revenue")
        profit = _get(index, "sku", sku_id, "profit")
        if margin and margin.baseline_30d is not None:
            drop = margin.baseline_30d - margin.current_value
            gmv_up = bool(revenue and revenue.trend_7d is not None and revenue.trend_7d >= policy.gmv_up_threshold)
            profit_down = bool(profit and profit.trend_7d is not None and profit.trend_7d < 0)
            if drop >= policy.profit_margin_drop_threshold or (gmv_up and profit_down):
                gap_per_week = Decimal(str(max(drop, 0.0))) * sku.revenue_7d
                impact = (gap_per_week * Decimal(horizon) / Decimal(7)).quantize(Decimal("0.01"))
                e1 = _evidence(
                    f"EV_{sku_id}_margin",
                    snapshot_id=snapshot.snapshot_id,
                    entity_id=sku_id,
                    metric="profit_margin",
                    value=margin.current_value,
                    comparison=f"current_7d {margin.current_value:.4f} vs baseline_30d {margin.baseline_30d:.4f}",
                    description="7d profit margin below 30d baseline",
                    created_at=detected_at,
                )
                ev_chunk.append(e1)
                if revenue and profit:
                    ev_chunk.append(
                        _evidence(
                            f"EV_{sku_id}_gmv_profit",
                            snapshot_id=snapshot.snapshot_id,
                            entity_id=sku_id,
                            metric="profit",
                            value=profit.current_value,
                            comparison=f"revenue_trend_7d={revenue.trend_7d} profit_trend_7d={profit.trend_7d}",
                            description="GMV vs profit scissors",
                            created_at=detected_at,
                        )
                    )
                severity = _severity(drop >= 0.10 or (gmv_up and profit_down))
                issues.append(
                    Issue(
                        issue_id=f"ISSUE_profit_erosion_{sku_id}",
                        issue_type=IssueType.PROFIT_EROSION,
                        entity_type="sku",
                        entity_id=sku_id,
                        detected_at=detected_at,
                        severity=severity,
                        confidence=0.85,
                        estimated_impact=impact,
                        impact_horizon_days=horizon,
                        evidence_ids=[e.evidence_id for e in ev_chunk],
                        status="open",
                        based_on_snapshot_id=snapshot.snapshot_id,
                        priority=_priority(severity, impact, 1.0, 0.85),
                    )
                )
                evidence.extend(ev_chunk)
                ev_chunk = []

        roas = _get(index, "sku", sku_id, "roas")
        ad_spend = _get(index, "sku", sku_id, "ad_spend")
        if roas:
            below_min = roas.current_value < policy.roas_min
            below_base = (
                roas.baseline_30d is not None
                and roas.baseline_30d > 0
                and roas.current_value < roas.baseline_30d * (1 - policy.roas_drop_ratio)
            )
            spend_up = bool(ad_spend and ad_spend.trend_7d is not None and ad_spend.trend_7d >= policy.ad_spend_up_threshold)
            revenue_flat = bool(revenue and (revenue.trend_7d is None or revenue.trend_7d < policy.attributed_revenue_match_threshold))
            if below_min or below_base or (spend_up and revenue_flat):
                target = Decimal(str(policy.roas_min))
                camp = next((c for c in snapshot.campaigns.values() if c.sku_id == sku_id), None)
                spend7 = camp.spend_7d if camp else Decimal("0")
                fair = (camp.attributed_revenue_7d / target).quantize(Decimal("0.01")) if camp and target else Decimal("0")
                impact = max(spend7 - fair, Decimal("0.00"))
                e = _evidence(
                    f"EV_{sku_id}_roas",
                    snapshot_id=snapshot.snapshot_id,
                    entity_id=sku_id,
                    metric="roas",
                    value=roas.current_value,
                    comparison=f"roas_7d={roas.current_value:.3f} min={policy.roas_min} baseline_30d={roas.baseline_30d}",
                    description="ROAS below threshold or spend/revenue mismatch",
                    created_at=detected_at,
                    reliability=0.8,
                )
                severity = _severity(roas.current_value < 1.5)
                issues.append(
                    Issue(
                        issue_id=f"ISSUE_ad_inefficiency_{sku_id}",
                        issue_type=IssueType.AD_INEFFICIENCY,
                        entity_type="sku",
                        entity_id=sku_id,
                        detected_at=detected_at,
                        severity=severity,
                        confidence=0.8,
                        estimated_impact=impact,
                        impact_horizon_days=horizon,
                        evidence_ids=[e.evidence_id],
                        status="open",
                        based_on_snapshot_id=snapshot.snapshot_id,
                        priority=_priority(severity, impact if impact > 0 else Decimal("1"), 1.0, 0.8),
                    )
                )
                evidence.append(e)

        cover = days_of_cover(sku.inventory_available, sku.units_sold_7d)
        cover_metric = _get(index, "sku", sku_id, "days_of_cover")
        threshold = sku.lead_time_days + policy.stockout_safety_days
        if cover < threshold:
            daily_profit = sku.profit_7d / Decimal(7) if sku.units_sold_7d else Decimal("0")
            stockout_days = max(threshold - cover, 0)
            impact = (daily_profit * Decimal(str(stockout_days))).quantize(Decimal("0.01"))
            e = _evidence(
                f"EV_{sku_id}_cover",
                snapshot_id=snapshot.snapshot_id,
                entity_id=sku_id,
                metric="days_of_cover",
                value=cover_metric.current_value if cover_metric else cover,
                comparison=f"days_of_cover={cover:.2f} < lead_time+safety={threshold}",
                description="inventory coverage below lead time plus safety stock",
                created_at=detected_at,
                reliability=0.7,
            )
            severity = _severity(cover < sku.lead_time_days)
            issues.append(
                Issue(
                    issue_id=f"ISSUE_stockout_risk_{sku_id}",
                    issue_type=IssueType.STOCKOUT_RISK,
                    entity_type="sku",
                    entity_id=sku_id,
                    detected_at=detected_at,
                    severity=severity,
                    confidence=0.7,
                    estimated_impact=impact,
                    impact_horizon_days=horizon,
                    evidence_ids=[e.evidence_id],
                    status="open",
                    based_on_snapshot_id=snapshot.snapshot_id,
                    priority=_priority(severity, abs(impact) if impact != 0 else Decimal("1"), 1.5, 0.7),
                )
            )
            evidence.append(e)

        units = _get(index, "sku", sku_id, "units_sold")
        declining = bool(units and units.trend_7d is not None and units.trend_7d <= policy.sales_decline_threshold)
        if cover > policy.excess_cover_days and declining:
            extra = excess_units(sku.inventory_available, sku.units_sold_7d, policy.target_cover_days_max)
            impact = inventory_value(sku.unit_cost, extra)
            e = _evidence(
                f"EV_{sku_id}_excess",
                snapshot_id=snapshot.snapshot_id,
                entity_id=sku_id,
                metric="days_of_cover",
                value=cover,
                comparison=f"days_of_cover={cover:.2f} > {policy.excess_cover_days} and units_trend_7d={units.trend_7d if units else None}",
                description="excess inventory with declining sales",
                created_at=detected_at,
                reliability=0.7,
            )
            severity = _severity(cover >= 90)
            issues.append(
                Issue(
                    issue_id=f"ISSUE_excess_inventory_{sku_id}",
                    issue_type=IssueType.EXCESS_INVENTORY,
                    entity_type="sku",
                    entity_id=sku_id,
                    detected_at=detected_at,
                    severity=severity,
                    confidence=0.7,
                    estimated_impact=impact,
                    impact_horizon_days=horizon,
                    evidence_ids=[e.evidence_id],
                    status="open",
                    based_on_snapshot_id=snapshot.snapshot_id,
                    priority=_priority(severity, impact if impact > 0 else Decimal("1"), 0.8, 0.7),
                )
            )
            evidence.append(e)

    issues.sort(key=lambda i: i.priority or 0, reverse=True)
    return issues, evidence
