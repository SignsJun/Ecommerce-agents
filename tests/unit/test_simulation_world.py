import random
from datetime import UTC, datetime
from decimal import Decimal

from app.config.settings import default_policy
from domain.strategy.actions import AdjustAdBudget, ReplenishInventory
from services.simulation.params import SimulatorParameterSet
from services.simulation.world import apply_strategy, make_request, rollout, step, world_from_snapshot
from tests.unit import factories as f


def _strat(actions, **kwargs):
    return f.strategy().model_copy(update={"actions": actions, **kwargs})


def test_inventory_ledger():
    snap = f.snapshot()
    policy = default_policy()
    params = SimulatorParameterSet(demand_sigma=0.0)
    state = world_from_snapshot(snap, "SKU_A", policy)
    start = state.inventory
    rng = random.Random(0)
    daily, _, _ = step(state, 1, params, policy, rng, "SIM")
    assert daily.expected_sales >= 0
    assert state.inventory == start - int(daily.expected_sales)
    assert daily.expected_profit.__class__ is Decimal


def test_replenish_arrives_after_lead_time():
    snap = f.snapshot()
    policy = default_policy()
    params = SimulatorParameterSet(demand_sigma=0.0)
    state = world_from_snapshot(snap, "SKU_A", policy)
    lead = state.lead_time
    apply_strategy(state, _strat([ReplenishInventory(action_type="replenish", sku_id="SKU_A", quantity=25)]))
    rng = random.Random(1)
    before = None
    for day in range(1, lead + 2):
        before = state.inventory
        step(state, day, params, policy, rng, "SIM")
        if day == lead:
            assert state.inventory >= before
    assert state.cash_required > 0


def test_deterministic_no_noise():
    snap = f.snapshot()
    policy = default_policy()
    params = SimulatorParameterSet(demand_sigma=0.0)
    req = make_request(f.strategy(), snap.snapshot_id, horizon=5, n=1, seed=7)
    a = rollout(snap, policy, req, "SKU_A", params=params, now=datetime(2018, 3, 16, tzinfo=UTC))
    b = rollout(snap, policy, req, "SKU_A", params=params, now=datetime(2018, 3, 16, tzinfo=UTC))
    assert a.expected_profit == b.expected_profit
    assert a.profit_p10 <= a.profit_p50 <= a.profit_p90


def test_seed_reproducible_with_noise():
    snap = f.snapshot()
    policy = default_policy()
    params = SimulatorParameterSet(demand_sigma=0.15)
    req = make_request(f.strategy(), snap.snapshot_id, horizon=7, n=8, seed=99)
    now = datetime(2018, 3, 16, tzinfo=UTC)
    a = rollout(snap, policy, req, "SKU_A", params=params, now=now)
    b = rollout(snap, policy, req, "SKU_A", params=params, now=now)
    assert a.expected_profit == b.expected_profit
    assert a.stockout_probability == b.stockout_probability


def test_ad_cut_lowers_spend():
    snap = f.snapshot()
    policy = default_policy()
    params = SimulatorParameterSet(demand_sigma=0.0)
    base = world_from_snapshot(snap, "SKU_A", policy)
    cut = base.clone()
    apply_strategy(
        cut,
        _strat([AdjustAdBudget(action_type="adjust_ad_budget", campaign_id="CMP_A", change_pct=-0.30)]),
    )

    def run(state):
        s = state.clone()
        rng = random.Random(0)
        for day in range(1, 8):
            step(s, day, params, policy, rng, "SIM")
        return s.cumulative_ad

    assert run(cut) < run(base)


def test_demand_mult_scales_sales():
    snap = f.snapshot()
    policy = default_policy()
    low = SimulatorParameterSet(demand_sigma=0.0, demand_mult=0.5)
    high = SimulatorParameterSet(demand_sigma=0.0, demand_mult=1.0)
    a = world_from_snapshot(snap, "SKU_A", policy)
    b = a.clone()
    rng = random.Random(0)
    da, _, _ = step(a, 1, low, policy, rng, "SIM")
    rng = random.Random(0)
    db, _, _ = step(b, 1, high, policy, rng, "SIM")
    assert da.expected_sales <= db.expected_sales


def test_lead_time_extra_delays_arrival():
    snap = f.snapshot()
    policy = default_policy()
    params = SimulatorParameterSet(demand_sigma=0.0)
    state = world_from_snapshot(snap, "SKU_A", policy)
    base_lead = state.lead_time
    state.lead_time = base_lead + 7
    apply_strategy(state, _strat([ReplenishInventory(action_type="replenish", sku_id="SKU_A", quantity=25)]))
    rng = random.Random(1)
    arrived = None
    for day in range(1, state.lead_time + 2):
        before = state.inventory
        step(state, day, params, policy, rng, "SIM")
        if state.inventory > before:
            arrived = day
            break
    assert arrived == base_lead + 7

