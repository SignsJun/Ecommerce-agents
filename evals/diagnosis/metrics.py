from agents.diagnosis.agent import DiagnoseOutcome
from domain.diagnosis.report import DiagnosisReport
from domain.diagnosis.state import DiagnosisState


def root_cause_accuracy(report: DiagnosisReport, hidden: list[str]) -> float:
    if not hidden:
        return 1.0
    got = {c.cause_type for c in report.root_causes}
    hit = len(got & set(hidden))
    return hit / len(hidden)


def evidence_grounding(report: DiagnosisReport, state: DiagnosisState) -> float:
    known = set(state.evidence_ids)
    cited = [eid for c in report.root_causes for eid in c.supporting_evidence_ids]
    if not cited:
        return 1.0 if report.status == "insufficient_evidence" else 0.0
    ok = sum(1 for eid in cited if eid in known)
    return ok / len(cited)


def tool_efficiency(state: DiagnosisState, cap: int = 8) -> float:
    n = len(state.tool_history)
    return 1.0 if n <= cap else cap / n


def irrelevant_tool_rate(outcome: DiagnoseOutcome) -> float:
    total = len(outcome.state.tool_history)
    if total == 0:
        return 0.0
    return outcome.irrelevant_tool_requests / total


def hallucination_rate(report: DiagnosisReport, state: DiagnosisState) -> float:
    known = set(state.evidence_ids)
    cited = [eid for c in report.root_causes for eid in c.supporting_evidence_ids]
    if not cited:
        return 0.0
    bad = sum(1 for eid in cited if eid not in known)
    return bad / len(cited)


def unnecessary_investigation_rate(outcome: DiagnoseOutcome) -> float:
    pre = set(outcome.preflight_tools)
    agent_calls = [t for t in outcome.state.tool_history if t.tool_name not in pre]
    if not agent_calls:
        return 0.0
    return outcome.unnecessary_tool_requests / len(agent_calls)


def correct_escalation(report: DiagnosisReport, expect_insufficient: bool) -> float:
    got = report.status == "insufficient_evidence"
    return 1.0 if got == expect_insufficient else 0.0
