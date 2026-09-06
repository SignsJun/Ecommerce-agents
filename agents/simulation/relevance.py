from agents.simulation.catalog import catalog_kind
from agents.simulation.compare import base_reports, rank_ids, scenario_of
from domain.simulation.report import SimulationReport
from domain.strategy.models import Strategy


def needed_scenarios(strategy: Strategy) -> tuple[str, ...]:
    acts = {a.action_type for a in strategy.actions}
    names: list[str] = []
    if "adjust_ad_budget" in acts:
        names.append("roas_down")
    if "pause_campaign" in acts:
        names.append("demand_down")
    if "update_listing" in acts:
        names.append("listing_worse")
    if "replenish" in acts:
        names.append("supplier_delay")
    if "adjust_price" in acts and "demand_down" not in names:
        names.append("demand_down")
    if not names:
        names.append("demand_down")
    return tuple(names)


def _order(strategies: list[Strategy], selected_id: str | None, reports: list[SimulationReport]) -> list[Strategy]:
    by_id = {s.strategy_id: s for s in strategies}
    ordered: list[Strategy] = []
    seen: set[str] = set()

    def add(sid: str | None) -> None:
        if not sid or sid in seen or sid not in by_id:
            return
        ordered.append(by_id[sid])
        seen.add(sid)

    add(selected_id)
    base = base_reports(reports) or reports
    for sid in rank_ids(base):
        add(sid)
    for item in strategies:
        add(item.strategy_id)
    return ordered


def pending_jobs(
    strategies: list[Strategy],
    selected_id: str | None,
    reports: list[SimulationReport],
    done: set[tuple[str, str]],
    *,
    remaining_stress: int | None = None,
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for item in _order(strategies, selected_id, reports):
        for name in needed_scenarios(item):
            kind = catalog_kind(name)
            if kind is None or (name, item.strategy_id) in done:
                continue
            if remaining_stress is not None and remaining_stress <= 0 and kind == "stress":
                continue
            out.append((name, item.strategy_id))
    return out


def relevant_rows(strategy: Strategy, rows: list[SimulationReport]) -> list[SimulationReport]:
    needed = set(needed_scenarios(strategy))
    return [r for r in rows if scenario_of(r) != "base" and scenario_of(r) in needed]


def has_relevant_stress(strategy: Strategy, reports: list[SimulationReport]) -> bool:
    return any(r.strategy_id == strategy.strategy_id for r in relevant_rows(strategy, reports))
