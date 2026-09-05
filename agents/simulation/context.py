import json
from pathlib import Path

from agents.simulation.catalog import CATALOG
from agents.simulation.compare import scenario_of
from domain.simulation.report import SimulationReport
from domain.strategy.models import Strategy

PROMPT_VERSION = "simulation/system_v1"
_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "simulation" / "system_v1.md"


def load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_experiment_context(
    strategies: list[Strategy],
    reports: list[SimulationReport],
    selected_id: str | None,
    remaining_jobs: int,
    remaining_stress: int,
    done: set[tuple[str, str]],
) -> str:
    body = {
        "task": "Choose one ExperimentChoice. kind is stress, sensitivity, or stop. name must be a catalog id. Do not write percents or profits to compute.",
        "selected_strategy_id": selected_id,
        "catalog": CATALOG,
        "remaining_jobs": remaining_jobs,
        "remaining_stress": remaining_stress,
        "done": [f"{n}:{s}" for n, s in sorted(done)],
        "strategies": [
            {
                "strategy_id": s.strategy_id,
                "strategy_type": s.strategy_type,
                "actions": [a.action_type for a in s.actions],
            }
            for s in strategies
        ],
        "reports": [
            {
                "strategy_id": r.strategy_id,
                "scenario": scenario_of(r),
                "expected_profit": str(r.expected_profit),
                "profit_p10": str(r.profit_p10),
            }
            for r in reports
        ],
    }
    return json.dumps(body, ensure_ascii=False, default=str)
