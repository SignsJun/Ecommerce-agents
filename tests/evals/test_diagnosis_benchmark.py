from datetime import UTC, datetime

from app.config.settings import Settings
from evals.diagnosis.runner import run_fake_benchmark, run_missing_metrics_escalation
from tests.fixtures.make_olist import AS_OF, write_mini_olist


def test_fake_benchmark_grounding(tmp_path):
    data_dir = write_mini_olist(tmp_path / "olist")
    settings = Settings(as_of_date=AS_OF, store_seller_id="seller_demo", timezone="UTC")
    scores = run_fake_benchmark(data_dir, datetime(2018, 3, 16, tzinfo=UTC), settings)
    assert len(scores) == 4
    for row in scores:
        assert row["evidence_grounding"] == 1.0
        assert row["root_cause_accuracy"] == 1.0
        assert row["tool_efficiency"] == 1.0
        assert row["hallucination_rate"] == 0.0
        assert row["irrelevant_tool_rate"] == 0.0
        assert row["correct_escalation"] == 1.0
        assert row["unnecessary_investigation_rate"] == 0.0


def test_missing_metrics_escalation(tmp_path):
    data_dir = write_mini_olist(tmp_path / "olist")
    settings = Settings(as_of_date=AS_OF, store_seller_id="seller_demo", timezone="UTC")
    row = run_missing_metrics_escalation(data_dir, datetime(2018, 3, 16, tzinfo=UTC), settings)
    assert row["status"] == "insufficient_evidence"
    assert row["correct_escalation"] == 1.0
    assert row["hallucination_rate"] == 0.0
