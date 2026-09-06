from __future__ import annotations

from dataclasses import dataclass, replace

from agents.decision.agent import PlanOutcome, attach_simulations
from agents.llm.client import LLMClient, LLMUnavailable
from agents.simulation.catalog import catalog_kind, scenario_jobs
from agents.simulation.compare import (
    base_reports,
    ranking_flipped,
    scenario_of,
)
from agents.simulation.context import PROMPT_VERSION, build_experiment_context, load_system_prompt
from agents.simulation.evaluate import evaluate_recommendations, format_recommendation_set
from agents.simulation.planner import rule_plan
from agents.simulation.relevance import pending_jobs
from agents.simulation.schema import ExperimentChoice
from domain.decision.recommendation import StrategyRecommendation
from domain.enums import DecisionPhase
from services.simulation.params import SimulatorParameterSet
from services.simulation.runner import simulate_strategies
from tools.diagnosis.base import ToolContext

AGENT_VERSION = "simulation-v1"
MAX_JOBS = 20
MAX_STRESS = 4


@dataclass
class ExperimentOutcome:
    plan: PlanOutcome
    experiment_status: str
    recommendations: list[StrategyRecommendation]
    jobs_used: int
    stress_jobs: int
    trace: list[str]
    prompt_version: str = PROMPT_VERSION


def _flipped(reports) -> bool:
    base = base_reports(reports) or reports
    by_scene: dict[str, list] = {}
    for row in reports:
        sc = scenario_of(row)
        if sc == "base":
            continue
        by_scene.setdefault(sc, []).append(row)
    return any(ranking_flipped(base, rows) for rows in by_scene.values())


def _has_row(reports, sid: str, scene: str) -> bool:
    return any(r.strategy_id == sid and scenario_of(r) == scene for r in reports)


def _pick(
    llm: LLMClient | None,
    strategies,
    reports,
    selected_id,
    done: set[tuple[str, str]],
    remaining_jobs: int,
    remaining_stress: int,
) -> ExperimentChoice:
    fallback = rule_plan(reports, strategies, selected_id, done, remaining_stress=remaining_stress)
    allowed = pending_jobs(strategies, selected_id, reports, done, remaining_stress=remaining_stress)
    if llm is None:
        return fallback
    try:
        choice = llm.complete(
            load_system_prompt(),
            build_experiment_context(
                strategies, reports, selected_id, remaining_jobs, remaining_stress, done, allowed
            ),
            ExperimentChoice,
        )
    except LLMUnavailable:
        return fallback
    if choice.kind == "stop":
        return fallback if allowed else choice
    allowed_set = set(allowed)
    ids = [i for i in choice.strategy_ids if (choice.name, i) in allowed_set]
    kind = catalog_kind(choice.name)
    if kind is None or not ids:
        return fallback
    return ExperimentChoice(kind=kind, name=choice.name, strategy_ids=ids[:1])


def _coverage_status(strategies, selected_id, reports, done) -> str:
    leftover = pending_jobs(strategies, selected_id, reports, done)
    return "sufficient" if not leftover else "budget_exhausted"


def run_experiments(
    outcome: PlanOutcome,
    ctx: ToolContext,
    llm: LLMClient | None = None,
    *,
    seed: int = 42,
    n: int = 32,
    open_loop: bool = False,
    max_jobs: int = MAX_JOBS,
    max_stress: int = MAX_STRESS,
) -> ExperimentOutcome:
    selected = outcome.state.initial_preferred_strategy_id
    if not outcome.state.simulation_reports:
        outcome = attach_simulations(outcome, ctx, seed=seed, n=n, open_loop=open_loop, llm=llm)
    reports = list(outcome.state.simulation_reports)
    jobs_used = max(len(base_reports(reports)), 1)
    stress_jobs = 0
    done: set[tuple[str, str]] = set()
    strategies = list(outcome.state.candidate_strategies)
    trace: list[str] = []
    status: str | None = None
    params = SimulatorParameterSet()
    snaps = ctx.snapshot()
    sku_id = outcome.state.issue.entity_id
    noop = next((s for s in strategies if not s.actions), None)
    skips = 0
    while True:
        if _flipped(reports):
            status = "uncertain"
            trace.append("stop\tuncertain")
            break
        if jobs_used >= max_jobs:
            status = "budget_exhausted"
            trace.append("stop\tbudget")
            break
        remaining_stress = max_stress - stress_jobs
        allowed = pending_jobs(strategies, selected, reports, done, remaining_stress=remaining_stress)
        if not allowed:
            status = _coverage_status(strategies, selected, reports, done)
            trace.append(f"stop\t{status}")
            break
        choice = _pick(llm, strategies, reports, selected, done, max_jobs - jobs_used, remaining_stress)
        if choice.kind == "stop":
            status = _coverage_status(strategies, selected, reports, done)
            trace.append(f"stop\t{status}")
            break
        kind = catalog_kind(choice.name)
        scenes = scenario_jobs(choice.name, params)
        ids = [i for i in choice.strategy_ids if (choice.name, i) not in done]
        if kind is None or not scenes or not ids:
            skips += 1
            trace.append(f"skip\t{choice.name}")
            if skips > 4:
                status = _coverage_status(strategies, selected, reports, done)
                break
            continue
        skips = 0
        for sid in ids:
            strat = next((s for s in strategies if s.strategy_id == sid), None)
            if strat is None:
                continue
            if jobs_used >= max_jobs:
                break
            if kind == "stress" and stress_jobs >= max_stress:
                break
            for scene in scenes:
                if jobs_used >= max_jobs:
                    break
                if kind == "stress" and stress_jobs >= max_stress:
                    break
                batch = [strat]
                if noop is not None and strat.strategy_id != noop.strategy_id:
                    batch = [noop, strat]
                rows = simulate_strategies(
                    snaps,
                    ctx.policy,
                    batch,
                    sku_id,
                    seed=seed,
                    n=n,
                    now=ctx.now,
                    open_loop=open_loop,
                    llm=llm,
                    scenario=scene,
                )
                for row in rows:
                    sc = scenario_of(row)
                    if _has_row(reports, row.strategy_id, sc):
                        continue
                    reports.append(row)
                    if row.strategy_id != sid:
                        continue
                    jobs_used += 1
                    if kind == "stress":
                        stress_jobs += 1
                    trace.append(f"job\t{choice.name}\t{sid}\t{sc}")
            done.add((choice.name, sid))
    if status is None:
        status = _coverage_status(strategies, selected, reports, done)
    recs, rejected_eval = evaluate_recommendations(reports, strategies, status)
    state = outcome.state.model_copy(
        update={
            "simulation_reports": reports,
            "phase": DecisionPhase.EVALUATING,
            "updated_at": ctx.now,
            "initial_preferred_strategy_id": selected,
            "experiment_status": status,
            "final_recommendations": recs,
            "rejected_after_eval": rejected_eval,
        }
    )
    planned = replace(outcome, state=state)
    return ExperimentOutcome(
        plan=planned,
        experiment_status=status,
        recommendations=recs,
        jobs_used=jobs_used,
        stress_jobs=stress_jobs,
        trace=trace,
    )


def format_experiment_trace(outcome: ExperimentOutcome) -> str:
    lines = [
        f"experiment\tstatus={outcome.experiment_status}\tjobs={outcome.jobs_used}\t"
        f"stress={outcome.stress_jobs}\tinitial={outcome.plan.state.initial_preferred_strategy_id}"
    ]
    lines.extend(outcome.trace)
    lines.append(
        format_recommendation_set(
            outcome.plan.state.final_recommendations,
            outcome.plan.state.rejected_after_eval,
        )
    )
    return "\n".join(lines)
