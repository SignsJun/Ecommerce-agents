from agents.decision.agent import attach_simulations, plan
from agents.diagnosis.agent import diagnose
from agents.llm.scripts import scripted_llm, scripted_strategy_llm
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


def run_simulation_benchmark(data_dir, now, settings, *, n: int = 8, seed: int = 42):
    daily = run_daily(data_dir, settings=settings, now=now)
    ctx = context_from_run(daily)
    rows = []
    for spec in load_scenarios():
        issue = _match(daily, spec)
        report = diagnose(issue, ctx, scripted_llm(IssueType(spec["issue_type"]))).report
        planned = plan(issue, report, ctx, scripted_strategy_llm(IssueType(spec["issue_type"])))
        selected = planned.state.selected_strategy_id
        simmed = attach_simulations(planned, ctx, seed=seed, n=n)
        open_loop = attach_simulations(planned, ctx, seed=seed, n=n, open_loop=True)
        reports = simmed.state.simulation_reports
        rows.append(
            {
                "scenario_id": spec["scenario_id"],
                "selected": simmed.state.selected_strategy_id,
                "selected_unchanged": simmed.state.selected_strategy_id == selected,
                "n_reports": len(reports),
                "ordered": all(r.profit_p10 <= r.profit_p50 <= r.profit_p90 for r in reports),
                "has_do_nothing": any(r.strategy_id == "ST_do_nothing" for r in reports),
                "adaptive": all(r.adaptive for r in reports),
                "open_loop_static": all(not r.adaptive for r in open_loop.state.simulation_reports),
                "reports": reports,
                "open_loop_reports": open_loop.state.simulation_reports,
            }
        )
    return rows
