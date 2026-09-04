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

_DEEP = {
    "refunds": "get_refund_breakdown",
    "ad_efficiency": "get_campaign_breakdown",
    "campaign_mix": "get_campaign_trend",
    "inventory": "get_metric_trend",
    "excess_inventory": "get_metric_trend",
    "demand_decline": "get_metric_trend",
    "revenue": "get_metric_trend",
    "cogs": "get_metric_trend",
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


def _active(payload: dict) -> list[str]:
    return list(payload.get("active_causes") or [])


def _stop_step(issue_type: IssueType, payload: dict) -> DiagnosisStep:
    eids = [e["evidence_id"] for e in payload.get("evidence") or []]
    return DiagnosisStep(
        action="request_stop",
        stop_reason="active resolved",
        hypotheses=[
            LLMHypothesis(
                hypothesis_id=f"H{n}",
                cause_type=c[0],
                description=c[1],
                confidence=0.88,
                supporting_evidence_ids=eids,
                status="supported",
            )
            for n, c in enumerate(_CAUSES[issue_type])
        ],
    )


def scripted_llm(issue_type: IssueType, *, extra_first: str | None = None) -> FakeLLM:
    extra = {"used": False}

    def complete(system: str, user: str, schema: type) -> object:
        payload = _load(user)
        if schema is DiagnosisReportDraft:
            blocked = any(c.get("status") == "blocked_by_data" for c in payload.get("causes") or [])
            eids = list(payload.get("evidence_ids") or [])
            if blocked and not any(c.get("status") == "investigated_supported" for c in payload.get("causes") or []):
                return DiagnosisReportDraft(status="insufficient_evidence", overall_confidence=0.2)
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
            return DiagnosisReportDraft(
                status="confirmed" if eids else "insufficient_evidence",
                root_causes=causes,
                uncertainties=[],
                overall_confidence=0.86 if eids else 0.2,
            )
        if extra_first and not extra["used"]:
            extra["used"] = True
            active = _active(payload)
            return DiagnosisStep(
                action="call_tool",
                tool_name=extra_first,
                target_cause=active[0] if active else "refunds",
                tool_args=_args(extra_first, payload),
            )
        active = _active(payload)
        for name in active:
            tool = _DEEP.get(name)
            if not tool:
                continue
            row = next((c for c in payload.get("causes") or [] if c.get("cause_type") == name), {})
            if int(row.get("investigation_tool_calls") or 0) < 1:
                return DiagnosisStep(
                    action="call_tool",
                    tool_name=tool,
                    target_cause=name,
                    tool_args=_args(tool, payload),
                    hypotheses=[
                        LLMHypothesis(
                            hypothesis_id="H0",
                            cause_type=name,
                            description="investigating",
                            confidence=0.4,
                            status="open",
                        )
                    ],
                )
        if active:
            return _stop_step(issue_type, payload)
        return _stop_step(issue_type, payload)

    return FakeLLM(complete)


def confirming_without_evidence_llm() -> FakeLLM:
    def complete(system: str, user: str, schema: type) -> object:
        if schema is DiagnosisStep:
            return DiagnosisStep(action="request_stop", stop_reason="guess")
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


def activating_llm(cause_type: str) -> FakeLLM:
    done = {"n": 0}

    def complete(system: str, user: str, schema: type) -> object:
        payload = _load(user) if user.startswith("{") else {}
        if schema is DiagnosisReportDraft:
            eids = list(payload.get("evidence_ids") or [])
            return DiagnosisReportDraft(
                status="partial",
                root_causes=[
                    LLMRootCause(
                        cause_type=cause_type,
                        description="reactivated",
                        confidence=0.8,
                        supporting_evidence_ids=eids[:1],
                    )
                ],
                overall_confidence=0.8,
            )
        if done["n"] == 0:
            done["n"] = 1
            eids = [e["evidence_id"] for e in payload.get("evidence") or []]
            return DiagnosisStep(
                action="activate_cause",
                target_cause=cause_type,
                reason="new evidence links paid traffic",
                evidence_ids=eids[:2],
            )
        return DiagnosisStep(
            action="request_stop",
            stop_reason="activated",
            hypotheses=[
                LLMHypothesis(
                    hypothesis_id="H1",
                    cause_type=cause_type,
                    description="reactivated",
                    confidence=0.8,
                    supporting_evidence_ids=[e["evidence_id"] for e in payload.get("evidence") or []][:2],
                    status="supported",
                )
            ],
        )

    return FakeLLM(complete)
