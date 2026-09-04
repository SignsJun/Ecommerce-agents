import json
from pathlib import Path

from agents.diagnosis.causal_graph import CAUSE_TYPES, allowed_tools
from domain.diagnosis.state import DiagnosisState
from tools.diagnosis.base import ToolContext, ToolResult
from tools.diagnosis.handlers import project_baseline_30d, project_horizon_dates

PROMPT_VERSION = "diagnosis/system_v2"
_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "diagnosis" / "system_v2.md"
_MAX_CHARS = 6000


def load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _clip(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    return text[: n - 1] + "…"


def _payload_brief(payload: dict) -> dict:
    kind = payload.get("kind")
    if kind == "issue_context":
        issue = payload.get("issue") or {}
        return {
            "kind": kind,
            "issue_id": issue.get("issue_id"),
            "issue_type": issue.get("issue_type"),
            "entity_id": issue.get("entity_id"),
        }
    if kind == "sku_summary":
        sku = payload.get("sku") or {}
        return {
            "kind": kind,
            "sku_id": sku.get("sku_id"),
            "profit_margin_7d": sku.get("profit_margin_7d"),
            "inventory_available": sku.get("inventory_available"),
            "units_sold_7d": sku.get("units_sold_7d"),
            "refund_rate_7d": sku.get("refund_rate_7d"),
            "roas_7d": sku.get("roas_7d"),
            "roas_prev_7d": sku.get("roas_prev_7d"),
            "ad_spend_7d": sku.get("ad_spend_7d"),
        }
    if kind == "metric_trend":
        series = payload.get("series") or []
        metric = payload.get("metric") or {}
        return {"kind": kind, "metric": metric.get("metric_name"), "n": len(series), "tail": series[-3:]}
    if kind == "profit_decompose":
        return {
            "kind": kind,
            "sku_id": payload.get("sku_id"),
            "delta_profit": payload.get("delta_profit"),
            "delta_ad_spend": payload.get("delta_ad_spend"),
            "delta_refund_loss": payload.get("delta_refund_loss"),
            "delta_revenue": payload.get("delta_revenue"),
            "delta_cogs": payload.get("delta_cogs"),
        }
    if kind == "campaign_breakdown":
        camps = payload.get("campaigns") or []
        return {"kind": kind, "n": len(camps), "campaigns": camps[:4]}
    if kind == "campaign_trend":
        pts = payload.get("points") or []
        return {
            "kind": kind,
            "campaign_id": payload.get("campaign_id"),
            "n": len(pts),
            "tail": pts[-3:],
        }
    if kind == "inventory_projection":
        return {
            "kind": kind,
            "sku_id": payload.get("sku_id"),
            "first_stockout_day": payload.get("first_stockout_day"),
            "daily_demand": payload.get("daily_demand"),
            "horizon_days": payload.get("horizon_days"),
        }
    if kind == "refund_breakdown":
        return {
            "kind": kind,
            "sku_id": payload.get("sku_id"),
            "refund_rate": payload.get("refund_rate"),
            "refund_loss": payload.get("refund_loss"),
            "refund_units": payload.get("refund_units"),
        }
    if kind == "review_analysis":
        return {
            "kind": kind,
            "sku_id": payload.get("sku_id"),
            "n": payload.get("n"),
            "avg_score": payload.get("avg_score"),
            "low_score_share": payload.get("low_score_share"),
            "score_counts": payload.get("score_counts"),
        }
    if kind == "peer_compare":
        peers = payload.get("peers") or []
        return {"kind": kind, "n": len(peers), "peers": peers[:3]}
    small: dict = {}
    for key, value in payload.items():
        if isinstance(value, list):
            small[key] = value[:3]
            small[f"{key}_n"] = len(value)
        elif isinstance(value, dict) and len(json.dumps(value, default=str)) > 400:
            small[key] = {"omitted": True}
        else:
            small[key] = value
    return small


def _tool_brief(result: ToolResult) -> dict:
    payload = None
    if result.payload is not None:
        payload = _payload_brief(result.payload.model_dump(mode="json"))
    return {
        "tool": result.tool_name,
        "success": result.success,
        "error": result.error.message if result.error else None,
        "evidence_ids": [e.evidence_id for e in result.evidence],
        "payload": payload,
    }


def _dumps(body: dict) -> str:
    text = json.dumps(body, ensure_ascii=False)
    if len(text) <= _MAX_CHARS:
        return text
    slim = dict(body)
    slim["recent_tool_results"] = [
        {
            "tool": row.get("tool"),
            "success": row.get("success"),
            "error": row.get("error"),
            "evidence_ids": row.get("evidence_ids"),
        }
        for row in (body.get("recent_tool_results") or [])
    ]
    slim["evidence"] = (body.get("evidence") or [])[:4]
    text = json.dumps(slim, ensure_ascii=False)
    if len(text) <= _MAX_CHARS:
        return text
    slim["recent_tool_results"] = []
    slim["evidence"] = slim["evidence"][:2]
    slim["hypotheses"] = []
    return json.dumps(slim, ensure_ascii=False)


def build_user_context(
    state: DiagnosisState,
    ctx: ToolContext,
    recent_results: list[ToolResult],
) -> str:
    issue = state.issue
    snap = ctx.snapshot()
    sku = None
    if snap is not None and issue.entity_id in snap.skus:
        s = snap.skus[issue.entity_id]
        sku = {
            "sku_id": s.sku_id,
            "category": s.category,
            "price": str(s.price),
            "inventory_available": s.inventory_available,
            "lead_time_days": s.lead_time_days,
            "units_sold_7d": s.units_sold_7d,
            "profit_margin_7d": s.profit_margin_7d,
            "refund_rate_7d": s.refund_rate_7d,
            "revenue_7d": str(s.revenue_7d),
            "profit_7d": str(s.profit_7d),
            "ad_spend_7d": str(s.ad_spend_7d),
            "roas_7d": s.roas_7d,
            "roas_prev_7d": s.roas_prev_7d,
            "roas_30d": s.roas_30d,
            "paid_traffic_7d": s.paid_traffic_7d,
            "ad_conversions_7d": s.ad_conversions_7d,
        }
    a0, a1, b0, b1 = project_horizon_dates(ctx.as_of)
    c0, c1 = project_baseline_30d(ctx.as_of)
    campaigns = ctx.business_repo.list_campaigns_for_sku(issue.entity_id)
    evidence = ctx.issue_repo.list_evidence(state.evidence_ids)
    active = [c.cause_type for c in state.causes if c.status.value == "active"]
    body = {
        "issue": {
            "issue_id": issue.issue_id,
            "issue_type": issue.issue_type.value,
            "entity_id": issue.entity_id,
            "severity": issue.severity,
            "confidence": issue.confidence,
            "estimated_impact": str(issue.estimated_impact) if issue.estimated_impact is not None else None,
        },
        "sku": sku,
        "as_of": ctx.as_of.isoformat(),
        "windows": {
            "period_a_start": a0.isoformat(),
            "period_a_end": a1.isoformat(),
            "period_b_start": b0.isoformat(),
            "period_b_end": b1.isoformat(),
            "baseline_30d_start": c0.isoformat(),
            "baseline_30d_end": c1.isoformat(),
            "metric_window": "7d",
        },
        "campaign_ids": campaigns[:8],
        "allowed_tools": list(allowed_tools(issue.issue_type)),
        "allowed_cause_types": list(CAUSE_TYPES.get(issue.issue_type, ())),
        "causes": [c.model_dump(mode="json") for c in state.causes],
        "active_causes": active,
        "gate_feedback": state.gate_feedback,
        "hypotheses": [h.model_dump(mode="json") for h in state.hypotheses],
        "unresolved_questions": state.unresolved_questions,
        "evidence": [
            {
                "evidence_id": e.evidence_id,
                "metric": e.metric,
                "value": e.value,
                "description": _clip(e.description, 160),
                "comparison": _clip(e.comparison, 120) if e.comparison else None,
            }
            for e in evidence[:8]
        ],
        "recent_tool_results": [_tool_brief(r) for r in recent_results[-3:]],
        "step_count": state.step_count,
        "tool_calls": len(state.tool_history),
    }
    return _dumps(body)


def build_report_context(state: DiagnosisState, ctx: ToolContext) -> str:
    evidence = ctx.issue_repo.list_evidence(state.evidence_ids)
    body = {
        "task": "Write DiagnosisReport JSON only. supporting_evidence_ids must be copied from evidence_ids below. Do not invent ids.",
        "issue_id": state.issue.issue_id,
        "issue_type": state.issue.issue_type.value,
        "allowed_cause_types": list(CAUSE_TYPES.get(state.issue.issue_type, ())),
        "hypotheses": [h.model_dump(mode="json") for h in state.hypotheses],
        "unresolved_questions": state.unresolved_questions,
        "evidence_ids": state.evidence_ids,
        "evidence": [
            {
                "evidence_id": e.evidence_id,
                "metric": e.metric,
                "value": e.value,
                "description": _clip(e.description, 160),
            }
            for e in evidence[:12]
        ],
        "causes": [c.model_dump(mode="json") for c in state.causes],
        "unresolved_active": [c.cause_type for c in state.causes if c.status.value == "active"],
    }
    return _dumps(body)
