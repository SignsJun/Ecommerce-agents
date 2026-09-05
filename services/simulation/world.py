from __future__ import annotations

import math
import random
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from domain.business.snapshot import BusinessStateSnapshot
from domain.common import BusinessPolicyConfig
from domain.simulation.envelope import RolloutActionRecord
from domain.simulation.models import FailureTrigger, ScenarioResult, SimulatedBusinessState, SimulationRequest
from domain.simulation.report import SimulationReport
from domain.simulation.scenario import SimulationScenario
from domain.strategy.actions import AdjustAdBudget, AdjustPrice, PauseCampaign, ReplenishInventory, UpdateListing
from domain.strategy.models import Strategy
from services.profit.engine import as_money, compute_cogs, compute_profit, compute_refund_loss, profit_margin
from services.simulation.params import PARAMETER_VERSION, SIMULATOR_VERSION, SimulatorParameterSet, with_overrides


def _money(value: Decimal | float | int) -> Decimal:
    return as_money(Decimal(str(value))).quantize(Decimal("0.01"))


def _pct(values: list[Decimal], q: float) -> Decimal:
    xs = sorted(values)
    if not xs:
        return Decimal("0.00")
    idx = int(round(q * (len(xs) - 1)))
    return xs[max(0, min(idx, len(xs) - 1))]


@dataclass
class CampaignSim:
    campaign_id: str
    daily_budget: Decimal
    weight: float
    paused: bool = False
    change_pct: float = 0.0


@dataclass
class WorldState:
    sku_id: str
    snapshot_id: str
    inventory: int
    price: Decimal
    unit_cost: Decimal
    refund_rate: float
    cash: Decimal
    lead_time: int
    base_daily_demand: float
    paid_share: float
    campaigns: dict[str, CampaignSim]
    incoming: list[tuple[int, int]] = field(default_factory=list)
    listing: bool = False
    cash_required: Decimal = Decimal("0.00")
    cumulative_ad: Decimal = Decimal("0.00")
    price_change: float = 0.0
    last_margin: float | None = None
    last_roas: float | None = None
    last_sales: int = 0
    applied_refund_rate: float = 0.0

    def clone(self) -> WorldState:
        return deepcopy(self)


def world_from_snapshot(snapshot: BusinessStateSnapshot, sku_id: str, policy: BusinessPolicyConfig) -> WorldState:
    sku = snapshot.skus[sku_id]
    camps = [c for c in snapshot.campaigns.values() if c.sku_id == sku_id]
    spend_total = sum((c.spend_7d for c in camps), Decimal("0"))
    campaigns: dict[str, CampaignSim] = {}
    for camp in camps:
        weight = float(camp.spend_7d / spend_total) if spend_total > 0 else 1.0 / max(len(camps), 1)
        campaigns[camp.campaign_id] = CampaignSim(
            campaign_id=camp.campaign_id,
            daily_budget=(camp.daily_budget if camp.daily_budget > 0 else camp.spend_7d / Decimal("7")),
            weight=weight,
            paused=camp.status == "paused",
        )
    return WorldState(
        sku_id=sku_id,
        snapshot_id=snapshot.snapshot_id,
        inventory=sku.inventory_available,
        price=sku.price,
        unit_cost=sku.unit_cost,
        refund_rate=sku.refund_rate_7d,
        cash=snapshot.store.cash_balance,
        lead_time=max(sku.lead_time_days, 1),
        base_daily_demand=max(sku.units_sold_7d / 7, 0.01),
        paid_share=policy.paid_revenue_share,
        campaigns=campaigns,
        applied_refund_rate=sku.refund_rate_7d,
    )


def apply_action(
    state: WorldState,
    action,
    *,
    current_day: int = 0,
    incremental_ad: bool = False,
    ad_floor: float = -0.30,
) -> bool:
    if isinstance(action, AdjustAdBudget):
        camp = state.campaigns.get(action.campaign_id)
        if camp is None:
            return False
        if incremental_ad:
            nxt = camp.change_pct + action.change_pct
            nxt = max(ad_floor, min(0.30, nxt))
            if abs(nxt - camp.change_pct) < 1e-12:
                return False
            camp.change_pct = nxt
        else:
            camp.change_pct = action.change_pct
        return True
    if isinstance(action, PauseCampaign):
        camp = state.campaigns.get(action.campaign_id)
        if camp is None or camp.paused:
            return False
        camp.paused = True
        return True
    if isinstance(action, ReplenishInventory):
        if action.sku_id != state.sku_id:
            return False
        cost = _money(state.unit_cost * action.quantity)
        state.cash -= cost
        state.cash_required += cost
        state.incoming.append((current_day + state.lead_time, action.quantity))
        return True
    if isinstance(action, AdjustPrice):
        if action.sku_id != state.sku_id:
            return False
        state.price = _money(state.price * Decimal(str(1 + action.change_pct)))
        state.price_change += action.change_pct
        return True
    if isinstance(action, UpdateListing):
        if action.sku_id != state.sku_id or state.listing:
            return False
        state.listing = True
        return True
    return False


def apply_strategy(state: WorldState, strategy: Strategy, current_day: int = 0) -> None:
    for action in strategy.actions:
        apply_action(state, action, current_day=current_day, incremental_ad=False)


def _demand(state: WorldState, params: SimulatorParameterSet, rng: random.Random) -> float:
    organic = state.base_daily_demand * (1 - state.paid_share)
    paid = state.base_daily_demand * state.paid_share
    if state.campaigns:
        paid_out = 0.0
        for camp in state.campaigns.values():
            if camp.paused:
                continue
            paid_out += paid * camp.weight * (1 + camp.change_pct * params.eta_ad)
        paid = paid_out
    demand = (organic + paid) * (1 + state.price_change * params.eta_price) * params.demand_mult
    if params.demand_sigma <= 0:
        return max(demand, 0.0)
    z = rng.gauss(0.0, params.demand_sigma)
    noise = math.exp(z - 0.5 * params.demand_sigma**2)
    return max(demand * noise, 0.0)


def _ad_spend(state: WorldState) -> Decimal:
    if not state.campaigns:
        return Decimal("0.00")
    total = Decimal("0.00")
    for camp in state.campaigns.values():
        if camp.paused:
            continue
        total += _money(camp.daily_budget * Decimal(str(1 + camp.change_pct)))
    return total


def _check_stability(
    state: WorldState,
    policy: BusinessPolicyConfig,
    params: SimulatorParameterSet,
    day: int,
    sales: int,
    margin: float,
    roas: float | None,
) -> FailureTrigger | None:
    cover = 999.0 if sales <= 0 else state.inventory / sales
    if cover < policy.stockout_safety_days:
        return FailureTrigger(day=day, constraint="inventory_cover", actual_value=cover, threshold=float(policy.stockout_safety_days))
    if state.cash < 0:
        return FailureTrigger(day=day, constraint="cash", actual_value=float(state.cash), threshold=0.0)
    if margin < params.min_margin:
        return FailureTrigger(day=day, constraint="profit_margin", actual_value=margin, threshold=params.min_margin)
    if roas is not None and roas < policy.roas_min:
        return FailureTrigger(day=day, constraint="roas", actual_value=roas, threshold=policy.roas_min)
    return None


def step(
    state: WorldState,
    day: int,
    params: SimulatorParameterSet,
    policy: BusinessPolicyConfig,
    rng: random.Random,
    simulation_id: str,
) -> tuple[SimulatedBusinessState, FailureTrigger | None, bool]:
    arrived = 0
    remaining: list[tuple[int, int]] = []
    for arrive_day, qty in state.incoming:
        if arrive_day <= day:
            arrived += qty
        else:
            remaining.append((arrive_day, qty))
    state.incoming = remaining
    state.inventory += arrived
    demand = _demand(state, params, rng)
    sales = min(int(demand), state.inventory)
    stockout = demand > state.inventory and state.inventory == sales
    if demand >= 1 and state.inventory == 0:
        stockout = True
    state.inventory -= sales
    refund_rate = state.refund_rate * (params.listing_refund_factor if state.listing else 1.0)
    revenue = _money(state.price * sales)
    cogs = compute_cogs(state.unit_cost, sales)
    ad = _ad_spend(state)
    state.cumulative_ad += ad
    refund = compute_refund_loss(revenue, refund_rate)
    profit = _money(compute_profit(revenue, cogs, ad, refund, policy))
    state.cash += profit
    margin = profit_margin(profit, revenue)
    roas = float(revenue * Decimal(str(state.paid_share)) / ad) if ad > 0 else None
    state.last_margin = margin
    state.last_roas = roas
    state.last_sales = sales
    state.applied_refund_rate = refund_rate
    trigger = _check_stability(state, policy, params, day, max(sales, 1) if demand > 0 else 0, margin, roas)
    sim = SimulatedBusinessState(
        simulation_id=simulation_id,
        simulated_day=day,
        source_snapshot_id=state.snapshot_id,
        expected_sales=float(sales),
        expected_inventory=float(state.inventory),
        expected_revenue=revenue,
        expected_profit=profit,
    )
    return sim, trigger, stockout or state.inventory == 0


@dataclass
class PathResult:
    profit: Decimal
    revenue: Decimal
    end_inv: int
    stockout: bool
    triggers: list[FailureTrigger]
    stability: int
    interventions: int
    trace: list[RolloutActionRecord]


def _accumulate(
    state: WorldState,
    params: SimulatorParameterSet,
    policy: BusinessPolicyConfig,
    horizon: int,
    rng: random.Random,
    simulation_id: str,
    on_day: Callable[[int, WorldState], RolloutActionRecord | None] | None,
) -> PathResult:
    profit = Decimal("0.00")
    revenue = Decimal("0.00")
    stockout = False
    triggers: list[FailureTrigger] = []
    stability = horizon
    interventions = 0
    trace: list[RolloutActionRecord] = []
    for day in range(1, horizon + 1):
        if on_day is not None:
            rec = on_day(day, state)
            if rec is not None:
                trace.append(rec)
                if rec.accepted:
                    interventions += 1
        daily, trigger, out = step(state, day, params, policy, rng, simulation_id)
        profit += daily.expected_profit
        revenue += daily.expected_revenue
        if out:
            stockout = True
        if trigger is not None and not triggers:
            triggers.append(trigger)
            stability = max(day - 1, 0)
    return PathResult(profit, revenue, state.inventory, stockout, triggers, stability, interventions, trace)


def open_loop_path(
    base: WorldState,
    strategy: Strategy,
    params: SimulatorParameterSet,
    policy: BusinessPolicyConfig,
    horizon: int,
    rng: random.Random,
    simulation_id: str,
) -> PathResult:
    state = base.clone()
    apply_strategy(state, strategy)
    return _accumulate(state, params, policy, horizon, rng, simulation_id, None)


def adaptive_path(
    base: WorldState,
    strategy: Strategy,
    params: SimulatorParameterSet,
    policy: BusinessPolicyConfig,
    horizon: int,
    rng: random.Random,
    simulation_id: str,
    decide: Callable,
) -> PathResult:
    from services.simulation.checkpoints import is_checkpoint
    from services.simulation.envelope import build_envelope
    from services.simulation.intervene import materialize_decision, validate_intervention
    from services.simulation.observe import observe

    state = base.clone()
    apply_strategy(state, strategy)
    envelope = build_envelope(strategy, policy)
    last_day: int | None = None
    remaining = envelope.max_interventions
    prev: list[str] = []
    baseline_refund = state.refund_rate

    def on_day(day: int, world: WorldState) -> RolloutActionRecord | None:
        nonlocal last_day, remaining
        obs = observe(world, envelope, day, last_day, remaining, tuple(prev))
        if not is_checkpoint(day, obs, policy, params, envelope, baseline_refund):
            return None
        decision = decide(obs)
        action_name = getattr(decision, "action", "noop") or "noop"
        target_id = getattr(decision, "target_id", None)
        intensity = getattr(decision, "intensity", None)
        accepted = False
        if action_name != "noop":
            drafted = materialize_decision(action_name, target_id, intensity, world, policy)
            if drafted is not None and validate_intervention(drafted, world, envelope, obs):
                ok = apply_action(
                    world,
                    drafted,
                    current_day=day,
                    incremental_ad=True,
                    ad_floor=envelope.ad_change_min,
                )
                if ok:
                    accepted = True
                    remaining -= 1
                    last_day = day
                    prev.append(action_name)
        return RolloutActionRecord(
            day=day,
            action=action_name,
            target_id=target_id,
            intensity=intensity,
            accepted=accepted,
        )

    return _accumulate(state, params, policy, horizon, rng, simulation_id, on_day)


def _one_path(
    base: WorldState,
    strategy: Strategy,
    params: SimulatorParameterSet,
    policy: BusinessPolicyConfig,
    horizon: int,
    rng: random.Random,
    simulation_id: str,
) -> tuple[Decimal, Decimal, int, bool, list[FailureTrigger], int]:
    row = open_loop_path(base, strategy, params, policy, horizon, rng, simulation_id)
    return row.profit, row.revenue, row.end_inv, row.stockout, row.triggers, row.stability


def rollout(
    snapshot: BusinessStateSnapshot,
    policy: BusinessPolicyConfig,
    request: SimulationRequest,
    sku_id: str,
    *,
    params: SimulatorParameterSet | None = None,
    now: datetime | None = None,
    baseline_profit: Decimal | None = None,
    adaptive: bool = False,
    decide: Callable | None = None,
) -> SimulationReport:
    params = params or SimulatorParameterSet()
    params = with_overrides(params, request.scenario.parameter_overrides)
    seed = request.random_seed if request.random_seed is not None else 0
    n = max(request.rollout_count, 1)
    base = world_from_snapshot(snapshot, sku_id, policy)
    base.lead_time = max(base.lead_time + int(params.lead_time_extra), 1)
    profits: list[Decimal] = []
    revenues: list[Decimal] = []
    ends: list[int] = []
    stockouts = 0
    stabilities: list[int] = []
    triggers: list[FailureTrigger] = []
    interventions: list[int] = []
    sample_trace: list[RolloutActionRecord] = []
    cash_required = Decimal("0.00")
    probe = base.clone()
    apply_strategy(probe, request.strategy)
    cash_required = probe.cash_required
    use_adaptive = adaptive and decide is not None
    for i in range(n):
        rng = random.Random(seed + i)
        if use_adaptive:
            row = adaptive_path(
                base, request.strategy, params, policy, request.horizon_days, rng, request.simulation_id, decide
            )
        else:
            row = open_loop_path(
                base, request.strategy, params, policy, request.horizon_days, rng, request.simulation_id
            )
        profits.append(row.profit)
        revenues.append(row.revenue)
        ends.append(row.end_inv)
        stabilities.append(row.stability)
        interventions.append(row.interventions)
        if i == 0:
            sample_trace = row.trace
        if row.stockout:
            stockouts += 1
        if row.triggers and not triggers:
            triggers = row.triggers
    expected = _money(sum(profits, Decimal("0")) / Decimal(n))
    expected_rev = _money(sum(revenues, Decimal("0")) / Decimal(n))
    p10 = _money(_pct(profits, 0.10))
    p50 = _money(_pct(profits, 0.50))
    p90 = _money(_pct(profits, 0.90))
    if p10 > p50:
        p10 = p50
    if p90 < p50:
        p90 = p50
    stockout_p = stockouts / n
    stability = int(round(sum(stabilities) / n))
    base_profit = baseline_profit if baseline_profit is not None else expected
    scenario_row = ScenarioResult(
        scenario_id=request.scenario.scenario_id,
        expected_profit=expected,
        profit_p10=p10,
        profit_p50=p50,
        profit_p90=p90,
        stockout_probability=stockout_p,
    )
    mean_iv = sum(interventions) / n if n else 0.0
    return SimulationReport(
        simulation_id=request.simulation_id,
        strategy_id=request.strategy.strategy_id,
        base_snapshot_id=snapshot.snapshot_id,
        horizon_days=request.horizon_days,
        expected_profit=expected,
        baseline_profit=base_profit,
        expected_revenue=expected_rev,
        profit_p10=p10,
        profit_p50=p50,
        profit_p90=p90,
        stockout_probability=stockout_p,
        expected_end_inventory=int(round(sum(ends) / n)),
        cash_required=cash_required,
        stability_horizon_days=stability,
        failure_triggers=triggers,
        scenario_results=[scenario_row],
        sensitivity=[],
        simulator_version=SIMULATOR_VERSION,
        parameter_version=PARAMETER_VERSION,
        created_at=now or datetime.now(),
        adaptive=use_adaptive,
        mean_interventions=mean_iv,
        sample_action_trace=sample_trace,
    )


def base_scenario() -> SimulationScenario:
    return SimulationScenario(
        scenario_id="base",
        name="base",
        scenario_type="base",
        description="base forecast",
        parameter_overrides={},
    )


def make_request(
    strategy: Strategy,
    snapshot_id: str,
    *,
    horizon: int,
    n: int,
    seed: int,
    scenario: SimulationScenario | None = None,
) -> SimulationRequest:
    return SimulationRequest(
        simulation_id=f"SIM_{uuid4().hex[:12]}",
        base_snapshot_id=snapshot_id,
        strategy=strategy,
        horizon_days=horizon,
        scenario=scenario or base_scenario(),
        rollout_count=n,
        random_seed=seed,
    )
