from decimal import Decimal

from agents.diagnosis.causal_graph import PREFLIGHT_TOOLS, SCREEN_FAMILIES
from agents.diagnosis.policy import MATERIALITY_ACTIVE, MATERIALITY_POSSIBLE
from domain.diagnosis.cause import CauseInvestigation, CauseStatus
from domain.diagnosis.state import DiagnosisState
from domain.enums import IssueType
from tools.diagnosis.base import ToolContext, ToolResult
from tools.diagnosis.handlers import project_horizon_dates
from tools.diagnosis.payloads import CampaignBreakdownPayload, InventoryProjectionPayload, ProfitDecomposePayload
from tools.diagnosis.registry import invoke


def _score_status(score: float) -> CauseStatus:
    if score > MATERIALITY_ACTIVE:
        return CauseStatus.ACTIVE
    if score > MATERIALITY_POSSIBLE:
        return CauseStatus.SCREENED_POSSIBLE
    return CauseStatus.SCREENED_NON_MATERIAL


def _item(cause_type: str, status: CauseStatus, score: float | None, reason: str) -> CauseInvestigation:
    return CauseInvestigation(
        cause_type=cause_type,
        status=status,
        screening_score=score,
        materiality_score=score,
        activation_reason=reason if status == CauseStatus.ACTIVE else None,
        resolution_reason=None if status == CauseStatus.ACTIVE else reason,
        was_activated=status == CauseStatus.ACTIVE,
    )


def _blocked(families: tuple[str, ...], reason: str) -> list[CauseInvestigation]:
    return [_item(name, CauseStatus.BLOCKED_BY_DATA, None, reason) for name in families]


def _profit_causes(payload: ProfitDecomposePayload) -> list[CauseInvestigation]:
    scale = abs(payload.delta_profit)
    harms = {
        "revenue": max(-payload.delta_revenue, Decimal("0")),
        "cogs": max(payload.delta_cogs, Decimal("0")),
        "ad_efficiency": max(payload.delta_ad_spend, Decimal("0")),
        "refunds": max(payload.delta_refund_loss, Decimal("0")),
    }
    total_harm = sum(harms.values(), Decimal("0"))
    denom = scale if scale > 0 else (total_harm if total_harm > 0 else Decimal("1"))
    out = []
    for name, harm in harms.items():
        score = float(harm / denom)
        status = _score_status(score)
        reason = f"contribution_ratio={score:.3f}"
        out.append(_item(name, status, score, reason))
    return out


def _ad_causes(payload: CampaignBreakdownPayload, roas_min: float) -> list[CauseInvestigation]:
    low = [c for c in payload.campaigns if c.roas is None or c.roas < roas_min]
    ad_score = 1.0 if low else 0.0
    mix_score = 0.1 if len(payload.campaigns) > 1 else 0.0
    return [
        _item("ad_efficiency", _score_status(ad_score), ad_score, "low_roas" if low else "roas_ok"),
        _item("campaign_mix", _score_status(mix_score), mix_score, "multi_campaign" if mix_score else "single_campaign"),
    ]


def _inventory_causes(payload: InventoryProjectionPayload, issue_type: IssueType) -> list[CauseInvestigation]:
    if issue_type == IssueType.STOCKOUT_RISK:
        active = payload.first_stockout_day is not None
        score = 1.0 if active else 0.2
        return [_item("inventory", _score_status(score), score, "stockout_projection")]
    cover_high = payload.first_stockout_day is None
    return [
        _item("excess_inventory", CauseStatus.ACTIVE if cover_high else CauseStatus.SCREENED_POSSIBLE, 0.8, "excess_cover"),
        _item("demand_decline", CauseStatus.SCREENED_POSSIBLE, 0.1, "need_trend"),
    ]


def _screen_from_results(issue_type: IssueType, results: list[ToolResult], roas_min: float) -> list[CauseInvestigation]:
    families = SCREEN_FAMILIES.get(issue_type, ())
    by_name = {r.tool_name: r for r in results}
    if issue_type == IssueType.PROFIT_EROSION:
        dec = by_name.get("decompose_profit")
        if dec is None or not dec.success or not isinstance(dec.payload, ProfitDecomposePayload):
            return _blocked(families, "decompose_profit_unavailable")
        return _profit_causes(dec.payload)
    if issue_type == IssueType.AD_INEFFICIENCY:
        br = by_name.get("get_campaign_breakdown")
        if br is None or not br.success or not isinstance(br.payload, CampaignBreakdownPayload):
            return _blocked(families, "campaign_breakdown_unavailable")
        return _ad_causes(br.payload, roas_min)
    proj = by_name.get("get_inventory_projection")
    if proj is None or not proj.success or not isinstance(proj.payload, InventoryProjectionPayload):
        return _blocked(families, "inventory_projection_unavailable")
    return _inventory_causes(proj.payload, issue_type)


def run_preflight(state: DiagnosisState, ctx: ToolContext) -> tuple[DiagnosisState, list[ToolResult]]:
    issue = state.issue
    names = PREFLIGHT_TOOLS.get(issue.issue_type, ("get_issue_context",))
    a0, a1, b0, b1 = project_horizon_dates(ctx.as_of)
    args_map = {
        "get_issue_context": {"issue_id": issue.issue_id},
        "decompose_profit": {
            "sku_id": issue.entity_id,
            "period_a_start": a0,
            "period_a_end": a1,
            "period_b_start": b0,
            "period_b_end": b1,
        },
        "get_campaign_breakdown": {"sku_id": issue.entity_id},
        "get_inventory_projection": {"sku_id": issue.entity_id},
    }
    results: list[ToolResult] = []
    evidence_ids = list(state.evidence_ids)
    history = list(state.tool_history)
    for name in names:
        result = invoke(ctx, name, **args_map[name])
        results.append(result)
        history.append(result.call)
        for ev in result.evidence:
            if ev.evidence_id not in evidence_ids:
                evidence_ids.append(ev.evidence_id)
    causes = _screen_from_results(issue.issue_type, results, ctx.policy.roas_min)
    state = state.model_copy(update={"tool_history": history, "evidence_ids": evidence_ids, "causes": causes})
    return state, results
