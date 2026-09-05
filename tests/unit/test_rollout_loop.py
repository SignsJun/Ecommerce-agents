from datetime import UTC, datetime

from agents.rollout.agent import RolloutPolicyAgent
from agents.rollout.schema import RolloutDecision
from app.config.settings import default_policy
from domain.strategy.actions import ReplenishInventory
from services.simulation.params import SimulatorParameterSet
from services.simulation.world import make_request, rollout
from tests.unit import factories as f


def _now():
    return datetime(2018, 3, 16, tzinfo=UTC)


def test_checkpoint_not_every_day():
    snap = f.snapshot()
    policy = default_policy()
    params = SimulatorParameterSet(demand_sigma=0.0)
    req = make_request(f.strategy(), snap.snapshot_id, horizon=14, n=1, seed=1)
    agent = RolloutPolicyAgent()
    rollout(snap, policy, req, "SKU_A", params=params, now=_now(), adaptive=True, decide=agent.decide)
    assert agent.decide_calls < 14
    assert agent.decide_calls >= 5


def test_illegal_decision_becomes_noop():
    snap = f.snapshot()
    policy = default_policy()
    params = SimulatorParameterSet(demand_sigma=0.0)
    req = make_request(f.strategy(), snap.snapshot_id, horizon=7, n=1, seed=1)

    def boom(obs):
        return RolloutDecision(action="replenish", target_id="SKU_A", intensity="strong", reason="x")

    row = rollout(snap, policy, req, "SKU_A", params=params, now=_now(), adaptive=True, decide=boom)
    assert row.mean_interventions == 0
    assert row.sample_action_trace
    assert all(not t.accepted for t in row.sample_action_trace)


def test_adaptive_p10_not_worse_on_stockout():
    sku = f.sku().model_copy(update={"inventory_available": 5, "inventory_on_hand": 5, "incoming_inventory": 0, "lead_time_days": 4})
    snap = f.snapshot().model_copy(update={"skus": {"SKU_A": sku}})
    policy = default_policy()
    params = SimulatorParameterSet(demand_sigma=0.0)
    strat = f.strategy().model_copy(
        update={"actions": [ReplenishInventory(action_type="replenish", sku_id="SKU_A", quantity=1)], "horizon_days": 14}
    )
    req = make_request(strat, snap.snapshot_id, horizon=14, n=4, seed=3)
    agent = RolloutPolicyAgent(cover_min=float(policy.stockout_safety_days))
    open_row = rollout(snap, policy, req, "SKU_A", params=params, now=_now(), adaptive=False)
    adapt_row = rollout(snap, policy, req, "SKU_A", params=params, now=_now(), adaptive=True, decide=agent.decide)
    assert adapt_row.adaptive
    assert not open_row.adaptive
    assert adapt_row.profit_p10 >= open_row.profit_p10
    assert adapt_row.mean_interventions >= 1
