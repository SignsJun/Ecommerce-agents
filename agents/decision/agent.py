from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from agents.decision.context import PROMPT_VERSION, build_plan_context, load_system_prompt
from agents.decision.materialize import MaterializedStrategy, do_nothing_strategy, materialize_draft
from agents.decision.schema import StrategyPlanDraft
from agents.llm.client import LLMClient, LLMUnavailable
from domain.decision.approval import ApprovalState
from domain.decision.state import DecisionState
from domain.diagnosis.report import DiagnosisReport
from domain.enums import DecisionPhase
from domain.issue.models import Issue
from domain.strategy.validation import StrategyValidationResult
from services.strategy.baseline import RankResult, rank_without_simulation
from services.strategy.templates import rule_plan_draft
from services.strategy.validator import validate_strategy
from tools.diagnosis.base import ToolContext

AGENT_VERSION = "decision-v1"


@dataclass
class PlanOutcome:
    state: DecisionState
    generation_source: str
    needs_simulation: bool
    approval_required: bool
    recommendation_confidence: float
    validations: list[StrategyValidationResult]
    materialized: list[MaterializedStrategy]
    rank: RankResult
    prompt_version: str = PROMPT_VERSION


def _finish(
    issue: Issue,
    report: DiagnosisReport,
    ctx: ToolContext,
    drafts: StrategyPlanDraft,
    source: str,
) -> PlanOutcome:
    snap = ctx.snapshot()
    policy = ctx.policy
    items = [
        materialize_draft(d, issue, snap, policy, report, strategy_id=f"ST_{uuid4().hex[:10]}")
        for d in drafts.strategies
    ]
    items.append(do_nothing_strategy(issue, snap, policy))
    validations = [validate_strategy(it.strategy, snap, policy, issue) for it in items]
    kept: list[MaterializedStrategy] = []
    rejected_ids: list[str] = []
    for item, result in zip(items, validations):
        if result.feasible and result.normalized_strategy is not None:
            kept.append(MaterializedStrategy(strategy=result.normalized_strategy, intensities=item.intensities))
        else:
            rejected_ids.append(item.strategy.strategy_id)
    if not kept:
        kept = [do_nothing_strategy(issue, snap, policy)]
        extra = validate_strategy(kept[0].strategy, snap, policy, issue)
        validations = [*validations, extra]
        if extra.normalized_strategy is not None:
            kept = [MaterializedStrategy(strategy=extra.normalized_strategy, intensities=())]
    ranked = rank_without_simulation(kept, report)
    now = ctx.now
    approval = ApprovalState(
        required=ranked.approval_required,
        status="pending" if ranked.approval_required else "not_required",
        risk_level="high" if ranked.approval_required else "low",
    )
    state = DecisionState(
        decision_id=f"DEC_{uuid4().hex[:12]}",
        phase=DecisionPhase.EVALUATING,
        issue=issue,
        diagnosis_report=report,
        candidate_strategies=[it.strategy for it in kept],
        simulation_reports=[],
        rejected_strategy_ids=rejected_ids,
        selected_strategy_id=ranked.selected.strategy.strategy_id,
        approval=approval,
        execution=None,
        monitoring=None,
        trace_id=f"TR_{uuid4().hex[:12]}",
        created_at=now,
        updated_at=now,
    )
    return PlanOutcome(
        state=state,
        generation_source=source,
        needs_simulation=ranked.needs_simulation,
        approval_required=ranked.approval_required,
        recommendation_confidence=ranked.confidence,
        validations=validations,
        materialized=items,
        rank=ranked,
        prompt_version=PROMPT_VERSION,
    )


def plan(issue: Issue, report: DiagnosisReport, ctx: ToolContext, llm: LLMClient) -> PlanOutcome:
    if report.status == "insufficient_evidence":
        return _finish(issue, report, ctx, StrategyPlanDraft(strategies=[]), "llm")
    try:
        draft = llm.complete(load_system_prompt(), build_plan_context(issue, report, ctx), StrategyPlanDraft)
        return _finish(issue, report, ctx, draft, "llm")
    except LLMUnavailable:
        return plan_from_rules(issue, report, ctx, source="llm_fallback")


def plan_from_rules(
    issue: Issue,
    report: DiagnosisReport,
    ctx: ToolContext,
    *,
    source: str = "rule",
) -> PlanOutcome:
    if report.status == "insufficient_evidence":
        return _finish(issue, report, ctx, StrategyPlanDraft(strategies=[]), source)
    return _finish(issue, report, ctx, rule_plan_draft(issue, report, ctx.snapshot()), source)


def format_plan_trace(outcome: PlanOutcome) -> str:
    report = outcome.state.diagnosis_report
    status = report.status if report else "-"
    lines = [
        f"plan\tgeneration_source={outcome.generation_source}\tdiagnosis={status}",
        f"selected={outcome.state.selected_strategy_id}\tneeds_simulation={outcome.needs_simulation}\t"
        f"approval_required={outcome.approval_required}\tconfidence={outcome.recommendation_confidence}",
    ]
    by_id = {v.strategy_id: v for v in outcome.validations}
    for item in outcome.materialized:
        result = by_id.get(item.strategy.strategy_id)
        feasible = result.feasible if result else False
        reason = result.errors[0].code if result and result.errors else "-"
        acts = ",".join(f"{a.action_type}:{item.intensities[i] if i < len(item.intensities) else '-'}" for i, a in enumerate(item.strategy.actions)) or "do_nothing"
        lines.append(
            f"strategy\t{item.strategy.strategy_id}\t{item.strategy.strategy_type}\t"
            f"feasible={feasible}\treject={reason if not feasible else '-'}\t{acts}"
        )
    return "\n".join(lines)
