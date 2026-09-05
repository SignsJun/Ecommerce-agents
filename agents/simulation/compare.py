from decimal import Decimal

from domain.simulation.report import SimulationReport


def scenario_of(report: SimulationReport) -> str:
    if report.scenario_results:
        return report.scenario_results[0].scenario_id
    return "base"


def utility(report: SimulationReport) -> tuple[bool, Decimal]:
    return (report.profit_p10 >= 0, report.expected_profit)


def rank_ids(reports: list[SimulationReport]) -> list[str]:
    best: dict[str, SimulationReport] = {}
    for row in reports:
        cur = best.get(row.strategy_id)
        if cur is None or utility(row) > utility(cur):
            best[row.strategy_id] = row
    return [sid for sid, _ in sorted(best.items(), key=lambda kv: utility(kv[1]), reverse=True)]


def close_top2(reports: list[SimulationReport], ratio: float = 0.10) -> bool:
    ranked = sorted(reports, key=utility, reverse=True)
    if len(ranked) < 2:
        return False
    a = float(ranked[0].expected_profit)
    b = float(ranked[1].expected_profit)
    denom = max(abs(a), abs(b), 1.0)
    return abs(a - b) / denom < ratio


def ranking_flipped(base_reports: list[SimulationReport], other_reports: list[SimulationReport]) -> bool:
    ids = {r.strategy_id for r in other_reports}
    if len(ids) < 2:
        return False
    base_order = [i for i in rank_ids(base_reports) if i in ids]
    other_order = rank_ids(other_reports)
    return bool(base_order and other_order and base_order[0] != other_order[0])


def robust_pick(reports: list[SimulationReport]) -> str | None:
    if not reports:
        return None
    by_id: dict[str, list[SimulationReport]] = {}
    for row in reports:
        by_id.setdefault(row.strategy_id, []).append(row)
    worst = [min(rows, key=lambda r: r.expected_profit) for rows in by_id.values()]
    ranked = rank_ids(worst)
    return ranked[0] if ranked else None


def base_reports(reports: list[SimulationReport]) -> list[SimulationReport]:
    return [r for r in reports if scenario_of(r) == "base"]


def reports_for(reports: list[SimulationReport], scenario_id: str) -> list[SimulationReport]:
    return [r for r in reports if scenario_of(r) == scenario_id]


def has_stress_for(reports: list[SimulationReport], strategy_id: str) -> bool:
    stress = {"roas_down", "demand_down", "supplier_delay"}
    return any(r.strategy_id == strategy_id and scenario_of(r) in stress for r in reports)
