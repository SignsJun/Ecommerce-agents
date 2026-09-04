import json
from pathlib import Path

from agents.diagnosis.agent import diagnose
from agents.llm.scripts import scripted_llm
from domain.enums import IssueType
from evals.diagnosis.metrics import (
    correct_escalation,
    evidence_grounding,
    hallucination_rate,
    irrelevant_tool_rate,
    root_cause_accuracy,
    tool_efficiency,
)
from services.daily_run import run_daily
from tools.diagnosis.investigate import context_from_run

_SCENARIO_DIR = Path(__file__).resolve().parents[1] / "scenarios"


def load_scenarios() -> list[dict]:
    rows = []
    for path in sorted(_SCENARIO_DIR.glob("*.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows


def _score(spec: dict, outcome, expect_insufficient: bool) -> dict:
    hidden = spec["hidden_root_causes"]
    return {
        "scenario_id": spec["scenario_id"],
        "status": outcome.report.status,
        "root_cause_accuracy": root_cause_accuracy(outcome.report, hidden),
        "evidence_grounding": evidence_grounding(outcome.report, outcome.state),
        "tool_efficiency": tool_efficiency(outcome.state),
        "irrelevant_tool_rate": irrelevant_tool_rate(outcome),
        "hallucination_rate": hallucination_rate(outcome.report, outcome.state),
        "correct_escalation": correct_escalation(outcome.report, expect_insufficient),
    }


def run_fake_benchmark(data_dir: Path, now, settings) -> list[dict]:
    daily = run_daily(data_dir, settings=settings, now=now)
    ctx = context_from_run(daily)
    scores = []
    for spec in load_scenarios():
        issue = next(i for i in daily.issues if i.entity_id == spec["issue_entity_id"])
        llm = scripted_llm(IssueType(spec["issue_type"]))
        outcome = diagnose(issue, ctx, llm)
        scores.append(_score(spec, outcome, False))
    return scores


def run_missing_metrics_escalation(data_dir: Path, now, settings) -> dict:
    daily = run_daily(data_dir, settings=settings, now=now)
    ctx = context_from_run(daily)
    ctx.business_repo._sku_daily.clear()
    ctx.business_repo._campaign_daily.clear()
    spec = next(s for s in load_scenarios() if s["issue_type"] == "profit_erosion")
    issue = next(i for i in daily.issues if i.entity_id == spec["issue_entity_id"])
    outcome = diagnose(issue, ctx, scripted_llm(IssueType.PROFIT_EROSION))
    return _score(spec, outcome, True)
