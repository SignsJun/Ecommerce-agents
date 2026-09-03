from typing import Literal

from domain.base import FrozenModel
from domain.enums import DataProvenance
from domain.strategy.actions import BusinessAction


class Assumption(FrozenModel):
    assumption_id: str
    description: str
    parameter: str | None = None
    assumed_value: float | None = None
    confidence: float
    source: str
    provenance: DataProvenance


class Strategy(FrozenModel):
    strategy_id: str
    issue_id: str
    name: str
    strategy_type: Literal["conservative", "balanced", "growth", "custom"]
    objective: str
    actions: list[BusinessAction]
    assumptions: list[Assumption]
    horizon_days: int
    based_on_snapshot_id: str
    based_on_state_version: int
    status: str
