from decimal import Decimal

from agents.simulation.evaluate import evaluate_recommendations
from domain.simulation.models import ScenarioResult
from domain.strategy.actions import AdjustAdBudget, AdjustPrice
from tests.unit import factories as f


def _rep(sid: str, profit: str, *, p10: str | None = None, stockout: float = 0.1, cash: str = "0", stability: int = 10, scene: str = "base"):
    p = Decimal(profit)
    q = Decimal(p10) if p10 is not None else p
    return f.simulation_report().model_copy(
        update={
            "strategy_id": sid,
            "expected_profit": p,
            "profit_p10": q,
            "profit_p50": p,
            "profit_p90": p,
            "stockout_probability": stockout,
            "cash_required": Decimal(cash),
            "stability_horizon_days": stability,
            "scenario_results": [
                ScenarioResult(
                    scenario_id=scene,
                    expected_profit=p,
                    profit_p10=q,
                    profit_p50=p,
                    profit_p90=p,
                    stockout_probability=stockout,
                )
            ],
        }
    )


def _noop():
    return f.strategy().model_copy(update={"strategy_id": "ST_do_nothing", "actions": [], "strategy_type": "custom"})


def _acted(sid: str):
    return f.strategy().model_copy(
        update={
            "strategy_id": sid,
            "actions": [AdjustAdBudget(action_type="adjust_ad_budget", campaign_id="CMP_A", change_pct=-0.10)],
        }
    )


def test_worse_than_baseline_rejected():
    recs, rejected = evaluate_recommendations(
        [
            _rep("ST_do_nothing", "100"),
            _rep("ST_bad", "20", p10="10"),
        ],
        [_noop(), _acted("ST_bad")],
    )
    assert "ST_bad" in rejected
    assert any(r.strategy_id == "ST_do_nothing" for r in recs)
    assert all(r.strategy_id != "ST_bad" for r in recs)


def test_dominated_rejected_keeps_frontier():
    recs, rejected = evaluate_recommendations(
        [
            _rep("ST_do_nothing", "50", stockout=0.10, cash="0"),
            _rep("ST_profit", "100", stockout=0.20, cash="500"),
            _rep("ST_mid", "60", stockout=0.20, cash="500"),
            _rep("ST_robust", "70", p10="65", stockout=0.05, cash="0"),
        ],
        [_noop(), _acted("ST_profit"), _acted("ST_mid"), _acted("ST_robust")],
    )
    assert "ST_mid" in rejected
    ids = [r.strategy_id for r in recs]
    assert "ST_profit" in ids
    assert "ST_robust" in ids
    assert 1 <= len(recs) <= 3
    assert [r.rank for r in recs] == list(range(1, len(recs) + 1))
    types = {r.recommendation_type for r in recs}
    assert types <= {"profit", "robust", "balanced", "status_quo"}


def test_keeps_status_quo_when_risk_tied():
    recs, rejected = evaluate_recommendations(
        [
            _rep("ST_do_nothing", "-15445.68", p10="-15774.12", stockout=0.0, cash="0", stability=0),
            _rep("ST_mild", "-9051.52", p10="-9159.84", stockout=0.0, cash="0", stability=0),
            _rep("ST_std", "-8606.76", p10="-8727.46", stockout=0.0, cash="0", stability=0),
            _rep("ST_strong", "-7774.14", p10="-7885.56", stockout=0.0, cash="0", stability=0),
        ],
        [_noop(), _acted("ST_mild"), _acted("ST_std"), _acted("ST_strong")],
    )
    ids = {r.strategy_id for r in recs}
    assert "ST_do_nothing" in ids
    assert "ST_strong" in ids
    assert 2 <= len(recs) <= 3
    assert "ST_mild" in rejected


def test_price_cut_not_unique_winner():
    recs, rejected = evaluate_recommendations(
        [
            _rep("ST_do_nothing", "80"),
            _rep("ST_cut", "-20", p10="-30"),
        ],
        [
            _noop(),
            f.strategy().model_copy(
                update={
                    "strategy_id": "ST_cut",
                    "actions": [AdjustPrice(action_type="adjust_price", sku_id="SKU_A", change_pct=-0.08)],
                }
            ),
        ],
    )
    assert "ST_cut" in rejected
    assert recs[0].strategy_id == "ST_do_nothing"
    assert recs[0].recommendation_type == "status_quo"
