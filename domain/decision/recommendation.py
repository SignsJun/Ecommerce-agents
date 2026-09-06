from decimal import Decimal
from typing import Literal

from domain.base import FrozenModel

RecommendationType = Literal["profit", "robust", "balanced", "status_quo"]
ConfidenceBand = Literal["high", "medium", "low"]


class StrategyRecommendation(FrozenModel):
    strategy_id: str
    rank: int
    recommendation_type: RecommendationType
    confidence: ConfidenceBand
    expected_profit: Decimal
    profit_p10: Decimal
    vs_baseline: Decimal
    strengths: list[str] = []
    risks: list[str] = []
    suitable_when: list[str] = []
    simulation_support: list[str] = []
