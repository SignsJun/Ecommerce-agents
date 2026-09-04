import json
from pathlib import Path

from agents.diagnosis.agent import diagnose, format_diagnosis_trace
from agents.llm.scripts import scripted_llm
from domain.enums import IssueType
from evals.diagnosis.metrics import (
    evidence_accuracy,
    finalization_accuracy,
    root_cause_f1,
    root_cause_precision,
    root_cause_recall,
)
from services.daily_run import run_daily
from tools.diagnosis.investigate import context_from_run

_SCENARIO_DIR = Path(__file__).resolve().parents[1] / "scenarios"


def load_scenarios() -> list[dict]:
    rows = []
    for path in sorted(_SCENARIO_DIR.glob("*.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows


def _score(spec: dict, outcome, expected_status: str) -> dict:
    hidden = spec["hidden_root_causes"]
    return {
        "scenario_id": spec["scenario_id"],
        "status": outcome.report.status,
        "root_cause_precision": root_cause_precision(outcome.report, hidden),
        "root_cause_recall": root_cause_recall(outcome.report, hidden),
        "root_cause_f1": root_cause_f1(outcome.report, hidden),
        "evidence_accuracy": evidence_accuracy(outcome.report, outcome.state),
        "tool_calls": outcome.report.tool_calls_used,
        "finalization_accuracy": finalization_accuracy(outcome.report, expected_status),
        "trace": format_diagnosis_trace(outcome),
    }


def run_fake_benchmark(data_dir: Path, now, settings) -> list[dict]:
    daily = run_daily(data_dir, settings=settings, now=now)
    ctx = context_from_run(daily)
    scores = []
    for spec in load_scenarios():
        issue = next(i for i in daily.issues if i.entity_id == spec["issue_entity_id"])
        llm = scripted_llm(IssueType(spec["issue_type"]))
        outcome = diagnose(issue, ctx, llm)
        scores.append(_score(spec, outcome, "confirmed"))
    return scores


def run_missing_metrics_escalation(data_dir: Path, now, settings) -> dict:
    daily = run_daily(data_dir, settings=settings, now=now)
    ctx = context_from_run(daily)
    ctx.business_repo._sku_daily.clear()
    ctx.business_repo._campaign_daily.clear()
    spec = next(s for s in load_scenarios() if s["issue_type"] == "profit_erosion")
    issue = next(i for i in daily.issues if i.entity_id == spec["issue_entity_id"])
    outcome = diagnose(issue, ctx, scripted_llm(IssueType.PROFIT_EROSION))
    return _score(spec, outcome, "insufficient_evidence")
