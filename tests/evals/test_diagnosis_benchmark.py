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
        assert row["status"] == "confirmed"
        assert row["root_cause_precision"] == 1.0
        assert row["root_cause_recall"] == 1.0
        assert row["root_cause_f1"] == 1.0
        assert row["evidence_accuracy"] == 1.0
        assert row["finalization_accuracy"] == 1.0


def test_missing_metrics_escalation(tmp_path):
    data_dir = write_mini_olist(tmp_path / "olist")
    settings = Settings(as_of_date=AS_OF, store_seller_id="seller_demo", timezone="UTC")
    row = run_missing_metrics_escalation(data_dir, datetime(2018, 3, 16, tzinfo=UTC), settings)
    assert row["status"] == "insufficient_evidence"
    assert row["finalization_accuracy"] == 1.0
    assert row["evidence_accuracy"] == 1.0
