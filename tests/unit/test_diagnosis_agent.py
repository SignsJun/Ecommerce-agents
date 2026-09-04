from datetime import UTC, datetime

from agents.diagnosis.agent import MAX_TOOL_CALLS, diagnose
from agents.diagnosis.causal_graph import is_allowed_tool
from agents.diagnosis.preflight import run_preflight
from agents.diagnosis.schema import DiagnosisReportDraft, DiagnosisStep, LLMHypothesis
from agents.llm.fake import FakeLLM
from agents.llm.scripts import activating_llm, confirming_without_evidence_llm, scripted_llm
from app.config.settings import Settings
from domain.diagnosis.cause import CauseStatus
from domain.diagnosis.state import DiagnosisState
from domain.enums import IssueType
from evals.diagnosis.metrics import correct_escalation, evidence_grounding, hallucination_rate
from services.daily_run import run_daily
from tests.fixtures.make_olist import AS_OF, write_mini_olist
from tools.diagnosis.handlers import project_horizon_dates
from tools.diagnosis.investigate import context_from_run


def _ctx(tmp_path):
    data_dir = write_mini_olist(tmp_path / "olist")
    settings = Settings(as_of_date=AS_OF, store_seller_id="seller_demo", timezone="UTC")
    daily = run_daily(data_dir, settings=settings, now=datetime(2018, 3, 16, tzinfo=UTC))
    return daily, context_from_run(daily)


def test_horizon_equal_length():
    a0, a1, b0, b1 = project_horizon_dates(AS_OF)
    assert (a1 - a0).days == 6
    assert (b1 - b0).days == 6
    assert (a0 - b0).days == 7


def test_sku_roas_context(tmp_path):
    daily, _ = _ctx(tmp_path)
    sku = daily.snapshot.skus["sku_profit_erosion"]
    assert sku.roas_7d is not None
    assert sku.ad_spend_7d > 0


def test_preflight_activates_material(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.entity_id == "sku_profit_erosion")
    state = DiagnosisState(diagnosis_id="DX", issue=issue, evidence_ids=list(issue.evidence_ids))
    state, _ = run_preflight(state, ctx)
    by = {c.cause_type: c for c in state.causes}
    assert "decompose_profit" in {t.tool_name for t in state.tool_history}
    assert by["refunds"].status == CauseStatus.ACTIVE
    assert CauseStatus.SCREENED_NON_MATERIAL in {c.status for c in state.causes}


def test_fake_llm_four_issue_types(tmp_path):
    daily, ctx = _ctx(tmp_path)
    mapping = {
        "sku_profit_erosion": IssueType.PROFIT_EROSION,
        "sku_ad_inefficiency": IssueType.AD_INEFFICIENCY,
        "sku_stockout_risk": IssueType.STOCKOUT_RISK,
        "sku_excess_inventory": IssueType.EXCESS_INVENTORY,
    }
    for entity_id, itype in mapping.items():
        issue = next(i for i in daily.issues if i.entity_id == entity_id)
        outcome = diagnose(issue, ctx, scripted_llm(itype))
        assert outcome.report.issue_id == issue.issue_id
        assert outcome.report.agent_version == "diagnosis-v2"
        assert outcome.prompt_version == "diagnosis/system_v2"
        assert outcome.report.root_causes
        assert outcome.report.status == "confirmed"
        assert evidence_grounding(outcome.report, outcome.state) == 1.0
        assert outcome.report.overall_confidence > 0.4


def test_neighborhood_rejects_tool(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.entity_id == "sku_profit_erosion")
    assert not is_allowed_tool(issue.issue_type, "get_promotion_history")
    outcome = diagnose(issue, ctx, scripted_llm(issue.issue_type, extra_first="get_promotion_history"))
    assert outcome.irrelevant_tool_requests >= 1
    assert any(t.tool_name == "get_promotion_history" and t.error_code == "unavailable" for t in outcome.state.tool_history)
    assert not any(t.tool_name == "get_promotion_history" and t.success for t in outcome.state.tool_history)


def test_gate_rejects_early_stop(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.entity_id == "sku_profit_erosion")
    seen = {"gate": False}

    def early_stop(system, user, schema):
        import json

        if schema is DiagnosisReportDraft:
            return DiagnosisReportDraft(status="insufficient_evidence", overall_confidence=0.1)
        if "STOP_REJECTED" in user:
            seen["gate"] = True
            payload = json.loads(user)
            target = (payload.get("active_causes") or ["refunds"])[0]
            return DiagnosisStep(
                action="reject_cause",
                target_cause=target,
                reason="force resolve",
            )
        return DiagnosisStep(action="request_stop", stop_reason="too soon")

    outcome = diagnose(issue, ctx, FakeLLM(early_stop))
    assert seen["gate"]
    assert any(c.status == CauseStatus.ACTIVE or c.status == CauseStatus.INVESTIGATED_REJECTED for c in outcome.state.causes)


def test_stagnant_rounds_stop(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.entity_id == "sku_profit_erosion")

    def always_promo(system, user, schema):
        import json

        if schema is DiagnosisReportDraft:
            return DiagnosisReportDraft(status="insufficient_evidence", overall_confidence=0.1)
        payload = json.loads(user)
        target = (payload.get("active_causes") or ["refunds"])[0]
        return DiagnosisStep(
            action="call_tool",
            tool_name="get_promotion_history",
            target_cause=target,
            tool_args={"sku_id": issue.entity_id},
        )

    outcome = diagnose(issue, ctx, FakeLLM(always_promo))
    assert len(outcome.state.tool_history) <= MAX_TOOL_CALLS
    assert outcome.irrelevant_tool_requests >= 2


def test_max_tool_budget(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.entity_id == "sku_profit_erosion")

    def always_context(system, user, schema):
        import json

        if schema is DiagnosisReportDraft:
            return DiagnosisReportDraft(status="insufficient_evidence", overall_confidence=0.1)
        payload = json.loads(user)
        target = (payload.get("active_causes") or ["refunds"])[0]
        return DiagnosisStep(
            action="call_tool",
            tool_name="get_issue_context",
            target_cause=target,
            tool_args={"issue_id": issue.issue_id},
        )

    outcome = diagnose(issue, ctx, FakeLLM(always_context))
    assert len(outcome.state.tool_history) <= MAX_TOOL_CALLS


def test_hallucinated_evidence_not_confirmed(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.entity_id == "sku_profit_erosion")
    outcome = diagnose(issue, ctx, confirming_without_evidence_llm())
    assert outcome.report.status == "insufficient_evidence"
    assert outcome.report.root_causes == []
    assert hallucination_rate(outcome.report, outcome.state) == 0.0
    assert correct_escalation(outcome.report, True) == 1.0


def test_missing_daily_metrics_escalates(tmp_path):
    daily, ctx = _ctx(tmp_path)
    ctx.business_repo._sku_daily.clear()
    ctx.business_repo._campaign_daily.clear()
    issue = next(i for i in daily.issues if i.entity_id == "sku_profit_erosion")
    outcome = diagnose(issue, ctx, scripted_llm(IssueType.PROFIT_EROSION))
    assert outcome.report.status == "insufficient_evidence"
    assert correct_escalation(outcome.report, True) == 1.0


def test_partial_blocked_keeps_confidence(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.entity_id == "sku_profit_erosion")

    def refund_then_block(system, user, schema):
        import json

        payload = json.loads(user)
        if schema is DiagnosisReportDraft:
            eids = list(payload.get("evidence_ids") or [])
            from agents.diagnosis.schema import LLMRootCause

            return DiagnosisReportDraft(
                status="confirmed",
                root_causes=[
                    LLMRootCause(
                        cause_type="refunds",
                        description="refunds",
                        confidence=0.93,
                        supporting_evidence_ids=eids[:1],
                    )
                ],
                overall_confidence=0.93,
            )
        active = payload.get("active_causes") or []
        if "refunds" in active:
            row = next((c for c in payload.get("causes") or [] if c.get("cause_type") == "refunds"), {})
            if int(row.get("investigation_tool_calls") or 0) < 1:
                return DiagnosisStep(
                    action="call_tool",
                    target_cause="refunds",
                    tool_name="get_refund_breakdown",
                    tool_args={"sku_id": issue.entity_id},
                )
            return DiagnosisStep(
                action="request_stop",
                hypotheses=[
                    LLMHypothesis(
                        hypothesis_id="H1",
                        cause_type="refunds",
                        description="refunds",
                        confidence=0.93,
                        supporting_evidence_ids=[e["evidence_id"] for e in payload.get("evidence") or []][:1],
                        status="supported",
                    )
                ],
            )
        return DiagnosisStep(action="request_stop", stop_reason="done")

    outcome = diagnose(issue, ctx, FakeLLM(refund_then_block))
    assert outcome.report.root_causes
    refund = next(c for c in outcome.report.root_causes if c.cause_type == "refunds")
    assert refund.confidence >= 0.9
    assert outcome.report.status == "partial"
    assert outcome.report.overall_confidence >= 0.9


def test_activate_cause_reopens(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.entity_id == "sku_profit_erosion")
    state = DiagnosisState(diagnosis_id="DX", issue=issue, evidence_ids=list(issue.evidence_ids))
    state, _ = run_preflight(state, ctx)
    non = next((c.cause_type for c in state.causes if c.status == CauseStatus.SCREENED_NON_MATERIAL), "cogs")
    outcome = diagnose(issue, ctx, activating_llm(non))
    assert any(c.cause_type == non and c.status != CauseStatus.SCREENED_NON_MATERIAL for c in outcome.state.causes)
