from datetime import datetime
from decimal import Decimal

from domain.base import FrozenModel
from domain.simulation.envelope import RolloutActionRecord
from domain.simulation.models import FailureTrigger, ScenarioResult, SensitivityResult


class SimulationReport(FrozenModel):
    simulation_id: str
    strategy_id: str
    base_snapshot_id: str
    horizon_days: int
    expected_profit: Decimal
    baseline_profit: Decimal
    expected_revenue: Decimal
    profit_p10: Decimal
    profit_p50: Decimal
    profit_p90: Decimal
    stockout_probability: float
    expected_end_inventory: int | None = None
    cash_required: Decimal
    stability_horizon_days: int
    failure_triggers: list[FailureTrigger]
    scenario_results: list[ScenarioResult]
    sensitivity: list[SensitivityResult]
    simulator_version: str
    parameter_version: str
    created_at: datetime
    adaptive: bool = False
    mean_interventions: float = 0.0
    sample_action_trace: list[RolloutActionRecord] = []
