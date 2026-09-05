from datetime import UTC, datetime

from agents.decision.agent import attach_simulations, plan
from agents.llm.scripts import scripted_strategy_llm
from app.config.settings import Settings
from domain.diagnosis.hypothesis import RootCause
from domain.diagnosis.report import DiagnosisReport
from domain.enums import IssueType
from evals.simulation.runner import run_simulation_benchmark
from services.daily_run import run_daily
from tests.fixtures.make_olist import AS_OF, write_mini_olist
from tools.diagnosis.investigate import context_from_run


def _ctx(tmp_path):
    data_dir = write_mini_olist(tmp_path / "olist")
    settings = Settings(as_of_date=AS_OF, store_seller_id="seller_demo", timezone="UTC")
    daily = run_daily(data_dir, settings=settings, now=datetime(2018, 3, 16, tzinfo=UTC))
    return daily, context_from_run(daily), data_dir, settings


def _report(issue, causes):
    return DiagnosisReport(
        diagnosis_id="DX",
        issue_id=issue.issue_id,
        status="confirmed",
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


def test_attach_keeps_selected(tmp_path):
    daily, ctx, _, _ = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.issue_type == IssueType.AD_INEFFICIENCY and i.entity_id == "sku_ad_inefficiency")
    planned = plan(issue, _report(issue, ("ad_efficiency",)), ctx, scripted_strategy_llm(IssueType.AD_INEFFICIENCY))
    selected = planned.state.initial_preferred_strategy_id
    simmed = attach_simulations(planned, ctx, n=4, seed=1)
    assert simmed.state.initial_preferred_strategy_id == selected
    assert 1 <= len(simmed.state.final_recommendations) <= 3
    assert len(simmed.state.simulation_reports) >= 2


def test_simulation_benchmark(tmp_path):
    _, _, data_dir, settings = _ctx(tmp_path)
    now = datetime(2018, 3, 16, tzinfo=UTC)
    rows = run_simulation_benchmark(data_dir, now, settings, n=6, seed=42)
    again = run_simulation_benchmark(data_dir, now, settings, n=6, seed=42)
    assert len(rows) == 4
    for a, b in zip(rows, again):
        assert a["selected_unchanged"]
        assert a["n_reports"] >= 2
        assert a["ordered"]
        assert a["has_do_nothing"]
        assert a["adaptive"]
        assert a["open_loop_static"]
        assert 1 <= a["n_recs"] <= 3
        assert [r.expected_profit for r in a["reports"]] == [r.expected_profit for r in b["reports"]]
    stock = next(r for r in rows if r["scenario_id"] == "sku_stockout_risk")
    noop = next(x for x in stock["reports"] if x.strategy_id == "ST_do_nothing")
    replenished = [x for x in stock["reports"] if x.cash_required > 0]
    assert replenished
    assert noop.stockout_probability >= min(x.stockout_probability for x in replenished)
