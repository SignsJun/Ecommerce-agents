from datetime import date
from decimal import Decimal

from domain.business.inventory import days_of_cover
from domain.business.snapshot import BusinessStateSnapshot
from domain.enums import DataProvenance
from services.metrics.aggregate import (
    build_campaign_metric_states,
    build_sku_metric_states,
    filter_sku,
    in_window,
    window,
)
from services.profit.engine import decompose_profit
from tools.diagnosis.base import ToolContext, ToolResult, fail, make_evidence, ok
from tools.diagnosis.payloads import (
    CampaignBreakdownPayload,
    CampaignShare,
    CampaignTrendPayload,
    CampaignTrendPoint,
    ConversionFunnelPayload,
    InventoryDay,
    InventoryProjectionPayload,
    IssueContextPayload,
    MetricTrendPayload,
    PeerComparePayload,
    PeerRow,
    PriceHistoryPayload,
    PricePoint,
    ProfitDecomposePayload,
    PromotionHistoryPayload,
    RefundBreakdownPayload,
    ReviewAnalysisPayload,
    SeriesPoint,
    SkuSummaryPayload,
)

_SKU_METRICS = {
    "profit_margin",
    "revenue",
    "profit",
    "units_sold",
    "refund_rate",
    "ad_spend",
    "roas",
    "days_of_cover",
}
_CAMPAIGN_METRICS = {"roas", "ad_spend", "attributed_revenue"}


def _require_snapshot(ctx: ToolContext, tool_name: str, arguments: dict) -> BusinessStateSnapshot | ToolResult:
    snap = ctx.snapshot()
    if snap is None:
        return fail(ctx, tool_name, "not_found", "snapshot not found", arguments)
    return snap


def _require_sku(ctx: ToolContext, tool_name: str, sku_id: str, arguments: dict):
    snap = _require_snapshot(ctx, tool_name, arguments)
    if not isinstance(snap, BusinessStateSnapshot):
        return snap
    sku = snap.skus.get(sku_id)
    if sku is None:
        return fail(ctx, tool_name, "not_found", f"sku not found: {sku_id}", arguments)
    return snap, sku


def get_issue_context(ctx: ToolContext, issue_id: str) -> ToolResult:
    name = "get_issue_context"
    args = {"issue_id": issue_id}
    issue = ctx.issue_repo.get_issue(issue_id)
    if issue is None:
        return fail(ctx, name, "not_found", f"issue not found: {issue_id}", args)
    snap = ctx.snapshot()
    sku = None
    if snap is not None and issue.entity_type == "sku":
        sku = snap.skus.get(issue.entity_id)
    evidence = ctx.issue_repo.list_evidence(issue.evidence_ids)
    payload = IssueContextPayload(issue=issue, evidence=evidence, sku=sku)
    ev = make_evidence(
        ctx,
        name,
        entity_type=issue.entity_type,
        entity_id=issue.entity_id,
        metric="issue_severity",
        value=issue.severity,
        description="issue context loaded",
        comparison=issue.issue_type.value,
    )
    return ok(ctx, name, payload, [ev], args)


def get_sku_summary(ctx: ToolContext, sku_id: str) -> ToolResult:
    name = "get_sku_summary"
    args = {"sku_id": sku_id}
    loaded = _require_sku(ctx, name, sku_id, args)
    if isinstance(loaded, ToolResult):
        return loaded
    _, sku = loaded
    ev = make_evidence(
        ctx,
        name,
        entity_type="sku",
        entity_id=sku_id,
        metric="profit_margin_7d",
        value=sku.profit_margin_7d,
        description="sku 7d summary",
        comparison=f"cover_units={sku.inventory_available} sold_7d={sku.units_sold_7d}",
    )
    return ok(ctx, name, SkuSummaryPayload(sku=sku), [ev], args)


def get_metric_trend(ctx: ToolContext, entity_type: str, entity_id: str, metric: str, window_name: str) -> ToolResult:
    name = "get_metric_trend"
    args = {"entity_type": entity_type, "entity_id": entity_id, "metric": metric, "window": window_name}
    snap = _require_snapshot(ctx, name, args)
    if not isinstance(snap, BusinessStateSnapshot):
        return snap
    days = 7 if window_name == "7d" else 30 if window_name == "30d" else None
    if days is None:
        return fail(ctx, name, "not_found", f"unknown window: {window_name}", args)
    start, end = window(ctx.as_of, days)
    if entity_type == "sku":
        if metric not in _SKU_METRICS:
            return fail(ctx, name, "not_found", f"unknown metric: {metric}", args)
        sku = snap.skus.get(entity_id)
        if sku is None:
            return fail(ctx, name, "not_found", f"sku not found: {entity_id}", args)
        rows = ctx.business_repo.list_all_sku_daily()
        camps = ctx.business_repo.list_all_campaign_daily()
        states = {m.metric_name: m for m in build_sku_metric_states(sku, rows, camps, ctx.as_of, ctx.now)}
        if window_name == "30d":
            chunk = filter_sku(rows, entity_id, start, end)
            current = _series_value(metric, chunk, sku, camps, start, end)
            metric_state = states[metric].model_copy(update={"current_value": current}) if metric in states else None
        else:
            metric_state = states.get(metric)
        if metric_state is None:
            return fail(ctx, name, "empty_result", f"no metric {metric}", args)
        series = _sku_series(metric, filter_sku(rows, entity_id, start, end), sku, camps)
    elif entity_type == "campaign":
        if metric not in _CAMPAIGN_METRICS:
            return fail(ctx, name, "not_found", f"unknown metric: {metric}", args)
        camp = snap.campaigns.get(entity_id)
        if camp is None:
            return fail(ctx, name, "not_found", f"campaign not found: {entity_id}", args)
        rows = ctx.business_repo.list_all_campaign_daily()
        states = {m.metric_name: m for m in build_campaign_metric_states(camp, rows, ctx.as_of, ctx.now)}
        metric_state = states.get(metric)
        if metric_state is None:
            return fail(ctx, name, "empty_result", f"no metric {metric}", args)
        series = _campaign_series(metric, [r for r in rows if r.campaign_id == entity_id and in_window(r.metric_date, start, end)])
    else:
        return fail(ctx, name, "not_found", f"unknown entity_type: {entity_type}", args)
    payload = MetricTrendPayload(metric=metric_state, series=series)
    ev = make_evidence(
        ctx,
        name,
        entity_type=entity_type,
        entity_id=entity_id,
        metric=metric,
        value=metric_state.current_value,
        description=f"{metric} {window_name} trend",
        comparison=f"trend_7d={metric_state.trend_7d}",
        period=ctx.period(start, end),
    )
    return ok(ctx, name, payload, [ev], args)


def _series_value(metric: str, rows, sku, camps, start, end) -> float:
    if metric == "units_sold":
        return float(sum(r.units_sold for r in rows))
    if metric == "revenue":
        return float(sum((r.revenue for r in rows), Decimal("0")))
    if metric == "profit":
        return float(sum((r.profit for r in rows), Decimal("0")))
    if metric == "ad_spend":
        return float(sum((r.ad_spend for r in rows), Decimal("0")))
    if metric == "refund_rate":
        units = sum(r.units_sold for r in rows)
        return (sum(r.refund_units for r in rows) / units) if units else 0.0
    if metric == "profit_margin":
        br = decompose_profit(rows)
        return br.profit_margin
    if metric == "roas":
        cr = [r for r in camps if r.sku_id == sku.sku_id and in_window(r.metric_date, start, end)]
        spend = sum((r.spend for r in cr), Decimal("0"))
        rev = sum((r.attributed_revenue for r in cr), Decimal("0"))
        return float(rev / spend) if spend else 0.0
    return days_of_cover(sku.inventory_available, sku.units_sold_7d)


def _sku_series(metric: str, rows, sku, camps) -> list[SeriesPoint]:
    points: list[SeriesPoint] = []
    demand = sku.units_sold_7d / 7 if sku.units_sold_7d else 0.0
    for row in sorted(rows, key=lambda r: r.metric_date):
        d = row.metric_date.date()
        if metric == "units_sold":
            val = float(row.units_sold)
        elif metric == "revenue":
            val = float(row.revenue)
        elif metric == "profit":
            val = float(row.profit)
        elif metric == "ad_spend":
            val = float(row.ad_spend)
        elif metric == "refund_rate":
            val = (row.refund_units / row.units_sold) if row.units_sold else 0.0
        elif metric == "profit_margin":
            val = float(row.profit / row.revenue) if row.revenue else 0.0
        elif metric == "roas":
            cr = [c for c in camps if c.sku_id == sku.sku_id and c.metric_date.date() == d]
            spend = sum((c.spend for c in cr), Decimal("0"))
            rev = sum((c.attributed_revenue for c in cr), Decimal("0"))
            val = float(rev / spend) if spend else 0.0
        else:
            val = (row.inventory_eod / demand) if demand else 999.0
        points.append(SeriesPoint(metric_date=d, value=val))
    return points


def _campaign_series(metric: str, rows) -> list[SeriesPoint]:
    points: list[SeriesPoint] = []
    for row in sorted(rows, key=lambda r: r.metric_date):
        if metric == "ad_spend":
            val = float(row.spend)
        elif metric == "attributed_revenue":
            val = float(row.attributed_revenue)
        else:
            val = float(row.attributed_revenue / row.spend) if row.spend else 0.0
        points.append(SeriesPoint(metric_date=row.metric_date.date(), value=val))
    return points


def decompose_profit_tool(
    ctx: ToolContext,
    sku_id: str,
    period_a_start: date,
    period_a_end: date,
    period_b_start: date,
    period_b_end: date,
) -> ToolResult:
    name = "decompose_profit"
    args = {
        "sku_id": sku_id,
        "period_a_start": period_a_start.isoformat(),
        "period_a_end": period_a_end.isoformat(),
        "period_b_start": period_b_start.isoformat(),
        "period_b_end": period_b_end.isoformat(),
    }
    loaded = _require_sku(ctx, name, sku_id, args)
    if isinstance(loaded, ToolResult):
        return loaded
    a0, a1 = ctx.bounds(period_a_start, period_a_end)
    b0, b1 = ctx.bounds(period_b_start, period_b_end)
    rows_a = ctx.business_repo.list_sku_daily(sku_id, a0, a1)
    rows_b = ctx.business_repo.list_sku_daily(sku_id, b0, b1)
    if not rows_a and not rows_b:
        return fail(ctx, name, "empty_result", "no daily metrics in periods", args)
    pa = decompose_profit(rows_a)
    pb = decompose_profit(rows_b)
    payload = ProfitDecomposePayload(
        sku_id=sku_id,
        period_a=pa,
        period_b=pb,
        delta_revenue=pa.revenue - pb.revenue,
        delta_cogs=pa.cogs - pb.cogs,
        delta_ad_spend=pa.ad_spend - pb.ad_spend,
        delta_refund_loss=pa.refund_loss - pb.refund_loss,
        delta_profit=pa.profit - pb.profit,
    )
    ev = make_evidence(
        ctx,
        name,
        entity_type="sku",
        entity_id=sku_id,
        metric="profit",
        value=float(payload.delta_profit),
        description="profit decompose period_a minus period_b",
        comparison=f"d_ad={payload.delta_ad_spend} d_refund={payload.delta_refund_loss}",
        period=ctx.period(period_a_start, period_a_end),
    )
    return ok(ctx, name, payload, [ev], args)


def get_conversion_funnel(ctx: ToolContext, sku_id: str) -> ToolResult:
    name = "get_conversion_funnel"
    args = {"sku_id": sku_id}
    loaded = _require_sku(ctx, name, sku_id, args)
    if isinstance(loaded, ToolResult):
        return loaded
    start, end = window(ctx.as_of, 7)
    lo, hi = ctx.bounds(start, end)
    sku_rows = ctx.business_repo.list_sku_daily(sku_id, lo, hi)
    camp_ids = ctx.business_repo.list_campaigns_for_sku(sku_id)
    impressions = 0
    clicks = 0
    for cid in camp_ids:
        for row in ctx.business_repo.list_campaign_daily(cid, lo, hi):
            impressions += row.impressions
            clicks += row.clicks
    sessions = sum(r.sessions for r in sku_rows)
    conversions = sum(r.conversions for r in sku_rows)
    units = sum(r.units_sold for r in sku_rows)
    payload = ConversionFunnelPayload(
        sku_id=sku_id,
        impressions=impressions,
        clicks=clicks,
        sessions=sessions,
        conversions=conversions,
        units_sold=units,
        click_through_rate=(clicks / impressions) if impressions else None,
        session_cvr=(conversions / sessions) if sessions else None,
        purchase_rate=(units / conversions) if conversions else None,
    )
    ev = make_evidence(
        ctx,
        name,
        entity_type="sku",
        entity_id=sku_id,
        metric="session_cvr",
        value=payload.session_cvr,
        description="7d conversion funnel",
        comparison=f"impr={impressions} clicks={clicks} sessions={sessions}",
        period=ctx.period(start, end),
    )
    return ok(ctx, name, payload, [ev], args)


def get_campaign_breakdown(ctx: ToolContext, sku_id: str) -> ToolResult:
    name = "get_campaign_breakdown"
    args = {"sku_id": sku_id}
    loaded = _require_sku(ctx, name, sku_id, args)
    if isinstance(loaded, ToolResult):
        return loaded
    snap, _ = loaded
    start, end = window(ctx.as_of, 7)
    lo, hi = ctx.bounds(start, end)
    shares: list[CampaignShare] = []
    total = Decimal("0")
    for cid in ctx.business_repo.list_campaigns_for_sku(sku_id):
        rows = ctx.business_repo.list_campaign_daily(cid, lo, hi)
        spend = sum((r.spend for r in rows), Decimal("0"))
        attr = sum((r.attributed_revenue for r in rows), Decimal("0"))
        total += spend
        shares.append(
            CampaignShare(
                campaign_id=cid,
                spend=spend,
                attributed_revenue=attr,
                roas=float(attr / spend) if spend else None,
                acos=float(spend / attr) if attr else None,
                spend_share=0.0,
            )
        )
    if not shares:
        return fail(ctx, name, "empty_result", "no campaigns", args)
    out = []
    for s in shares:
        share = float(s.spend / total) if total else 0.0
        out.append(s.model_copy(update={"spend_share": share}))
    payload = CampaignBreakdownPayload(sku_id=sku_id, campaigns=out)
    top = max(out, key=lambda x: x.spend)
    ev = make_evidence(
        ctx,
        name,
        entity_type="sku",
        entity_id=sku_id,
        metric="ad_spend",
        value=float(top.spend),
        description="campaign spend mix 7d",
        comparison=f"top={top.campaign_id} share={top.spend_share}",
        period=ctx.period(start, end),
    )
    return ok(ctx, name, payload, [ev], args)


def get_campaign_trend(ctx: ToolContext, campaign_id: str) -> ToolResult:
    name = "get_campaign_trend"
    args = {"campaign_id": campaign_id}
    snap = _require_snapshot(ctx, name, args)
    if not isinstance(snap, BusinessStateSnapshot):
        return snap
    camp = snap.campaigns.get(campaign_id)
    sku_id = camp.sku_id if camp else None
    if sku_id is None:
        for row in ctx.business_repo.list_all_campaign_daily():
            if row.campaign_id == campaign_id:
                sku_id = row.sku_id
                break
    if sku_id is None:
        return fail(ctx, name, "not_found", f"campaign not found: {campaign_id}", args)
    start, end = window(ctx.as_of, 30)
    lo, hi = ctx.bounds(start, end)
    rows = ctx.business_repo.list_campaign_daily(campaign_id, lo, hi)
    if not rows:
        return fail(ctx, name, "empty_result", "no campaign daily rows", args)
    points = []
    for row in sorted(rows, key=lambda r: r.metric_date):
        points.append(
            CampaignTrendPoint(
                metric_date=row.metric_date.date(),
                spend=row.spend,
                attributed_revenue=row.attributed_revenue,
                roas=float(row.attributed_revenue / row.spend) if row.spend else None,
            )
        )
    payload = CampaignTrendPayload(campaign_id=campaign_id, sku_id=sku_id, points=points)
    last = points[-1]
    ev = make_evidence(
        ctx,
        name,
        entity_type="campaign",
        entity_id=campaign_id,
        metric="roas",
        value=last.roas,
        description="campaign 30d spend/roas series",
        period=ctx.period(start, end),
    )
    return ok(ctx, name, payload, [ev], args)


def get_inventory_projection(ctx: ToolContext, sku_id: str) -> ToolResult:
    name = "get_inventory_projection"
    args = {"sku_id": sku_id}
    loaded = _require_sku(ctx, name, sku_id, args)
    if isinstance(loaded, ToolResult):
        return loaded
    _, sku = loaded
    horizon = ctx.policy.impact_horizon_days
    daily = sku.units_sold_7d / 7 if sku.units_sold_7d else 0.0
    inv = float(sku.inventory_available)
    first = None
    days: list[InventoryDay] = []
    for offset in range(1, horizon + 1):
        arrival = sku.incoming_inventory if offset == sku.lead_time_days else 0
        inv += arrival
        sales = min(daily, inv)
        inv -= sales
        stockout = daily > 0 and inv <= 1e-9
        if stockout and first is None:
            first = offset
        days.append(
            InventoryDay(
                day_offset=offset,
                inventory_eod=inv,
                expected_sales=sales,
                arrival=arrival,
                stockout=stockout,
            )
        )
    payload = InventoryProjectionPayload(
        sku_id=sku_id,
        horizon_days=horizon,
        daily_demand=daily,
        days=days,
        first_stockout_day=first,
    )
    ev = make_evidence(
        ctx,
        name,
        entity_type="sku",
        entity_id=sku_id,
        metric="first_stockout_day",
        value=first if first is not None else -1,
        description="deterministic inventory projection",
        comparison=f"demand={daily:.2f} available={sku.inventory_available} lt={sku.lead_time_days}",
    )
    return ok(ctx, name, payload, [ev], args)


def get_refund_breakdown(ctx: ToolContext, sku_id: str) -> ToolResult:
    name = "get_refund_breakdown"
    args = {"sku_id": sku_id}
    loaded = _require_sku(ctx, name, sku_id, args)
    if isinstance(loaded, ToolResult):
        return loaded
    start, end = window(ctx.as_of, 7)
    lo, hi = ctx.bounds(start, end)
    rows = ctx.business_repo.list_sku_daily(sku_id, lo, hi)
    units = sum(r.units_sold for r in rows)
    refund_units = sum(r.refund_units for r in rows)
    refund_loss = sum((r.refund_loss for r in rows), Decimal("0"))
    reviews = ctx.business_repo.list_reviews(sku_id, lo, hi)
    low = sum(1 for r in reviews if r.score <= 2)
    payload = RefundBreakdownPayload(
        sku_id=sku_id,
        refund_units=refund_units,
        refund_loss=refund_loss,
        refund_rate=(refund_units / units) if units else 0.0,
        low_score_share=(low / len(reviews)) if reviews else None,
    )
    ev = make_evidence(
        ctx,
        name,
        entity_type="sku",
        entity_id=sku_id,
        metric="refund_rate",
        value=payload.refund_rate,
        description="7d refund breakdown",
        comparison=f"loss={refund_loss} low_score={payload.low_score_share}",
        period=ctx.period(start, end),
        provenance=DataProvenance.DERIVED,
    )
    return ok(ctx, name, payload, [ev], args)


def analyze_reviews(ctx: ToolContext, sku_id: str, window_name: str) -> ToolResult:
    name = "analyze_reviews"
    args = {"sku_id": sku_id, "window": window_name}
    loaded = _require_sku(ctx, name, sku_id, args)
    if isinstance(loaded, ToolResult):
        return loaded
    days = 7 if window_name == "7d" else 30 if window_name == "30d" else None
    if days is None:
        return fail(ctx, name, "not_found", f"unknown window: {window_name}", args)
    start, end = window(ctx.as_of, days)
    lo, hi = ctx.bounds(start, end)
    reviews = ctx.business_repo.list_reviews(sku_id, lo, hi)
    counts = [0, 0, 0, 0, 0]
    for r in reviews:
        if 1 <= r.score <= 5:
            counts[r.score - 1] += 1
    n = len(reviews)
    low = counts[0] + counts[1]
    avg = (sum((i + 1) * c for i, c in enumerate(counts)) / n) if n else None
    payload = ReviewAnalysisPayload(
        sku_id=sku_id,
        n=n,
        score_counts=counts,
        avg_score=avg,
        low_score_share=(low / n) if n else 0.0,
    )
    ev = make_evidence(
        ctx,
        name,
        entity_type="sku",
        entity_id=sku_id,
        metric="low_score_share",
        value=payload.low_score_share,
        description="review score distribution",
        comparison=f"n={n} counts={counts}",
        period=ctx.period(start, end),
        provenance=DataProvenance.OBSERVED,
        reliability=0.9,
    )
    return ok(ctx, name, payload, [ev], args)


def compare_peer_skus(ctx: ToolContext, sku_id: str, metrics: str) -> ToolResult:
    name = "compare_peer_skus"
    args = {"sku_id": sku_id, "metrics": metrics}
    loaded = _require_sku(ctx, name, sku_id, args)
    if isinstance(loaded, ToolResult):
        return loaded
    snap, sku = loaded
    wanted = {m.strip() for m in metrics.split(",") if m.strip()}
    rows = ctx.business_repo.list_all_sku_daily()
    camps = ctx.business_repo.list_all_campaign_daily()
    peers: list[PeerRow] = []
    for other in snap.skus.values():
        if other.sku_id == sku_id or other.category != sku.category:
            continue
        states = {m.metric_name: m for m in build_sku_metric_states(other, rows, camps, ctx.as_of, ctx.now)}
        peers.append(
            PeerRow(
                sku_id=other.sku_id,
                profit_margin=states["profit_margin"].current_value if "profit_margin" in wanted else None,
                roas=states["roas"].current_value if "roas" in wanted else None,
                days_of_cover=states["days_of_cover"].current_value if "days_of_cover" in wanted else None,
            )
        )
    if not peers:
        return fail(ctx, name, "empty_result", "no peer skus in category", args)
    payload = PeerComparePayload(sku_id=sku_id, category=sku.category, peers=peers)
    ev = make_evidence(
        ctx,
        name,
        entity_type="sku",
        entity_id=sku_id,
        metric="peer_count",
        value=len(peers),
        description="same-category peer compare",
        comparison=sku.category,
    )
    return ok(ctx, name, payload, [ev], args)


def get_price_history(ctx: ToolContext, sku_id: str) -> ToolResult:
    name = "get_price_history"
    args = {"sku_id": sku_id}
    loaded = _require_sku(ctx, name, sku_id, args)
    if isinstance(loaded, ToolResult):
        return loaded
    start, end = window(ctx.as_of, 30)
    lo, hi = ctx.bounds(start, end)
    rows = ctx.business_repo.list_sku_daily(sku_id, lo, hi)
    points = []
    for row in sorted(rows, key=lambda r: r.metric_date):
        if row.units_sold <= 0:
            continue
        points.append(
            PricePoint(
                metric_date=row.metric_date.date(),
                price=(row.revenue / row.units_sold).quantize(Decimal("0.01")),
                units_sold=row.units_sold,
            )
        )
    if not points:
        return fail(ctx, name, "empty_result", "no priced days", args)
    payload = PriceHistoryPayload(sku_id=sku_id, points=points)
    ev = make_evidence(
        ctx,
        name,
        entity_type="sku",
        entity_id=sku_id,
        metric="price",
        value=float(points[-1].price),
        description="implied daily price",
        comparison=f"n={len(points)} last={points[-1].price}",
        period=ctx.period(start, end),
    )
    return ok(ctx, name, payload, [ev], args)


def get_promotion_history(ctx: ToolContext, sku_id: str) -> ToolResult:
    name = "get_promotion_history"
    args = {"sku_id": sku_id}
    loaded = _require_sku(ctx, name, sku_id, args)
    if isinstance(loaded, ToolResult):
        return loaded
    payload = PromotionHistoryPayload(sku_id=sku_id, promotions=[], missing_sources=["promotions"])
    return ok(ctx, name, payload, [], args, produces_evidence=False)


def project_horizon_dates(as_of: date) -> tuple[date, date, date, date]:
    a_start, a_end = window(as_of, 7)
    b_start, b_end = window(as_of, 7, offset_end=7)
    return a_start, a_end, b_start, b_end


def project_baseline_30d(as_of: date) -> tuple[date, date]:
    return window(as_of, 30)
