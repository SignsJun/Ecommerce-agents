from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from inspect import signature
from uuid import uuid4

from agents.diagnosis.causal_graph import COVERAGE_TOOLS, is_allowed_tool
from agents.diagnosis.context import (
    PROMPT_VERSION,
    build_report_context,
    build_user_context,
    load_system_prompt,
)
from agents.diagnosis.schema import (
    DiagnosisReportDraft,
    DiagnosisStep,
    to_hypotheses,
    to_root_causes,
)
from agents.llm.client import LLMClient, LLMUnavailable
from domain.diagnosis.hypothesis import RootCause, ToolCallRecord
from domain.diagnosis.report import DiagnosisReport
from domain.diagnosis.state import DiagnosisState
from domain.issue.models import Issue
from tools.diagnosis.base import TOOL_VERSION, ToolContext, ToolResult
from tools.diagnosis.registry import invoke

AGENT_VERSION = "diagnosis-v1"
MAX_TOOL_CALLS = 8
MAX_ROUNDS = 6
STAGNANT_LIMIT = 2
CONF_THRESHOLD = 0.75


@dataclass
class DiagnoseOutcome:
    report: DiagnosisReport
    state: DiagnosisState
    irrelevant_tool_requests: int
    prompt_version: str
    recent_results: list[ToolResult] = field(default_factory=list)


def _coerce_args(raw: dict[str, str | int | float | bool | None]) -> dict[str, str | int | float | bool | None | date]:
    out: dict[str, str | int | float | bool | None | date] = {}
    for key, value in raw.items():
        if isinstance(value, str) and (key.endswith("_start") or key.endswith("_end")):
            out[key] = date.fromisoformat(value)
        else:
            out[key] = value
    return out


def _filter_kwargs(tool_name: str, args: dict) -> dict:
    from tools.diagnosis import registry as reg

    handler = reg._HANDLERS.get(tool_name)
    if handler is None:
        return args
    names = {p for p in signature(handler).parameters if p != "ctx"}
    return {k: v for k, v in args.items() if k in names}


def _coverage_ok(state: DiagnosisState) -> bool:
    needed = COVERAGE_TOOLS.get(state.issue.issue_type, frozenset())
    used = {t.tool_name for t in state.tool_history if t.success}
    if not needed:
        return False
    return bool(used & needed)


def _high_conf(state: DiagnosisState) -> bool:
    return any(
        h.confidence >= CONF_THRESHOLD and h.supporting_evidence_ids and h.status == "supported"
        for h in state.hypotheses
    )


def _should_stop(state: DiagnosisState, stagnant: int, tool_calls: int, rounds: int) -> bool:
    if tool_calls >= MAX_TOOL_CALLS:
        return True
    if rounds >= MAX_ROUNDS:
        return True
    if stagnant >= STAGNANT_LIMIT:
        return True
    if _high_conf(state) and _coverage_ok(state):
        return True
    return False


def _rejected_call(ctx: ToolContext, tool_name: str, args: dict) -> ToolCallRecord:
    clean = {k: v for k, v in args.items() if isinstance(v, (str, int, float, bool)) or v is None}
    return ToolCallRecord(
        tool_name=tool_name,
        tool_version=TOOL_VERSION,
        arguments=clean,
        success=False,
        error_code="unavailable",
        evidence_ids=[],
        called_at=ctx.now,
    )


def _validate_report(
    state: DiagnosisState, draft: DiagnosisReportDraft, model_version: str, now
) -> DiagnosisReport:
    known = set(state.evidence_ids)
    causes: list[RootCause] = []
    for cause in to_root_causes(draft.root_causes):
        kept = [eid for eid in cause.supporting_evidence_ids if eid in known]
        if not kept:
            continue
        causes.append(
            RootCause(
                cause_type=cause.cause_type,
                description=cause.description,
                confidence=cause.confidence,
                estimated_contribution=cause.estimated_contribution,
                supporting_evidence_ids=kept,
            )
        )
    status = draft.status
    if not causes or not _coverage_ok(state):
        status = "insufficient_evidence"
    overall = max(0.0, min(1.0, draft.overall_confidence))
    if status == "insufficient_evidence":
        overall = min(overall, 0.4)
    key_ids: list[str] = []
    for c in causes:
        for eid in c.supporting_evidence_ids:
            if eid not in key_ids:
                key_ids.append(eid)
    return DiagnosisReport(
        diagnosis_id=state.diagnosis_id,
        issue_id=state.issue.issue_id,
        status=status,
        root_causes=causes,
        overall_confidence=overall,
        key_evidence_ids=key_ids,
        uncertainties=list(draft.uncertainties) or list(state.unresolved_questions),
        generated_at=now,
        agent_version=AGENT_VERSION,
        model_version=model_version,
    )


def _fallback_report(state: DiagnosisState, model_version: str, reason: str, now) -> DiagnosisReport:
    return DiagnosisReport(
        diagnosis_id=state.diagnosis_id,
        issue_id=state.issue.issue_id,
        status="insufficient_evidence",
        root_causes=[],
        overall_confidence=0.0,
        key_evidence_ids=[],
        uncertainties=[reason, *state.unresolved_questions],
        generated_at=now,
        agent_version=AGENT_VERSION,
        model_version=model_version,
    )


def diagnose(issue: Issue, ctx: ToolContext, llm: LLMClient) -> DiagnoseOutcome:
    state = DiagnosisState(
        diagnosis_id=f"DX_{uuid4().hex[:12]}",
        issue=issue,
        evidence_ids=list(issue.evidence_ids),
        diagnosis_status="in_progress",
    )
    system = load_system_prompt()
    recent: list[ToolResult] = []
    irrelevant = 0
    stagnant = 0
    rounds = 0
    tool_calls = 0

    while True:
        if _should_stop(state, stagnant, tool_calls, rounds) and rounds > 0:
            break
        if rounds >= MAX_ROUNDS:
            break
        try:
            step = llm.complete(system, build_user_context(state, ctx, recent), DiagnosisStep)
        except LLMUnavailable:
            stagnant += 1
            rounds += 1
            if stagnant >= STAGNANT_LIMIT or rounds >= MAX_ROUNDS:
                break
            continue
        state = state.model_copy(
            update={
                "hypotheses": to_hypotheses(step.hypotheses) or state.hypotheses,
                "unresolved_questions": list(step.unresolved_questions),
                "step_count": state.step_count + 1,
            }
        )
        rounds += 1
        if step.action != "call_tool" or not step.tool_name:
            break
        tool_calls += 1
        if not is_allowed_tool(issue.issue_type, step.tool_name):
            irrelevant += 1
            record = _rejected_call(ctx, step.tool_name, step.tool_args)
            state = state.model_copy(update={"tool_history": [*state.tool_history, record]})
            stagnant += 1
            if _should_stop(state, stagnant, tool_calls, rounds):
                break
            continue
        try:
            kwargs = _filter_kwargs(step.tool_name, _coerce_args(step.tool_args))
            result = invoke(ctx, step.tool_name, **kwargs)
        except (TypeError, ValueError):
            record = _rejected_call(ctx, step.tool_name, step.tool_args)
            state = state.model_copy(update={"tool_history": [*state.tool_history, record]})
            stagnant += 1
            continue
        recent.append(result)
        new_ids = [e.evidence_id for e in result.evidence if e.evidence_id not in state.evidence_ids]
        evidence_ids = [*state.evidence_ids, *new_ids]
        state = state.model_copy(
            update={
                "tool_history": [*state.tool_history, result.call],
                "evidence_ids": evidence_ids,
            }
        )
        if new_ids:
            stagnant = 0
        else:
            stagnant += 1
        if _should_stop(state, stagnant, tool_calls, rounds):
            break

    try:
        draft = llm.complete(system, build_report_context(state, ctx), DiagnosisReportDraft)
        report = _validate_report(state, draft, llm.model_name, ctx.now)
    except LLMUnavailable:
        report = _fallback_report(state, llm.model_name, "llm_unavailable", ctx.now)
    state = state.model_copy(
        update={
            "root_causes": report.root_causes,
            "diagnosis_status": report.status,
        }
    )
    return DiagnoseOutcome(
        report=report,
        state=state,
        irrelevant_tool_requests=irrelevant,
        prompt_version=PROMPT_VERSION,
        recent_results=recent,
    )
