from datetime import UTC, datetime

from app.config.settings import Settings
from evals.experiment.runner import run_experiment_benchmark
from tests.fixtures.make_olist import AS_OF, write_mini_olist


def test_experiment_benchmark(tmp_path):
    data_dir = write_mini_olist(tmp_path / "olist")
    settings = Settings(as_of_date=AS_OF, store_seller_id="seller_demo", timezone="UTC")
    now = datetime(2018, 3, 16, tzinfo=UTC)
    rows = run_experiment_benchmark(data_dir, now, settings, n=3, seed=42)
    again = run_experiment_benchmark(data_dir, now, settings, n=3, seed=42)
    assert len(rows) == 4
    for a, b in zip(rows, again):
        assert a["selected_unchanged"]
        assert a["has_stress"]
        assert a["jobs"] <= 20
        assert a["status"] in {"sufficient", "uncertain", "budget_exhausted"}
        assert a["profits"] == b["profits"]
