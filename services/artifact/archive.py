from __future__ import annotations

from agents.decision.agent import PlanOutcome
from agents.simulation.agent import ExperimentOutcome
from agents.simulation.compare import scenario_of
from domain.decision.case import DecisionCase
from domain.decision.recommendation import StrategyRecommendation
from domain.decision.record import DecisionRecord
from domain.simulation.report import SimulationReport
from repositories.decision import FileDecisionRepository
from services.artifact.provenance import build_graph
from tools.diagnosis.base import ToolContext


def _support(recs: list[StrategyRecommendation], reports: list[SimulationReport]) -> list[StrategyRecommendation]:
    scenes: dict[str, list[str]] = {}
    for row in reports:
        sid = row.strategy_id
        scene = scenario_of(row)
        bucket = scenes.setdefault(sid, [])
        if scene not in bucket:
            bucket.append(scene)
    return [rec.model_copy(update={"simulation_support": scenes.get(rec.strategy_id, [])}) for rec in recs]


def _evidence_ids(plan: PlanOutcome) -> list[str]:
    issue = plan.state.issue
    report = plan.state.diagnosis_report
    ids = list(issue.evidence_ids)
    if report is not None:
        ids.extend(report.key_evidence_ids)
        for cause in report.root_causes:
            ids.extend(cause.supporting_evidence_ids)
        for item in report.cause_assessments:
            ids.extend(item.evidence_ids)
    seen: set[str] = set()
    out: list[str] = []
    for eid in ids:
        if eid in seen:
            continue
        seen.add(eid)
        out.append(eid)
    return out


def assemble_case(
    plan: PlanOutcome,
    ctx: ToolContext,
    *,
    experiment: ExperimentOutcome | None = None,
) -> DecisionCase:
    outcome = experiment.plan if experiment is not None else plan
    state = outcome.state
    snap = ctx.snapshot()
    if snap is None:
        raise ValueError("snapshot missing")
    recs = _support(list(state.final_recommendations), list(state.simulation_reports))
    status = experiment.experiment_status if experiment is not None else state.experiment_status
    record = DecisionRecord(
        decision_id=state.decision_id,
        issue_id=state.issue.issue_id,
        issue_type=state.issue.issue_type,
        snapshot_id=snap.snapshot_id,
        diagnosis_id=state.diagnosis_report.diagnosis_id if state.diagnosis_report else None,
        experiment_status=status,
        recommendations=recs,
        rejected_after_eval=list(state.rejected_after_eval),
        rejected_strategy_ids=list(state.rejected_strategy_ids),
        created_at=state.created_at,
    )
    evidence = ctx.issue_repo.list_evidence(_evidence_ids(outcome))
    graph = build_graph(
        decision_id=state.decision_id,
        snapshot_id=snap.snapshot_id,
        issue=state.issue,
        evidence=evidence,
        diagnosis=state.diagnosis_report,
        strategies=list(state.candidate_strategies),
        validations=list(outcome.validations),
        simulations=list(state.simulation_reports),
        recommendations=recs,
        rejected_after_eval=list(state.rejected_after_eval),
        rejected_strategy_ids=list(state.rejected_strategy_ids),
    )
    return DecisionCase(
        record=record,
        snapshot=snap,
        issue=state.issue,
        evidence=evidence,
        diagnosis=state.diagnosis_report,
        strategies=list(state.candidate_strategies),
        validations=list(outcome.validations),
        simulations=list(state.simulation_reports),
        recommendations=recs,
        provenance=graph,
    )


def archive_decision(
    plan: PlanOutcome,
    ctx: ToolContext,
    repo: FileDecisionRepository,
    *,
    experiment: ExperimentOutcome | None = None,
) -> DecisionCase:
    case = assemble_case(plan, ctx, experiment=experiment)
    artifacts = repo.save(case)
    return case.model_copy(update={"artifacts": artifacts})
