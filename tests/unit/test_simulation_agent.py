from datetime import UTC, datetime
from decimal import Decimal

from agents.decision.agent import attach_simulations, plan
from agents.llm.scripts import scripted_strategy_llm
from agents.simulation.agent import run_experiments
from agents.simulation.catalog import scenario_jobs
from agents.simulation.compare import has_stress_for, ranking_flipped
from app.config.settings import Settings
from domain.diagnosis.hypothesis import RootCause
from domain.diagnosis.report import DiagnosisReport
from domain.enums import IssueType
from domain.simulation.models import ScenarioResult
from services.daily_run import run_daily
from tests.fixtures.make_olist import AS_OF, write_mini_olist
from tests.unit import factories as f
from tools.diagnosis.investigate import context_from_run


def _rep(sid: str, profit: str, scene: str = "base"):
    p = Decimal(profit)
    return f.simulation_report().model_copy(
        update={
            "strategy_id": sid,
            "expected_profit": p,
            "profit_p10": p,
            "scenario_results": [
                ScenarioResult(
                    scenario_id=scene,
                    expected_profit=p,
                    profit_p10=p,
                    profit_p50=p,
                    profit_p90=p,
                    stockout_probability=0.0,
                )
            ],
        }
    )


def _ctx(tmp_path):
    data_dir = write_mini_olist(tmp_path / "olist")
    settings = Settings(as_of_date=AS_OF, store_seller_id="seller_demo", timezone="UTC")
    daily = run_daily(data_dir, settings=settings, now=datetime(2018, 3, 16, tzinfo=UTC))
    return daily, context_from_run(daily)


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


def test_catalog_overrides():
    jobs = scenario_jobs("roas_down")
    assert jobs[0].scenario_type == "stress"
    assert abs(jobs[0].parameter_overrides["eta_ad"] - 0.48) < 1e-9
    delay = scenario_jobs("supplier_delay")
    assert delay[0].parameter_overrides["lead_time_extra"] == 7.0
    pm = scenario_jobs("eta_ad_pm20")
    assert len(pm) == 2


def test_ranking_flip_uncertain():
    base = [_rep("G", "28000"), _rep("B", "25000")]
    stress = [_rep("G", "13000", "roas_down"), _rep("B", "22000", "roas_down")]
    assert ranking_flipped(base, stress)
    assert not ranking_flipped(base, [_rep("G", "20000", "roas_down")])


def test_experiments_keep_selected_and_budget(tmp_path):
    daily, ctx = _ctx(tmp_path)
    issue = next(i for i in daily.issues if i.issue_type == IssueType.AD_INEFFICIENCY and i.entity_id == "sku_ad_inefficiency")
    planned = plan(issue, _report(issue, ("ad_efficiency",)), ctx, scripted_strategy_llm(IssueType.AD_INEFFICIENCY))
    selected = planned.state.initial_preferred_strategy_id
    simmed = attach_simulations(planned, ctx, n=2, seed=1)
    a = run_experiments(simmed, ctx, llm=None, n=2, seed=1)
    b = run_experiments(simmed, ctx, llm=None, n=2, seed=1)
    assert a.plan.state.initial_preferred_strategy_id == selected
    assert a.jobs_used <= 20
    assert a.stress_jobs <= 4
    assert 1 <= len(a.plan.state.final_recommendations) <= 3
    assert [r.rank for r in a.plan.state.final_recommendations] == list(range(1, len(a.plan.state.final_recommendations) + 1))
    target = selected if selected != "ST_do_nothing" else None
    if target:
        assert has_stress_for(a.plan.state.simulation_reports, target)
    assert [r.expected_profit for r in a.plan.state.simulation_reports] == [
        r.expected_profit for r in b.plan.state.simulation_reports
    ]
