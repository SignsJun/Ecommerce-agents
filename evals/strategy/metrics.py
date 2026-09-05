from agents.decision.agent import PlanOutcome
from domain.strategy.validation import StrategyValidationResult


def feasibility_rate(outcome: PlanOutcome) -> float:
    generated = [v for v in outcome.validations if v.strategy_id != "ST_do_nothing"]
    if not generated:
        return 1.0
    return sum(1 for v in generated if v.feasible) / len(generated)


def constraint_violation_rate(outcome: PlanOutcome) -> float:
    generated = [v for v in outcome.validations if v.strategy_id != "ST_do_nothing"]
    if not generated:
        return 0.0
    return sum(1 for v in generated if not v.feasible) / len(generated)


def strategy_diversity(outcome: PlanOutcome) -> int:
    return len({s.strategy_type for s in outcome.state.candidate_strategies})


def unknown_target_rejected(validations: list[StrategyValidationResult]) -> bool:
    return any(any(e.code == "UNKNOWN_TARGET_ID" for e in v.errors) and not v.feasible for v in validations)
