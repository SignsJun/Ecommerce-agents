import json

from agents.diagnosis.schema import DiagnosisReportDraft, DiagnosisStep, LLMHypothesis, LLMRootCause
from agents.llm.fake import FakeLLM
from domain.enums import IssueType

_CAUSES = {
    IssueType.PROFIT_EROSION: (("ad_efficiency", "ads spend up"), ("refunds", "refunds up")),
    IssueType.AD_INEFFICIENCY: (("ad_efficiency", "roas down"),),
    IssueType.STOCKOUT_RISK: (("inventory", "cover below lead time"),),
    IssueType.EXCESS_INVENTORY: (("excess_inventory", "cover too high"),),
}

_TOOLS = {
    IssueType.PROFIT_EROSION: (
        "get_issue_context",
        "decompose_profit",
        "get_campaign_breakdown",
        "get_refund_breakdown",
    ),
    IssueType.AD_INEFFICIENCY: (
        "get_issue_context",
        "get_campaign_breakdown",
        "get_campaign_trend",
    ),
    IssueType.STOCKOUT_RISK: ("get_issue_context", "get_inventory_projection"),
    IssueType.EXCESS_INVENTORY: ("get_issue_context", "get_inventory_projection"),
}


def _load(user: str) -> dict:
    return json.loads(user)


def _args(name: str, payload: dict) -> dict[str, str | int | float | bool | None]:
    issue_id = payload["issue"]["issue_id"]
    sku_id = payload["issue"]["entity_id"]
    windows = payload.get("windows") or {}
    campaigns = payload.get("campaign_ids") or []
    if name == "get_issue_context":
        return {"issue_id": issue_id}
    if name == "decompose_profit":
        return {
            "sku_id": sku_id,
            "period_a_start": windows["period_a_start"],
            "period_a_end": windows["period_a_end"],
            "period_b_start": windows["period_b_start"],
            "period_b_end": windows["period_b_end"],
        }
    if name == "get_campaign_trend":
        return {"campaign_id": campaigns[0] if campaigns else ""}
    if name == "get_metric_trend":
        return {
            "entity_type": "sku",
            "entity_id": sku_id,
            "metric": "profit_margin",
            "window_name": "7d",
        }
    if name == "analyze_reviews":
        return {"sku_id": sku_id, "window_name": "7d"}
    if name == "compare_peer_skus":
        return {"sku_id": sku_id, "metrics": "profit_margin,roas,days_of_cover"}
    return {"sku_id": sku_id}


def scripted_llm(issue_type: IssueType, *, extra_first: str | None = None) -> FakeLLM:
    names = list(_TOOLS[issue_type])
    if extra_first:
        names = [extra_first, *names]
    cursor = {"i": 0}

    def complete(system: str, user: str, schema: type) -> object:
        payload = _load(user)
        if schema is DiagnosisReportDraft:
            eids = list(payload.get("evidence_ids") or [])
            causes = []
            for idx, (ctype, desc) in enumerate(_CAUSES[issue_type]):
                eid = eids[idx] if idx < len(eids) else (eids[-1] if eids else "")
                ids = [eid] if eid else []
                causes.append(
                    LLMRootCause(
                        cause_type=ctype,
                        description=desc,
                        confidence=0.88,
                        estimated_contribution=0.5,
                        supporting_evidence_ids=ids,
                    )
                )
            status = "confirmed" if eids else "insufficient_evidence"
            return DiagnosisReportDraft(
                status=status,
                root_causes=causes,
                uncertainties=[],
                overall_confidence=0.86 if eids else 0.2,
            )
        i = cursor["i"]
        cursor["i"] += 1
        if i >= len(names):
            return DiagnosisStep(
                action="stop",
                stop_reason="enough evidence",
                hypotheses=[
                    LLMHypothesis(
                        hypothesis_id=f"H{n}",
                        cause_type=c[0],
                        description=c[1],
                        confidence=0.88,
                        supporting_evidence_ids=[e["evidence_id"] for e in payload.get("evidence") or []],
                        status="supported",
                    )
                    for n, c in enumerate(_CAUSES[issue_type])
                ],
            )
        name = names[i]
        return DiagnosisStep(
            action="call_tool",
            tool_name=name,
            tool_args=_args(name, payload),
            hypotheses=[
                LLMHypothesis(
                    hypothesis_id="H0",
                    cause_type=_CAUSES[issue_type][0][0],
                    description="investigating",
                    confidence=0.4,
                    status="open",
                )
            ],
        )

    return FakeLLM(complete)


def confirming_without_evidence_llm() -> FakeLLM:
    def complete(system: str, user: str, schema: type) -> object:
        if schema is DiagnosisStep:
            return DiagnosisStep(action="stop", stop_reason="guess")
        return DiagnosisReportDraft(
            status="confirmed",
            root_causes=[
                LLMRootCause(
                    cause_type="ad_efficiency",
                    description="invented",
                    confidence=0.99,
                    supporting_evidence_ids=["EV_does_not_exist"],
                )
            ],
            overall_confidence=0.99,
        )

    return FakeLLM(complete)
