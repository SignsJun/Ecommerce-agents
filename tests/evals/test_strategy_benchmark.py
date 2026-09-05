from datetime import UTC, datetime

from app.config.settings import Settings
from evals.strategy.runner import run_llm_strategy_benchmark, run_rule_strategy_benchmark
from tests.fixtures.make_olist import AS_OF, write_mini_olist


def test_strategy_llm_and_rule_benchmark(tmp_path):
    data_dir = write_mini_olist(tmp_path / "olist")
    settings = Settings(as_of_date=AS_OF, store_seller_id="seller_demo", timezone="UTC")
    now = datetime(2018, 3, 16, tzinfo=UTC)
    llm_rows = run_llm_strategy_benchmark(data_dir, now, settings)
    rule_rows = run_rule_strategy_benchmark(data_dir, now, settings)
    assert len(llm_rows) == 4
    assert len(rule_rows) == 4
    for row in llm_rows:
        assert row["generation_source"] == "llm"
        assert row["selected"]
        assert row["feasible"] >= 1
        assert row["feasibility_rate"] == 1.0
        assert row["constraint_violation_rate"] == 0.0
        assert row["diversity"] >= 2
        assert row["approval_from_partial_only"] is False
    for row in rule_rows:
        assert row["generation_source"] == "rule"
        assert row["selected"]
        assert row["feasible"] >= 1
