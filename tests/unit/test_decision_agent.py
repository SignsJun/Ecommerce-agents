from datetime import UTC, datetime

from agents.decision.agent import plan, plan_from_rules
from agents.diagnosis.schema import DiagnosisStep
from agents.llm.client import LLMUnavailable
from agents.llm.fake import FakeLLM
from agents.llm.scripts import scripted_strategy_llm, unknown_target_strategy_llm
from app.config.settings import Settings
from domain.diagnosis.hypothesis import RootCause
from domain.diagnosis.report import DiagnosisReport
from domain.enums import IssueType
from evals.strategy.metrics import unknown_target_rejected
from services.daily_run import run_daily
from tests.fixtures.make_olist import AS_OF, write_mini_olist
from tools.diagnosis.investigate import context_from_run


def _ctx(tmp_path):
    data_dir = write_mini_olist(tmp_path / "olist")
    settings = Settings(as_of_date=AS_OF, store_seller_id="seller_demo", timezone="UTC")
    daily = run_daily(data_dir, settings=settings, now=datetime(2018, 3, 16, tzinfo=UTC))
    return daily, context_from_run(daily)


def _report(issue, status="confirmed", causes=("ad_efficiency",)):
    return DiagnosisReport(
        diagnosis_id="DX",
        issue_id=issue.issue_id,
        status=status,
        root_causes=[
            RootCause(
                cause_type=c,
                description=c,
                confidence=0.9,
                estimated_contribution=0.5,
                supporting_evidence_ids=["E1"],
            )
            for c in causes
        ],
        overall_confidence=0.86,
        key_evidence_ids=["E1"],
        uncertainties=[],
        generated_at=datetime(2018, 3, 16, tzinfo=UTC),
        agent_version="diagnosis-v2",
        model_version="fake",
    )


def test_plan_does_not_call_diagnose(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.issue_type == IssueType.AD_INEFFICIENCY and i.entity_id == "sku_ad_inefficiency")

    def boom(system, user, schema):
        if schema is DiagnosisStep:
            raise LLMUnavailable("diagnose should not run")
        from agents.decision.schema import StrategyPlanDraft

        if schema is StrategyPlanDraft:
            return scripted_strategy_llm(IssueType.AD_INEFFICIENCY)._responder(system, user, schema)
        raise LLMUnavailable("unexpected")

    planned = plan(issue, _report(issue), ctx, FakeLLM(boom))
    assert planned.generation_source == "llm"
    assert planned.state.selected_strategy_id
    assert planned.state.candidate_strategies


def test_unknown_target_rejected(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.issue_type == IssueType.AD_INEFFICIENCY)
    planned = plan(issue, _report(issue), ctx, unknown_target_strategy_llm())
    assert unknown_target_rejected(planned.validations)
    assert "ST_do_nothing" in {s.strategy_id for s in planned.state.candidate_strategies}
    invented = [v for v in planned.validations if any(e.code == "UNKNOWN_TARGET_ID" for e in v.errors)]
    assert invented
    assert all(v.strategy_id in planned.state.rejected_strategy_ids for v in invented)
    assert planned.state.selected_strategy_id == "ST_do_nothing"


def test_insufficient_only_do_nothing(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.issue_type == IssueType.PROFIT_EROSION)

    def boom(system, user, schema):
        raise LLMUnavailable("should skip llm")

    report = _report(issue, status="insufficient_evidence", causes=())
    planned = plan(issue, report, ctx, FakeLLM(boom))
    assert planned.state.selected_strategy_id == "ST_do_nothing"
    assert planned.generation_source == "llm"


def test_partial_needs_simulation_not_approval(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.issue_type == IssueType.AD_INEFFICIENCY and i.entity_id == "sku_ad_inefficiency")
    planned = plan(issue, _report(issue, status="partial"), ctx, scripted_strategy_llm(IssueType.AD_INEFFICIENCY))
    assert planned.needs_simulation is True
    assert planned.approval_required is False


def test_replenish_requires_approval(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.issue_type == IssueType.STOCKOUT_RISK)
    planned = plan(
        issue,
        _report(issue, causes=("inventory",)),
        ctx,
        scripted_strategy_llm(IssueType.STOCKOUT_RISK),
    )
    assert planned.approval_required is True


def test_four_types_llm_and_rule(tmp_path):
    daily, ctx = _ctx(tmp_path)
    mapping = {
        IssueType.PROFIT_EROSION: ("sku_profit_erosion", ("ad_efficiency", "refunds")),
        IssueType.AD_INEFFICIENCY: ("sku_ad_inefficiency", ("ad_efficiency",)),
        IssueType.STOCKOUT_RISK: ("sku_stockout_risk", ("inventory",)),
        IssueType.EXCESS_INVENTORY: ("sku_excess_inventory", ("excess_inventory",)),
    }
    for itype, (entity, causes) in mapping.items():
        issue = next(i for i in daily.issues if i.entity_id == entity and i.issue_type == itype)
        report = _report(issue, causes=causes)
        llm_out = plan(issue, report, ctx, scripted_strategy_llm(itype))
        rule_out = plan_from_rules(issue, report, ctx)
        assert llm_out.generation_source == "llm"
        assert rule_out.generation_source == "rule"
        assert llm_out.state.selected_strategy_id
        assert rule_out.state.selected_strategy_id
        assert any(v.feasible for v in llm_out.validations)
        assert any(v.feasible for v in rule_out.validations)


def test_llm_fallback_source(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.issue_type == IssueType.AD_INEFFICIENCY and i.entity_id == "sku_ad_inefficiency")

    def boom(system, user, schema):
        raise LLMUnavailable("down")

    planned = plan(issue, _report(issue), ctx, FakeLLM(boom))
    assert planned.generation_source == "llm_fallback"
    assert planned.state.selected_strategy_id
