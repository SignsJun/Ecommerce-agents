from agents.decision.agent import attach_simulations, plan
from agents.diagnosis.agent import diagnose
from agents.llm.scripts import scripted_llm, scripted_strategy_llm
from agents.simulation.agent import run_experiments
from agents.simulation.compare import has_stress_for
from domain.enums import IssueType
from evals.diagnosis.runner import load_scenarios
from services.daily_run import run_daily
from tools.diagnosis.investigate import context_from_run


def _match(daily, spec):
    return next(
        i
        for i in daily.issues
        if i.entity_id == spec["issue_entity_id"] and i.issue_type == IssueType(spec["issue_type"])
    )


def run_experiment_benchmark(data_dir, now, settings, *, n: int = 4, seed: int = 42):
    daily = run_daily(data_dir, settings=settings, now=now)
    ctx = context_from_run(daily)
    rows = []
    for spec in load_scenarios():
        issue = _match(daily, spec)
        report = diagnose(issue, ctx, scripted_llm(IssueType(spec["issue_type"]))).report
        planned = plan(issue, report, ctx, scripted_strategy_llm(IssueType(spec["issue_type"])))
        selected = planned.state.initial_preferred_strategy_id
        simmed = attach_simulations(planned, ctx, seed=seed, n=n)
        exp = run_experiments(simmed, ctx, llm=None, seed=seed, n=n)
        target = selected if selected != "ST_do_nothing" else None
        recs = exp.plan.state.final_recommendations
        rows.append(
            {
                "scenario_id": spec["scenario_id"],
                "selected": exp.plan.state.initial_preferred_strategy_id,
                "selected_unchanged": exp.plan.state.initial_preferred_strategy_id == selected,
                "has_stress": bool(target and has_stress_for(exp.plan.state.simulation_reports, target)),
                "jobs": exp.jobs_used,
                "status": exp.experiment_status,
                "n_recs": len(recs),
                "ranks": [r.rank for r in recs],
                "profits": [r.expected_profit for r in exp.plan.state.simulation_reports],
            }
        )
    return rows
