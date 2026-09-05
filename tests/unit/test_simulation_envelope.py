from app.config.settings import default_policy
from domain.strategy.actions import ReplenishInventory
from services.simulation.envelope import build_envelope
from tests.unit import factories as f


def test_ad_envelope_allows_pause_not_replenish():
    policy = default_policy()
    env = build_envelope(f.strategy(), policy)
    assert "adjust_ad_budget" in env.allowed_actions
    assert "pause_campaign" in env.allowed_actions
    assert "replenish" not in env.allowed_actions
    assert env.price_locked
    assert not env.replenish_allowed
    assert env.allowed_targets == ("CMP_A",)


def test_do_nothing_envelope_empty():
    policy = default_policy()
    strat = f.strategy().model_copy(update={"actions": [], "strategy_type": "custom", "strategy_id": "ST_do_nothing"})
    env = build_envelope(strat, policy)
    assert env.allowed_actions == ()
    assert env.allowed_targets == ()


def test_replenish_envelope_no_ads():
    policy = default_policy()
    strat = f.strategy().model_copy(
        update={"actions": [ReplenishInventory(action_type="replenish", sku_id="SKU_A", quantity=10)]}
    )
    env = build_envelope(strat, policy)
    assert env.allowed_actions == ("replenish",)
    assert env.replenish_allowed
    assert "adjust_ad_budget" not in env.allowed_actions
