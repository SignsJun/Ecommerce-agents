from decimal import Decimal

from domain.decision.case import DecisionCase
from domain.decision.recommendation import StrategyRecommendation
from domain.decision.record import DecisionRecord
from domain.simulation.models import ScenarioResult
from domain.strategy.validation import StrategyValidationResult
from services.artifact.provenance import build_graph
from services.artifact.render import render_documents
from tests.unit import factories as f


def _rec(**kwargs):
    base = dict(
        strategy_id="STRAT_B",
        rank=1,
        recommendation_type="balanced",
        confidence="medium",
        expected_profit=Decimal("1000.00"),
        profit_p10=Decimal("600.00"),
        vs_baseline=Decimal("200.00"),
        strengths=["vs_baseline_positive"],
        risks=["p10_negative"],
        suitable_when=["prefer_balance"],
        simulation_support=["base"],
    )
    base.update(kwargs)
    return StrategyRecommendation(**base)


def _val(sid: str, feasible: bool = True):
    return StrategyValidationResult(strategy_id=sid, feasible=feasible, errors=[], warnings=[], normalized_strategy=None)


def make_case(*, rejected_after_eval=None, extra_sim=None):
    issue = f.issue()
    evidence = f.evidence()
    diagnosis = f.diagnosis_report()
    strat = f.strategy()
    mid = strat.model_copy(update={"strategy_id": "ST_mid", "name": "Mid", "strategy_type": "growth"})
    noop = strat.model_copy(update={"strategy_id": "ST_do_nothing", "name": "Noop", "strategy_type": "custom", "actions": []})
    sims = [f.simulation_report()]
    if extra_sim:
        sims.append(extra_sim)
    recs = [_rec()]
    rejected = rejected_after_eval if rejected_after_eval is not None else ["ST_mid"]
    strategies = [strat, mid, noop]
    graph = build_graph(
        decision_id="DEC_018",
        snapshot_id="SNAP_184",
        issue=issue,
        evidence=[evidence],
        diagnosis=diagnosis,
        strategies=strategies,
        validations=[_val("STRAT_B"), _val("ST_mid"), _val("ST_do_nothing")],
        simulations=sims,
        recommendations=recs,
        rejected_after_eval=rejected,
        rejected_strategy_ids=[],
    )
    return DecisionCase(
        record=DecisionRecord(
            decision_id="DEC_018",
            issue_id=issue.issue_id,
            issue_type=issue.issue_type,
            snapshot_id="SNAP_184",
            diagnosis_id=diagnosis.diagnosis_id,
            experiment_status="sufficient",
            recommendations=recs,
            rejected_after_eval=rejected,
            rejected_strategy_ids=[],
            created_at=f.NOW,
        ),
        snapshot=f.snapshot(),
        issue=issue,
        evidence=[evidence],
        diagnosis=diagnosis,
        strategies=strategies,
        validations=[_val("STRAT_B"), _val("ST_mid"), _val("ST_do_nothing")],
        simulations=sims,
        recommendations=recs,
        provenance=graph,
    )


def test_render_front_matter_and_recommendation():
    docs = render_documents(make_case())
    record = docs["05_decision_record.md"]
    assert record.startswith("---")
    assert "document_type: decision_record" in record
    assert "decision_id: DEC_018" in record
    assert "1. balanced STRAT_B" in record
    assert "strengths=vs_baseline_positive" in record
    assert "- ST_mid 原因：rejected_after_eval" in record
    brief = docs["01_issue_brief.md"]
    assert "document_type: issue_brief" in brief
    assert "profit_erosion" in brief
    diag = docs["02_diagnosis_report.md"]
    assert "ad_efficiency" in diag
    assert "E101" in diag
    sim = docs["04_simulation_report.md"]
    assert "STRAT_B" in sim
    assert "base" in sim


def test_render_uses_structured_fields_only():
    docs = render_documents(make_case())
    body = docs["05_decision_record.md"]
    assert "support=base" in body
    extra = f.simulation_report().model_copy(
        update={
            "simulation_id": "SIM_stress",
            "strategy_id": "STRAT_B",
            "expected_profit": Decimal("800.00"),
            "scenario_results": [
                ScenarioResult(
                    scenario_id="roas_down",
                    expected_profit=Decimal("800.00"),
                    profit_p10=Decimal("500.00"),
                    profit_p50=Decimal("800.00"),
                    profit_p90=Decimal("900.00"),
                    stockout_probability=0.1,
                )
            ],
        }
    )
    case = make_case(extra_sim=extra)
    rec = case.recommendations[0].model_copy(update={"simulation_support": ["base", "roas_down"]})
    case = case.model_copy(update={"recommendations": [rec], "record": case.record.model_copy(update={"recommendations": [rec]})})
    text = render_documents(case)["05_decision_record.md"]
    assert "roas_down" in text
    assert "support=base,roas_down" in text
