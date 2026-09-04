from datetime import UTC, datetime

from agents.diagnosis.agent import MAX_ROUNDS, MAX_TOOL_CALLS, diagnose
from agents.diagnosis.causal_graph import is_allowed_tool
from agents.diagnosis.schema import DiagnosisReportDraft, DiagnosisStep
from agents.llm.fake import FakeLLM
from agents.llm.scripts import confirming_without_evidence_llm, scripted_llm
from app.config.settings import Settings
from domain.enums import IssueType
from evals.diagnosis.metrics import correct_escalation, evidence_grounding, hallucination_rate
from services.daily_run import run_daily
from tests.fixtures.make_olist import AS_OF, write_mini_olist
from tools.diagnosis.investigate import context_from_run


def _ctx(tmp_path):
    data_dir = write_mini_olist(tmp_path / "olist")
    settings = Settings(as_of_date=AS_OF, store_seller_id="seller_demo", timezone="UTC")
    daily = run_daily(data_dir, settings=settings, now=datetime(2018, 3, 16, tzinfo=UTC))
    return daily, context_from_run(daily)


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
        assert outcome.report.agent_version == "diagnosis-v1"
        assert outcome.prompt_version == "diagnosis/system_v1"
        assert outcome.report.root_causes
        assert outcome.report.status in {"confirmed", "partial"}
        assert evidence_grounding(outcome.report, outcome.state) == 1.0
        assert all(t.success for t in outcome.state.tool_history)


def test_neighborhood_rejects_tool(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.entity_id == "sku_profit_erosion")
    assert not is_allowed_tool(issue.issue_type, "get_promotion_history")
    outcome = diagnose(issue, ctx, scripted_llm(issue.issue_type, extra_first="get_promotion_history"))
    assert outcome.irrelevant_tool_requests >= 1
    assert any(t.tool_name == "get_promotion_history" and t.error_code == "unavailable" for t in outcome.state.tool_history)
    assert not any(t.tool_name == "get_promotion_history" and t.success for t in outcome.state.tool_history)


def test_stagnant_rounds_stop(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.entity_id == "sku_profit_erosion")

    def always_promo(system, user, schema):
        if schema is DiagnosisReportDraft:
            return DiagnosisReportDraft(status="insufficient_evidence", overall_confidence=0.1)
        return DiagnosisStep(
            action="call_tool",
            tool_name="get_promotion_history",
            tool_args={"sku_id": issue.entity_id},
        )

    outcome = diagnose(issue, ctx, FakeLLM(always_promo))
    assert len(outcome.state.tool_history) <= MAX_TOOL_CALLS
    assert outcome.irrelevant_tool_requests >= 2


def test_max_rounds_stop(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.entity_id == "sku_profit_erosion")

    def always_context(system, user, schema):
        if schema is DiagnosisReportDraft:
            return DiagnosisReportDraft(status="insufficient_evidence", overall_confidence=0.1)
        return DiagnosisStep(
            action="call_tool",
            tool_name="get_issue_context",
            tool_args={"issue_id": issue.issue_id},
        )

    outcome = diagnose(issue, ctx, FakeLLM(always_context))
    assert len(outcome.state.tool_history) <= MAX_TOOL_CALLS
    assert outcome.state.step_count <= MAX_ROUNDS
    assert len(outcome.state.tool_history) == MAX_ROUNDS


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
