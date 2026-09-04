from domain.base import FrozenModel


class InvestigationBudget(FrozenModel):
    max_total_tool_calls: int = 8
    max_calls_per_cause: int = 4
    max_iterations: int = 10


MATERIALITY_ACTIVE = 0.15
MATERIALITY_POSSIBLE = 0.05

DEFAULT_BUDGET = InvestigationBudget()
