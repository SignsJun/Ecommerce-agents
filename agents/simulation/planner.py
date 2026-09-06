from agents.simulation.catalog import catalog_kind
from agents.simulation.compare import base_reports, rank_ids
from agents.simulation.relevance import pending_jobs
from agents.simulation.schema import ExperimentChoice
from domain.simulation.report import SimulationReport
from domain.strategy.models import Strategy


def _selected(selected_id: str | None, reports: list[SimulationReport]) -> str | None:
    base = base_reports(reports) or reports
    if selected_id and selected_id != "ST_do_nothing":
        return selected_id
    ordered = [sid for sid in rank_ids(base) if sid != "ST_do_nothing"]
    return ordered[0] if ordered else selected_id


def rule_plan(
    reports: list[SimulationReport],
    strategies: list[Strategy],
    selected_id: str | None,
    done: set[tuple[str, str]],
    *,
    remaining_stress: int | None = None,
) -> ExperimentChoice:
    jobs = pending_jobs(strategies, selected_id, reports, done, remaining_stress=remaining_stress)
    if not jobs:
        return ExperimentChoice(kind="stop")
    name, sid = jobs[0]
    kind = catalog_kind(name) or "stop"
    return ExperimentChoice(kind=kind, name=name, strategy_ids=[sid])
