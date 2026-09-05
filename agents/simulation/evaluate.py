from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from agents.simulation.compare import base_reports, has_stress_for, ranking_flipped, scenario_of
from domain.decision.recommendation import StrategyRecommendation
from domain.simulation.report import SimulationReport
from domain.strategy.models import Strategy

_NOOP = "ST_do_nothing"


@dataclass
class _Agg:
    strategy_id: str
    noop: bool
    base: SimulationReport
    worst_expected: Decimal
    min_p10: Decimal
    stockout: float
    cash: Decimal
    stability: int
    vs_baseline: Decimal
    fragile: bool


def _is_noop(sid: str, strategies: list[Strategy]) -> bool:
    if sid == _NOOP:
        return True
    item = next((s for s in strategies if s.strategy_id == sid), None)
    return item is not None and not item.actions


def _by_strategy(reports: list[SimulationReport]) -> dict[str, list[SimulationReport]]:
    out: dict[str, list[SimulationReport]] = {}
    for row in reports:
        out.setdefault(row.strategy_id, []).append(row)
    return out


def _agg(sid: str, rows: list[SimulationReport], strategies: list[Strategy], baseline: Decimal) -> _Agg | None:
    bases = [r for r in rows if scenario_of(r) == "base"] or rows
    base = max(bases, key=lambda r: r.expected_profit)
    worst = min(rows, key=lambda r: r.expected_profit)
    min_p10 = min(r.profit_p10 for r in rows)
    stress = [r for r in rows if scenario_of(r) != "base"]
    fragile = bool(stress) and any(r.expected_profit + Decimal("1") < base.expected_profit for r in stress)
    return _Agg(
        strategy_id=sid,
        noop=_is_noop(sid, strategies),
        base=base,
        worst_expected=worst.expected_profit,
        min_p10=min_p10,
        stockout=base.stockout_probability,
        cash=base.cash_required,
        stability=base.stability_horizon_days,
        vs_baseline=base.expected_profit - baseline,
        fragile=fragile,
    )


def _ops_better(a: _Agg, b: _Agg) -> bool:
    return a.stockout <= b.stockout - 0.05 or a.stability >= b.stability + 3


def _worse_than_baseline(a: _Agg, noop: _Agg) -> bool:
    if a.noop:
        return False
    if a.base.expected_profit < noop.base.expected_profit and a.min_p10 < noop.min_p10:
        return not _ops_better(a, noop)
    return False


def _risk_better(a: _Agg, b: _Agg) -> bool:
    return a.stockout < b.stockout - 1e-12 or a.cash < b.cash or a.stability > b.stability


def _profit_gap(a: _Agg, b: _Agg) -> float:
    denom = max(abs(float(b.base.expected_profit)), 1.0)
    return float(a.base.expected_profit - b.base.expected_profit) / denom


def _dominates(a: _Agg, b: _Agg) -> bool:
    if b.noop:
        return False
    profit_ge = a.base.expected_profit >= b.base.expected_profit and a.min_p10 >= b.min_p10
    if not profit_ge:
        return False
    if _risk_better(a, b):
        return True
    risk_not_worse = a.stockout <= b.stockout and a.cash <= b.cash and a.stability >= b.stability
    return risk_not_worse and _profit_gap(a, b) >= 0.10


def _confidence(reports: list[SimulationReport], status: str | None, survivors: list[_Agg]) -> str:
    if status == "uncertain":
        return "low"
    base = base_reports(reports) or reports
    others = [r for r in reports if scenario_of(r) != "base"]
    if others and ranking_flipped(base, others):
        return "low"
    if any(has_stress_for(reports, a.strategy_id) for a in survivors):
        return "high"
    return "medium"


def _labels(item: _Agg, rec_type: str) -> tuple[list[str], list[str], list[str]]:
    strengths: list[str] = []
    risks: list[str] = []
    if item.vs_baseline > 0:
        strengths.append("vs_baseline_positive")
    elif item.vs_baseline < 0:
        risks.append("vs_baseline_negative")
    if item.min_p10 >= 0:
        strengths.append("p10_non_negative")
    else:
        risks.append("p10_negative")
    if item.stockout <= 0.1:
        strengths.append("low_stockout")
    elif item.stockout >= 0.3:
        risks.append("high_stockout")
    if item.cash == 0:
        strengths.append("no_cash_outlay")
    elif item.cash > 0:
        risks.append("cash_required")
    if item.fragile:
        risks.append("fragile_under_stress")
    else:
        strengths.append("stable_under_stress")
    suitable = {
        "profit": ["prefer_profit"],
        "robust": ["prefer_stability"],
        "status_quo": ["prefer_no_execution"],
        "balanced": ["prefer_balance"],
    }[rec_type]
    return strengths, risks, suitable


def _pick(survivors: list[_Agg]) -> list[tuple[_Agg, str]]:
    if not survivors:
        return []
    used: set[str] = set()
    picked: list[tuple[_Agg, str]] = []
    noop = next((a for a in survivors if a.noop), None)
    profit = max(survivors, key=lambda a: a.base.expected_profit)
    robust = max(survivors, key=lambda a: (a.worst_expected, a.min_p10))
    if noop is not None:
        picked.append((noop, "status_quo"))
        used.add(noop.strategy_id)
    if profit.strategy_id not in used:
        picked.append((profit, "profit"))
        used.add(profit.strategy_id)
    if robust.strategy_id not in used:
        picked.append((robust, "robust"))
        used.add(robust.strategy_id)
    rest = sorted(survivors, key=lambda a: (a.worst_expected, a.base.expected_profit), reverse=True)
    for item in rest:
        if len(picked) >= 3:
            break
        if item.strategy_id in used:
            continue
        picked.append((item, "balanced"))
        used.add(item.strategy_id)
    return picked[:3]


def evaluate_recommendations(
    reports: list[SimulationReport],
    strategies: list[Strategy],
    experiment_status: str | None = None,
) -> tuple[list[StrategyRecommendation], list[str]]:
    if not reports:
        return [], []
    grouped = _by_strategy(reports)
    noop_rows = grouped.get(_NOOP) or next((rows for sid, rows in grouped.items() if _is_noop(sid, strategies)), None)
    baseline = Decimal("0")
    if noop_rows:
        nb = [r for r in noop_rows if scenario_of(r) == "base"] or noop_rows
        baseline = max(nb, key=lambda r: r.expected_profit).expected_profit
    aggs = []
    for sid, rows in grouped.items():
        item = _agg(sid, rows, strategies, baseline)
        if item is not None:
            aggs.append(item)
    noop = next((a for a in aggs if a.noop), None)
    rejected: list[str] = []
    kept: list[_Agg] = []
    for item in aggs:
        if noop is not None and _worse_than_baseline(item, noop):
            rejected.append(item.strategy_id)
            continue
        kept.append(item)
    survivors: list[_Agg] = []
    for item in kept:
        if any(_dominates(other, item) for other in kept if other.strategy_id != item.strategy_id):
            rejected.append(item.strategy_id)
            continue
        survivors.append(item)
    if not survivors and noop is not None and noop.strategy_id not in rejected:
        survivors = [noop]
    elif not survivors and kept:
        survivors = [max(kept, key=lambda a: (a.worst_expected, a.base.expected_profit))]
    picked = _pick(survivors)
    picked.sort(key=lambda pair: (pair[0].worst_expected, pair[0].base.expected_profit), reverse=True)
    band = _confidence(reports, experiment_status, [p[0] for p in picked])
    recs: list[StrategyRecommendation] = []
    for rank, (item, rec_type) in enumerate(picked, start=1):
        strengths, risks, suitable = _labels(item, rec_type)
        recs.append(
            StrategyRecommendation(
                strategy_id=item.strategy_id,
                rank=rank,
                recommendation_type=rec_type,
                confidence=band,
                expected_profit=item.base.expected_profit,
                profit_p10=item.min_p10,
                vs_baseline=item.vs_baseline,
                strengths=strengths,
                risks=risks,
                suitable_when=suitable,
            )
        )
    return recs, rejected


def format_recommendation_set(
    recs: list[StrategyRecommendation],
    rejected: list[str] | None = None,
) -> str:
    if not recs:
        return "recommend\tnone"
    lines = [f"recommend\tn={len(recs)}"]
    for rec in recs:
        lines.append(
            f"recommend\trank={rec.rank}\ttype={rec.recommendation_type}\tconfidence={rec.confidence}\t"
            f"id={rec.strategy_id}\tprofit={rec.expected_profit}\tp10={rec.profit_p10}\tvs_base={rec.vs_baseline}"
        )
        lines.append(
            f"  strengths={','.join(rec.strengths) or '-'}\trisks={','.join(rec.risks) or '-'}\t"
            f"suitable={','.join(rec.suitable_when) or '-'}"
        )
    for sid in rejected or []:
        lines.append(f"rejected\t{sid}")
    return "\n".join(lines)
