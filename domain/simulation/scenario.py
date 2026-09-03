from datetime import datetime
from typing import Literal

from domain.base import FrozenModel


class SimulationScenario(FrozenModel):
    scenario_id: str
    name: str
    scenario_type: Literal["base", "what_if", "stress", "sensitivity"]
    description: str
    parameter_overrides: dict[str, float] = {}
