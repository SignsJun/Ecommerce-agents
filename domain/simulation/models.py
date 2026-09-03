from datetime import datetime
from decimal import Decimal
from typing import Literal

from domain.base import FrozenModel
from domain.simulation.scenario import SimulationScenario
from domain.strategy.models import Strategy


class SimulationRequest(FrozenModel):
    simulation_id: str
    base_snapshot_id: str
    strategy: Strategy
    horizon_days: int
    scenario: SimulationScenario
    rollout_count: int = 100
    random_seed: int | None = None


class ConfidenceInterval(FrozenModel):
    low: Decimal
    high: Decimal
    level: float = 0.8


class FailureTrigger(FrozenModel):
    day: int
    constraint: str
    actual_value: float
    threshold: float


class ScenarioResult(FrozenModel):
    scenario_id: str
    expected_profit: Decimal
    profit_p10: Decimal
    profit_p50: Decimal
    profit_p90: Decimal
    stockout_probability: float


class SensitivityResult(FrozenModel):
    parameter: str
    delta_pct: float
    profit_delta: Decimal


class SimulatedBusinessState(FrozenModel):
    simulation_id: str
    simulated_day: int
    source_snapshot_id: str
    expected_sales: float
    expected_inventory: float
    expected_revenue: Decimal
    expected_profit: Decimal
    confidence_interval: ConfidenceInterval | None = None


class SimulationJob(FrozenModel):
    job_id: str
    simulation_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    submitted_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
