from typing import Literal

from domain.base import FrozenModel
from domain.strategy.models import Strategy


class ValidationIssue(FrozenModel):
    code: str
    field: str | None = None
    message: str
    severity: Literal["error", "warning"]


class StrategyValidationResult(FrozenModel):
    strategy_id: str
    feasible: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    normalized_strategy: Strategy | None = None
