from agents.simulation.catalog import catalog_kind
from agents.simulation.compare import base_reports, close_top2, rank_ids
from agents.simulation.schema import ExperimentChoice
from domain.simulation.report import SimulationReport
from domain.strategy.actions import ReplenishInventory, UpdateListing
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
) -> ExperimentChoice:
    base = base_reports(reports) or reports
    selected = _selected(selected_id, reports)

    def unused(name: str, sid: str) -> bool:
        return catalog_kind(name) is not None and (name, sid) not in done

    if selected and unused("roas_down", selected):
        return ExperimentChoice(kind="stress", name="roas_down", strategy_ids=[selected])
    if close_top2(base) and len(rank_ids(base)) >= 2:
        runner = rank_ids(base)[1]
        if runner != selected and unused("roas_down", runner):
            return ExperimentChoice(kind="stress", name="roas_down", strategy_ids=[runner])
    listing_ids = [
        s.strategy_id
        for s in strategies
        if any(isinstance(a, UpdateListing) for a in s.actions) and unused("listing_worse", s.strategy_id)
    ]
    if listing_ids:
        return ExperimentChoice(kind="sensitivity", name="listing_worse", strategy_ids=listing_ids[:2])
    replenish_ids = [
        s.strategy_id
        for s in strategies
        if any(isinstance(a, ReplenishInventory) for a in s.actions) and unused("supplier_delay", s.strategy_id)
    ]
    if replenish_ids:
        return ExperimentChoice(kind="stress", name="supplier_delay", strategy_ids=replenish_ids[:2])
    return ExperimentChoice(kind="stop")
