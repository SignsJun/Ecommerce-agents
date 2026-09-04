from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from inspect import signature
from uuid import uuid4

from agents.diagnosis.causal_graph import CAUSE_TYPES, PREFLIGHT_TOOLS, is_allowed_tool
from agents.diagnosis.context import (
    PROMPT_VERSION,
    build_report_context,
    build_user_context,
    load_system_prompt,
)
from agents.diagnosis.policy import DEFAULT_BUDGET, InvestigationBudget
from agents.diagnosis.preflight import run_preflight
from agents.diagnosis.schema import (
    DiagnosisReportDraft,
    DiagnosisStep,
    LLMCauseAssessment,
    to_assessments,
    to_hypotheses,
    to_root_causes,
)
from agents.llm.client import LLMClient, LLMUnavailable
from domain.diagnosis.cause import CauseAssessment, CauseInvestigation, CauseStatus
from domain.diagnosis.hypothesis import RootCause, ToolCallRecord
from domain.diagnosis.report import DiagnosisReport
from domain.diagnosis.state import DiagnosisState
from domain.issue.models import Issue
from tools.diagnosis.base import TOOL_VERSION, ToolContext, ToolResult
from tools.diagnosis.handlers import project_horizon_dates
from tools.diagnosis.registry import invoke

def format_diagnosis_trace(outcome: DiagnoseOutcome) -> str:
    lines = ["Preflight Cause Status"]
    for c in outcome.preflight_causes:
        lines.append(f"  {c.cause_type}\t{c.status.value}")
    lines.append("→ ReAct 后 Cause Status")
    for c in outcome.post_react_causes:
        lines.append(f"  {c.cause_type}\t{c.status.value}")
    lines.append("→ CauseAssessment")
    for a in outcome.report.cause_assessments:
        lines.append(f"  {a.cause_type}\t{a.conclusion}\tconf={a.confidence}\tevidence={len(a.evidence_ids)}")
    if not outcome.report.cause_assessments:
        lines.append("  -")
    lines.append("→ Root Causes")
    for c in outcome.report.root_causes:
        lines.append(f"  {c.cause_type}\tconf={c.confidence}\tevidence={len(c.supporting_evidence_ids)}")
    if not outcome.report.root_causes:
        lines.append("  -")
    lines.append("→ Unresolved Active Causes")
    lines.append(f"  {','.join(outcome.report.unresolved_causes) or '-'}")
    lines.append("→ Final Status")
    lines.append(
        f"  {outcome.report.status}\tcoverage={outcome.report.active_investigation_coverage}\t"
        f"tools={outcome.report.tool_calls_used}"
    )
    return "\n".join(lines)

AGENT_VERSION = "diagnosis-v2"
MAX_TOOL_CALLS = DEFAULT_BUDGET.max_total_tool_calls
MAX_ROUNDS = DEFAULT_BUDGET.max_iterations
STAGNANT_LIMIT = 2


@dataclass
class DiagnoseOutcome:
    report: DiagnosisReport
    state: DiagnosisState
    irrelevant_tool_requests: int
    unnecessary_tool_requests: int
    prompt_version: str
    preflight_tools: tuple[str, ...] = ()
    recent_results: list[ToolResult] = field(default_factory=list)
    preflight_causes: list[CauseInvestigation] = field(default_factory=list)
    post_react_causes: list[CauseInvestigation] = field(default_factory=list)


def _coerce_args(raw: dict[str, str | int | float | bool | None]) -> dict[str, str | int | float | bool | None | date]:
    out: dict[str, str | int | float | bool | None | date] = {}
    for key, value in raw.items():
        if isinstance(value, str) and (key.endswith("_start") or key.endswith("_end")):
            out[key] = date.fromisoformat(value)
        else:
            out[key] = value
    return out


def _default_tool_args(issue: Issue, ctx: ToolContext, tool_name: str) -> dict:
    a0, a1, b0, b1 = project_horizon_dates(ctx.as_of)
    sku = issue.entity_id
    campaigns = ctx.business_repo.list_campaigns_for_sku(sku)
    mapping = {
        "get_issue_context": {"issue_id": issue.issue_id},
        "get_sku_summary": {"sku_id": sku},
        "decompose_profit": {
            "sku_id": sku,
            "period_a_start": a0,
            "period_a_end": a1,
            "period_b_start": b0,
            "period_b_end": b1,
        },
        "get_campaign_breakdown": {"sku_id": sku},
        "get_campaign_trend": {"campaign_id": campaigns[0] if campaigns else ""},
        "get_inventory_projection": {"sku_id": sku},
        "get_refund_breakdown": {"sku_id": sku},
        "analyze_reviews": {"sku_id": sku, "window_name": "7d"},
        "get_metric_trend": {
            "entity_type": "sku",
            "entity_id": sku,
            "metric": "profit_margin",
            "window_name": "7d",
        },
        "compare_peer_skus": {"sku_id": sku, "metrics": "profit_margin,roas,days_of_cover"},
    }
    return mapping.get(tool_name, {})


def _filter_kwargs(tool_name: str, args: dict) -> dict:
    from tools.diagnosis import registry as reg

    handler = reg._HANDLERS.get(tool_name)
    if handler is None:
        return args
    names = {p for p in signature(handler).parameters if p != "ctx"}
    return {k: v for k, v in args.items() if k in names}


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


def _get_cause(state: DiagnosisState, name: str | None) -> CauseInvestigation | None:
    if not name:
        return None
    return next((c for c in state.causes if c.cause_type == name), None)


def _put_cause(state: DiagnosisState, cause: CauseInvestigation) -> DiagnosisState:
    existing = next((c for c in state.causes if c.cause_type == cause.cause_type), None)
    if cause.status == CauseStatus.ACTIVE or cause.was_activated or (existing is not None and existing.was_activated):
        cause = cause.model_copy(update={"was_activated": True})
    found = False
    causes = []
    for item in state.causes:
        if item.cause_type == cause.cause_type:
            causes.append(cause)
            found = True
        else:
            causes.append(item)
    if not found:
        causes.append(cause)
    return state.model_copy(update={"causes": causes})


def _unresolved_active(state: DiagnosisState) -> list[CauseInvestigation]:
    return [c for c in state.causes if c.status == CauseStatus.ACTIVE]


def _budget_left(state: DiagnosisState, budget: InvestigationBudget, rounds: int) -> bool:
    return len(state.tool_history) < budget.max_total_tool_calls and rounds < budget.max_iterations


def _apply_hypotheses(state: DiagnosisState, step: DiagnosisStep) -> DiagnosisState:
    hyps = to_hypotheses(step.hypotheses)
    known = set(state.evidence_ids)
    next_state = state.model_copy(update={"hypotheses": hyps or state.hypotheses})
    for h in hyps:
        cur = _get_cause(next_state, h.cause_type)
        if cur is None:
            continue
        if cur.status != CauseStatus.ACTIVE:
            continue
        if h.status == "supported":
            kept = [eid for eid in h.supporting_evidence_ids if eid in known]
            if not kept:
                continue
            next_state = _put_cause(
                next_state,
                cur.model_copy(
                    update={
                        "status": CauseStatus.INVESTIGATED_SUPPORTED,
                        "confidence": max(0.0, min(1.0, h.confidence)),
                        "evidence_ids": list(dict.fromkeys([*cur.evidence_ids, *kept])),
                        "resolution_reason": h.description,
                    }
                ),
            )
        elif h.status == "rejected":
            next_state = _put_cause(
                next_state,
                cur.model_copy(update={"status": CauseStatus.INVESTIGATED_REJECTED, "resolution_reason": h.description}),
            )
    return next_state


_RESOLVED = {CauseStatus.INVESTIGATED_SUPPORTED, CauseStatus.INVESTIGATED_REJECTED}


def _activated(state: DiagnosisState) -> list[CauseInvestigation]:
    return [c for c in state.causes if c.was_activated]


def _unresolved_activated(state: DiagnosisState) -> list[CauseInvestigation]:
    return [c for c in _activated(state) if c.status not in _RESOLVED]


def _coverage(state: DiagnosisState) -> tuple[list[str], float]:
    activated = _activated(state)
    unresolved = [c.cause_type for c in _unresolved_activated(state)]
    if not activated:
        return unresolved, 1.0
    resolved = [c for c in activated if c.status in _RESOLVED]
    return unresolved, len(resolved) / len(activated)


def _ground_from_causes(state: DiagnosisState) -> list[RootCause]:
    known = set(state.evidence_ids)
    out: list[RootCause] = []
    for c in state.causes:
        if c.investigation_tool_calls < 1 and c.status != CauseStatus.INVESTIGATED_SUPPORTED:
            continue
        kept = [eid for eid in c.evidence_ids if eid in known]
        if not kept:
            continue
        conf = c.confidence if c.confidence else 0.7
        out.append(
            RootCause(
                cause_type=c.cause_type,
                description=c.resolution_reason or c.activation_reason or c.cause_type,
                confidence=conf,
                estimated_contribution=c.materiality_score,
                supporting_evidence_ids=kept,
            )
        )
    return out


def _legal_status(grounded: list[RootCause], state: DiagnosisState) -> str:
    if not grounded:
        return "insufficient_evidence"
    leftover = _unresolved_activated(state)
    if leftover:
        return "partial"
    return "confirmed"


def resolve_cause_states(
    state: DiagnosisState,
    grounded: list[RootCause],
    draft_assessments: list[LLMCauseAssessment] | list[CauseAssessment],
) -> tuple[DiagnosisState, list[CauseAssessment]]:
    known = set(state.evidence_ids)
    by_draft = {a.cause_type: a for a in to_assessments(list(draft_assessments))}
    grounded_map = {c.cause_type: c for c in grounded}
    assessments: list[CauseAssessment] = []
    next_state = state
    for cur in state.causes:
        draft_a = by_draft.get(cur.cause_type)
        if cur.cause_type in grounded_map:
            rc = grounded_map[cur.cause_type]
            assessment = CauseAssessment(
                cause_type=cur.cause_type,
                conclusion="supported",
                confidence=rc.confidence,
                evidence_ids=list(rc.supporting_evidence_ids),
            )
        elif draft_a is not None:
            eids = [eid for eid in draft_a.evidence_ids if eid in known]
            conclusion = draft_a.conclusion
            if conclusion == "supported" and not eids and cur.status != CauseStatus.INVESTIGATED_SUPPORTED:
                conclusion = "uncertain"
            assessment = CauseAssessment(
                cause_type=cur.cause_type,
                conclusion=conclusion,
                confidence=draft_a.confidence,
                evidence_ids=eids,
            )
        elif cur.status == CauseStatus.INVESTIGATED_REJECTED:
            assessment = CauseAssessment(
                cause_type=cur.cause_type,
                conclusion="rejected",
                confidence=cur.confidence,
                evidence_ids=list(cur.evidence_ids),
            )
        elif cur.status == CauseStatus.INVESTIGATED_SUPPORTED:
            assessment = CauseAssessment(
                cause_type=cur.cause_type,
                conclusion="supported",
                confidence=cur.confidence,
                evidence_ids=list(cur.evidence_ids),
            )
        elif cur.status == CauseStatus.ACTIVE:
            assessment = CauseAssessment(
                cause_type=cur.cause_type,
                conclusion="uncertain",
                confidence=0.0,
                evidence_ids=list(cur.evidence_ids),
            )
        else:
            continue
        assessments.append(assessment)
        latest = _get_cause(next_state, cur.cause_type) or cur
        if assessment.conclusion == "supported":
            next_state = _put_cause(
                next_state,
                latest.model_copy(
                    update={
                        "status": CauseStatus.INVESTIGATED_SUPPORTED,
                        "confidence": assessment.confidence or latest.confidence,
                        "evidence_ids": list(dict.fromkeys([*latest.evidence_ids, *assessment.evidence_ids])),
                        "resolution_reason": latest.resolution_reason or "supported_by_evidence",
                    }
                ),
            )
        elif assessment.conclusion == "rejected":
            next_state = _put_cause(
                next_state,
                latest.model_copy(
                    update={
                        "status": CauseStatus.INVESTIGATED_REJECTED,
                        "confidence": assessment.confidence,
                        "evidence_ids": list(dict.fromkeys([*latest.evidence_ids, *assessment.evidence_ids])),
                        "resolution_reason": latest.resolution_reason or "rejected",
                    }
                ),
            )
        elif assessment.conclusion == "uncertain" and latest.status == CauseStatus.ACTIVE:
            next_state = _put_cause(
                next_state,
                latest.model_copy(
                    update={
                        "status": CauseStatus.BLOCKED_BY_DATA,
                        "resolution_reason": latest.resolution_reason or "insufficient_data",
                    }
                ),
            )
    return next_state, assessments


def _validate_report(
    state: DiagnosisState, draft: DiagnosisReportDraft, model_version: str, now
) -> tuple[DiagnosisReport, DiagnosisState]:
    known = set(state.evidence_ids)
    grounded: list[RootCause] = []
    for cause in to_root_causes(draft.root_causes):
        kept = [eid for eid in cause.supporting_evidence_ids if eid in known]
        if not kept:
            continue
        grounded.append(
            RootCause(
                cause_type=cause.cause_type,
                description=cause.description,
                confidence=cause.confidence,
                estimated_contribution=cause.estimated_contribution,
                supporting_evidence_ids=kept,
            )
        )
    if not grounded:
        grounded = _ground_from_causes(state)
    state, assessments = resolve_cause_states(state, grounded, draft.cause_assessments)
    status = _legal_status(grounded, state)
    overall = max((c.confidence for c in grounded), default=0.0)
    if draft.overall_confidence and grounded:
        overall = max(overall, max(0.0, min(1.0, draft.overall_confidence)))
    key_ids: list[str] = []
    for c in grounded:
        for eid in c.supporting_evidence_ids:
            if eid not in key_ids:
                key_ids.append(eid)
    unresolved, cov = _coverage(state)
    return (
        DiagnosisReport(
            diagnosis_id=state.diagnosis_id,
            issue_id=state.issue.issue_id,
            status=status,
            root_causes=grounded,
            overall_confidence=overall,
            key_evidence_ids=key_ids,
            uncertainties=list(draft.uncertainties) or list(state.unresolved_questions),
            generated_at=now,
            agent_version=AGENT_VERSION,
            model_version=model_version,
            screened_causes=list(state.causes),
            cause_assessments=assessments,
            unresolved_causes=unresolved,
            active_investigation_coverage=cov,
            tool_calls_used=len(state.tool_history),
        ),
        state,
    )


def _fallback_report(state: DiagnosisState, model_version: str, reason: str, now) -> tuple[DiagnosisReport, DiagnosisState]:
    state, assessments = resolve_cause_states(state, [], [])
    unresolved, cov = _coverage(state)
    return (
        DiagnosisReport(
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
            screened_causes=list(state.causes),
            cause_assessments=assessments,
            unresolved_causes=unresolved,
            active_investigation_coverage=cov,
            tool_calls_used=len(state.tool_history),
        ),
        state,
    )


def _allowed_cause(issue_type, name: str) -> bool:
    return name in CAUSE_TYPES.get(issue_type, ())


def diagnose(
    issue: Issue,
    ctx: ToolContext,
    llm: LLMClient,
    budget: InvestigationBudget | None = None,
) -> DiagnoseOutcome:
    budget = budget or DEFAULT_BUDGET
    state = DiagnosisState(
        diagnosis_id=f"DX_{uuid4().hex[:12]}",
        issue=issue,
        evidence_ids=list(issue.evidence_ids),
        diagnosis_status="in_progress",
    )
    state, recent = run_preflight(state, ctx)
    preflight_causes = list(state.causes)
    system = load_system_prompt()
    irrelevant = 0
    unnecessary = 0
    stagnant = 0
    rounds = 0

    while _budget_left(state, budget, rounds):
        try:
            step = llm.complete(system, build_user_context(state, ctx, recent), DiagnosisStep)
        except LLMUnavailable:
            stagnant += 1
            rounds += 1
            if stagnant >= STAGNANT_LIMIT:
                break
            continue
        state = state.model_copy(
            update={
                "unresolved_questions": list(step.unresolved_questions) or state.unresolved_questions,
                "step_count": state.step_count + 1,
                "gate_feedback": None,
            }
        )
        state = _apply_hypotheses(state, step)
        rounds += 1
        action = step.action
        if action == "escalate":
            note = step.reason or step.stop_reason or "escalate"
            state = state.model_copy(update={"unresolved_questions": [*state.unresolved_questions, note]})
            continue
        if action == "activate_cause":
            name = step.target_cause
            if not name or not _allowed_cause(issue.issue_type, name):
                stagnant += 1
                continue
            cur = _get_cause(state, name)
            kept = [eid for eid in step.evidence_ids if eid in state.evidence_ids]
            if cur is None:
                cur = CauseInvestigation(cause_type=name, status=CauseStatus.UNSCREENED)
            if cur.status in {CauseStatus.INVESTIGATED_SUPPORTED, CauseStatus.INVESTIGATED_REJECTED}:
                continue
            state = _put_cause(
                state,
                cur.model_copy(
                    update={
                        "status": CauseStatus.ACTIVE,
                        "activation_reason": step.reason or "agent_reactivate",
                        "evidence_ids": list(dict.fromkeys([*cur.evidence_ids, *kept])),
                    }
                ),
            )
            stagnant = 0
            continue
        if action == "reject_cause":
            cur = _get_cause(state, step.target_cause)
            if cur is None or cur.status != CauseStatus.ACTIVE:
                stagnant += 1
                continue
            state = _put_cause(
                state,
                cur.model_copy(
                    update={
                        "status": CauseStatus.INVESTIGATED_REJECTED,
                        "resolution_reason": step.reason or "rejected",
                    }
                ),
            )
            stagnant = 0
            continue
        if action == "request_stop":
            if _unresolved_active(state) and _budget_left(state, budget, rounds):
                missing = ",".join(c.cause_type for c in _unresolved_active(state))
                state = state.model_copy(update={"gate_feedback": f"STOP_REJECTED unresolved_active={missing}"})
                continue
            break
        if action != "call_tool" or not step.tool_name:
            stagnant += 1
            continue
        target = step.target_cause
        cur = _get_cause(state, target)
        if cur is not None and cur.status == CauseStatus.SCREENED_NON_MATERIAL:
            unnecessary += 1
            state = state.model_copy(update={"tool_history": [*state.tool_history, _rejected_call(ctx, step.tool_name, step.tool_args)]})
            stagnant += 1
            continue
        if cur is not None and cur.status == CauseStatus.SCREENED_POSSIBLE:
            cur = cur.model_copy(update={"status": CauseStatus.ACTIVE, "activation_reason": step.reason or "tool_on_possible"})
            state = _put_cause(state, cur)
        if cur is None or cur.status != CauseStatus.ACTIVE:
            stagnant += 1
            continue
        if cur.investigation_tool_calls >= budget.max_calls_per_cause:
            stagnant += 1
            continue
        if not is_allowed_tool(issue.issue_type, step.tool_name):
            irrelevant += 1
            state = state.model_copy(update={"tool_history": [*state.tool_history, _rejected_call(ctx, step.tool_name, step.tool_args)]})
            stagnant += 1
            continue
        try:
            kwargs = _filter_kwargs(
                step.tool_name,
                _coerce_args({**_default_tool_args(issue, ctx, step.tool_name), **step.tool_args}),
            )
            result = invoke(ctx, step.tool_name, **kwargs)
        except (TypeError, ValueError):
            state = state.model_copy(update={"tool_history": [*state.tool_history, _rejected_call(ctx, step.tool_name, step.tool_args)]})
            stagnant += 1
            continue
        recent.append(result)
        new_ids = [e.evidence_id for e in result.evidence if e.evidence_id not in state.evidence_ids]
        cause_ids = list(dict.fromkeys([*cur.evidence_ids, *new_ids]))
        update = {
            "investigation_tool_calls": cur.investigation_tool_calls + 1,
            "evidence_ids": cause_ids,
        }
        if not result.success and result.error and result.error.error_code == "empty_result":
            update["status"] = CauseStatus.BLOCKED_BY_DATA
            update["resolution_reason"] = result.error.message
        state = _put_cause(state, cur.model_copy(update=update))
        state = state.model_copy(
            update={
                "tool_history": [*state.tool_history, result.call],
                "evidence_ids": [*state.evidence_ids, *new_ids],
            }
        )
        if new_ids:
            stagnant = 0
        else:
            stagnant += 1
        if stagnant >= STAGNANT_LIMIT:
            break

    post_react_causes = list(state.causes)
    try:
        draft = llm.complete(system, build_report_context(state, ctx), DiagnosisReportDraft)
        report, state = _validate_report(state, draft, llm.model_name, ctx.now)
    except LLMUnavailable:
        report, state = _fallback_report(state, llm.model_name, "llm_unavailable", ctx.now)
    state = state.model_copy(update={"root_causes": report.root_causes, "diagnosis_status": report.status})
    return DiagnoseOutcome(
        report=report,
        state=state,
        irrelevant_tool_requests=irrelevant,
        unnecessary_tool_requests=unnecessary,
        prompt_version=PROMPT_VERSION,
        preflight_tools=PREFLIGHT_TOOLS.get(issue.issue_type, ()),
        recent_results=recent,
        preflight_causes=preflight_causes,
        post_react_causes=post_react_causes,
    )
