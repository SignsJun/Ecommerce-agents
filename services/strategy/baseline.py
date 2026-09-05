from dataclasses import dataclass

from agents.decision.materialize import MaterializedStrategy
from domain.diagnosis.report import DiagnosisReport
from domain.strategy.actions import AdjustAdBudget, AdjustPrice, PauseCampaign, ReplenishInventory, UpdateListing
from domain.strategy.models import Strategy

_CAUSE_ACTIONS = {
    "ad_efficiency": {"adjust_ad_budget", "pause_campaign"},
    "campaign_mix": {"adjust_ad_budget", "pause_campaign"},
    "refunds": {"update_listing"},
    "inventory": {"replenish"},
    "excess_inventory": {"adjust_price", "adjust_ad_budget", "pause_campaign"},
    "demand_decline": {"adjust_price"},
}

_REVERSIBILITY = {
    "adjust_ad_budget": 1.0,
    "update_listing": 0.8,
    "pause_campaign": 0.55,
    "adjust_price": 0.35,
    "replenish": 0.2,
}


@dataclass(frozen=True)
class RankResult:
    selected: MaterializedStrategy
    scores: dict[str, float]
    needs_simulation: bool
    approval_required: bool
    confidence: float


def _alignment(strategy: Strategy, report: DiagnosisReport) -> float:
    causes = [c.cause_type for c in report.root_causes]
    if not causes:
        return 0.0 if strategy.actions else 1.0
    types = {a.action_type for a in strategy.actions}
    hit = 0
    for cause in causes:
        if types & _CAUSE_ACTIONS.get(cause, set()):
            hit += 1
    return hit / len(causes)


def _reversibility(strategy: Strategy) -> float:
    if not strategy.actions:
        return 1.0
    return min(_REVERSIBILITY.get(a.action_type, 0.5) for a in strategy.actions)


def _slack(strategy: Strategy) -> float:
    if not strategy.actions:
        return 1.0
    scores = []
    for action in strategy.actions:
        if isinstance(action, AdjustAdBudget):
            scores.append(1.0 - min(1.0, abs(action.change_pct) / 0.30))
        elif isinstance(action, AdjustPrice):
            scores.append(1.0 - min(1.0, abs(action.change_pct) / 0.15))
        else:
            scores.append(0.5)
    return sum(scores) / len(scores)


def score_strategy(item: MaterializedStrategy, report: DiagnosisReport) -> float:
    strategy = item.strategy
    if not strategy.actions:
        if report.status == "insufficient_evidence":
            return 1.0
        return 0.40 if report.status == "partial" else 0.12
    total = 0.45 * _alignment(strategy, report) + 0.35 * _reversibility(strategy) + 0.20 * _slack(strategy)
    if report.status == "partial":
        if strategy.strategy_type == "growth":
            total *= 0.5
        elif strategy.strategy_type == "conservative":
            total += 0.12
    return total


def _high_risk(item: MaterializedStrategy) -> bool:
    for action, intensity in zip(item.strategy.actions, item.intensities):
        if isinstance(action, (AdjustPrice, ReplenishInventory, PauseCampaign)):
            return True
        if isinstance(action, AdjustAdBudget) and (intensity == "strong" or action.change_pct <= -0.20):
            return True
        if isinstance(action, UpdateListing):
            continue
    return False


def rank_without_simulation(items: list[MaterializedStrategy], report: DiagnosisReport) -> RankResult:
    scores = {item.strategy.strategy_id: score_strategy(item, report) for item in items}
    selected = max(items, key=lambda it: scores[it.strategy.strategy_id])
    coupled = len(selected.strategy.actions) > 1
    needs_simulation = report.status == "partial" or coupled
    approval_required = _high_risk(selected)
    conf = report.overall_confidence
    if report.status == "partial":
        conf *= 0.7
    if report.status == "insufficient_evidence":
        conf = min(conf, 0.2) if conf else 0.2
    return RankResult(
        selected=selected,
        scores=scores,
        needs_simulation=needs_simulation,
        approval_required=approval_required,
        confidence=max(0.0, min(1.0, conf)),
    )
