from decimal import Decimal

from app.config.settings import default_policy
from domain.strategy.actions import AdjustAdBudget, PauseCampaign, ReplenishInventory
from domain.strategy.models import Strategy
from services.strategy.validator import validate_strategy
from tests.unit import factories as f


def _strat(**kwargs):
    base = f.strategy()
    return base.model_copy(update=kwargs)


def test_unknown_campaign_rejects_whole_strategy():
    snap = f.snapshot()
    issue = f.issue()
    strategy = _strat(
        actions=[AdjustAdBudget(action_type="adjust_ad_budget", campaign_id="CAMP_999", change_pct=-0.10)]
    )
    result = validate_strategy(strategy, snap, default_policy(), issue)
    assert result.feasible is False
    assert any(e.code == "UNKNOWN_TARGET_ID" for e in result.errors)
    assert result.normalized_strategy is None


def test_disallowed_action():
    snap = f.snapshot()
    issue = f.issue()
    strategy = _strat(
        actions=[ReplenishInventory(action_type="replenish", sku_id="SKU_A", quantity=10)]
    )
    result = validate_strategy(strategy, snap, default_policy(), issue)
    assert result.feasible is False
    assert any(e.code == "DISALLOWED_ACTION" for e in result.errors)


def test_pause_and_adjust_conflict():
    snap = f.snapshot()
    issue = f.issue()
    strategy = _strat(
        actions=[
            PauseCampaign(action_type="pause_campaign", campaign_id="CMP_A"),
            AdjustAdBudget(action_type="adjust_ad_budget", campaign_id="CMP_A", change_pct=-0.10),
        ]
    )
    result = validate_strategy(strategy, snap, default_policy(), issue)
    assert result.feasible is False
    assert any(e.code == "CONFLICT" for e in result.errors)


def test_replenish_cash():
    from domain.enums import IssueType

    snap = f.snapshot().model_copy(update={"store": f.store().model_copy(update={"cash_balance": Decimal("1.00")})})
    issue = f.issue().model_copy(update={"issue_type": IssueType.STOCKOUT_RISK})
    strategy = _strat(
        actions=[ReplenishInventory(action_type="replenish", sku_id="SKU_A", quantity=50)]
    )
    result = validate_strategy(strategy, snap, default_policy(), issue)
    assert result.feasible is False
    assert any(e.code == "INSUFFICIENT_CASH" for e in result.errors)


def test_snapshot_mismatch():
    snap = f.snapshot()
    issue = f.issue()
    strategy = _strat(based_on_snapshot_id="SNAP_OTHER")
    result = validate_strategy(strategy, snap, default_policy(), issue)
    assert result.feasible is False
    assert any(e.code == "SNAPSHOT_MISMATCH" for e in result.errors)


def test_do_nothing_ok():
    snap = f.snapshot()
    issue = f.issue()
    strategy = _strat(strategy_type="custom", name="Do Nothing", actions=[])
    result = validate_strategy(strategy, snap, default_policy(), issue)
    assert result.feasible is True
