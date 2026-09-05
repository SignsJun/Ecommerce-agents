from pathlib import Path

from agents.decision.agent import plan, plan_from_rules
from agents.diagnosis.agent import diagnose
from agents.llm.scripts import scripted_llm, scripted_strategy_llm
from domain.enums import IssueType
from evals.diagnosis.runner import load_scenarios
from evals.strategy.metrics import constraint_violation_rate, feasibility_rate, strategy_diversity
from services.daily_run import run_daily
from tools.diagnosis.investigate import context_from_run


def _match_issue(daily, spec):
    return next(
        i
        for i in daily.issues
        if i.entity_id == spec["issue_entity_id"] and i.issue_type == IssueType(spec["issue_type"])
    )


def _row(spec, planned, report) -> dict:
    return {
        "scenario_id": spec["scenario_id"],
        "diagnosis_status": report.status,
        "generation_source": planned.generation_source,
        "selected": planned.state.selected_strategy_id,
        "feasible": sum(1 for v in planned.validations if v.feasible),
        "feasibility_rate": feasibility_rate(planned),
        "constraint_violation_rate": constraint_violation_rate(planned),
        "diversity": strategy_diversity(planned),
        "needs_simulation": planned.needs_simulation,
        "approval_required": planned.approval_required,
        "approval_from_partial_only": report.status == "partial"
        and planned.approval_required
        and not any(a.action_type in {"adjust_price", "replenish", "pause_campaign"} for a in planned.rank.selected.strategy.actions)
        and not any(i == "strong" for i in planned.rank.selected.intensities),
    }


def run_llm_strategy_benchmark(data_dir: Path, now, settings) -> list[dict]:
    daily = run_daily(data_dir, settings=settings, now=now)
    ctx = context_from_run(daily)
    rows = []
    for spec in load_scenarios():
        issue = _match_issue(daily, spec)
        report = diagnose(issue, ctx, scripted_llm(IssueType(spec["issue_type"]))).report
        planned = plan(issue, report, ctx, scripted_strategy_llm(IssueType(spec["issue_type"])))
        rows.append(_row(spec, planned, report))
    return rows


def run_rule_strategy_benchmark(data_dir: Path, now, settings) -> list[dict]:
    daily = run_daily(data_dir, settings=settings, now=now)
    ctx = context_from_run(daily)
    rows = []
    for spec in load_scenarios():
        issue = _match_issue(daily, spec)
        report = diagnose(issue, ctx, scripted_llm(IssueType(spec["issue_type"]))).report
        planned = plan_from_rules(issue, report, ctx)
        rows.append(_row(spec, planned, report))
    return rows
