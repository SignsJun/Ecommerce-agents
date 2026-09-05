from datetime import datetime
from decimal import Decimal

from agents.llm.client import LLMClient
from agents.rollout.agent import RolloutPolicyAgent
from domain.business.snapshot import BusinessStateSnapshot
from domain.common import BusinessPolicyConfig
from domain.simulation.report import SimulationReport
from domain.simulation.scenario import SimulationScenario
from domain.strategy.models import Strategy
from services.simulation.params import SimulatorParameterSet
from services.simulation.world import make_request, rollout

DEFAULT_ROLLOUTS = 32


def _sku_id(strategy: Strategy, fallback: str) -> str:
    for action in strategy.actions:
        sku = getattr(action, "sku_id", None)
        if sku:
            return sku
    return fallback


def simulate_strategies(
    snapshot: BusinessStateSnapshot,
    policy: BusinessPolicyConfig,
    strategies: list[Strategy],
    sku_id: str,
    *,
    horizon: int | None = None,
    seed: int = 42,
    n: int = DEFAULT_ROLLOUTS,
    params: SimulatorParameterSet | None = None,
    now: datetime | None = None,
    open_loop: bool = False,
    llm: LLMClient | None = None,
    scenario: SimulationScenario | None = None,
) -> list[SimulationReport]:
    params = params or SimulatorParameterSet()
    horizon = horizon or next((s.horizon_days for s in strategies if s.horizon_days), policy.impact_horizon_days)
    agent = None if open_loop else RolloutPolicyAgent(llm, roas_min=policy.roas_min, cover_min=float(policy.stockout_safety_days))
    decide = None if agent is None else agent.decide
    noop = next((s for s in strategies if not s.actions), None)
    baseline = Decimal("0.00")
    cached: dict[str, SimulationReport] = {}
    if noop is not None:
        rep = rollout(
            snapshot,
            policy,
            make_request(noop, snapshot.snapshot_id, horizon=horizon, n=n, seed=seed, scenario=scenario),
            _sku_id(noop, sku_id),
            params=params,
            now=now,
            adaptive=not open_loop,
            decide=decide,
        )
        baseline = rep.expected_profit
        cached[noop.strategy_id] = rep.model_copy(update={"baseline_profit": baseline})
    out: list[SimulationReport] = []
    for strategy in strategies:
        if strategy.strategy_id in cached:
            out.append(cached[strategy.strategy_id])
            continue
        sid = _sku_id(strategy, sku_id)
        req = make_request(strategy, snapshot.snapshot_id, horizon=horizon, n=n, seed=seed, scenario=scenario)
        out.append(
            rollout(
                snapshot,
                policy,
                req,
                sid,
                params=params,
                now=now,
                baseline_profit=baseline,
                adaptive=not open_loop,
                decide=decide,
            )
        )
    return out
