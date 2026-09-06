from datetime import UTC, datetime

from agents.llm.client import LLMUnavailable
from app.cli import main
from app.config.settings import Settings
from domain.business.inventory import days_of_cover
from domain.enums import IssueType
from services.daily_run import run_daily
from tests.fixtures.make_olist import AS_OF, write_mini_olist


def test_pipeline_detects_four_issue_types(tmp_path):
    data_dir = write_mini_olist(tmp_path / "olist")
    settings = Settings(as_of_date=AS_OF, store_seller_id="seller_demo", timezone="UTC")
    result = run_daily(data_dir, settings=settings, now=datetime(2018, 3, 16, tzinfo=UTC))
    assert result.snapshot.skus
    assert result.snapshot.data_quality.missing_sources
    sku = result.snapshot.skus["sku_stockout_risk"]
    assert sku.inventory_available > 0
    assert sku.revenue_7d > 0
    assert days_of_cover(sku.inventory_available, sku.units_sold_7d) < sku.lead_time_days + 7
    cover_excess = days_of_cover(
        result.snapshot.skus["sku_excess_inventory"].inventory_available,
        result.snapshot.skus["sku_excess_inventory"].units_sold_7d,
    )
    assert cover_excess > 60
    assert any(
        i.issue_type == IssueType.PROFIT_EROSION and i.entity_id == "sku_profit_erosion" for i in result.issues
    )
    assert any(
        i.issue_type == IssueType.AD_INEFFICIENCY and i.entity_id == "sku_ad_inefficiency" for i in result.issues
    )
    assert any(
        i.issue_type == IssueType.STOCKOUT_RISK and i.entity_id == "sku_stockout_risk" for i in result.issues
    )
    assert any(
        i.issue_type == IssueType.EXCESS_INVENTORY and i.entity_id == "sku_excess_inventory" for i in result.issues
    )
    for issue in result.issues:
        assert issue.evidence_ids
        assert issue.based_on_snapshot_id == result.snapshot.snapshot_id


def test_cli_run_daily(tmp_path, capsys):
    data_dir = write_mini_olist(tmp_path / "olist")
    code = main(["run-daily", "--data-dir", str(data_dir)])
    assert code == 0
    out = capsys.readouterr().out
    assert "issues=" in out


def test_cli_investigate(tmp_path, capsys):
    data_dir = write_mini_olist(tmp_path / "olist")
    code = main(["investigate", "--data-dir", str(data_dir)])
    assert code == 0
    out = capsys.readouterr().out
    assert "investigate" in out
    assert "get_sku_summary" in out


def test_cli_diagnose_fake(tmp_path, capsys):
    data_dir = write_mini_olist(tmp_path / "olist")
    code = main(["diagnose", "--data-dir", str(data_dir), "--fake-llm"])
    assert code == 0
    out = capsys.readouterr().out
    assert "diagnose" in out
    assert "status=" in out


def test_cli_diagnose_missing_key(tmp_path, capsys, monkeypatch):
    data_dir = write_mini_olist(tmp_path / "olist")

    def boom(settings):
        raise LLMUnavailable("missing ECOM_LLM_API_KEY")

    monkeypatch.setattr("app.cli.llm_from_settings", boom)
    code = main(["diagnose", "--data-dir", str(data_dir)])
    assert code == 1
    assert "missing ECOM_LLM_API_KEY" in capsys.readouterr().out


def test_cli_plan_fake(tmp_path, capsys):
    data_dir = write_mini_olist(tmp_path / "olist")
    code = main(["plan", "--data-dir", str(data_dir), "--fake-llm"])
    assert code == 0
    out = capsys.readouterr().out
    assert "generation_source=llm" in out
    assert "initial=" in out


def test_cli_simulate_fake(tmp_path, capsys):
    data_dir = write_mini_olist(tmp_path / "olist")
    code = main(["simulate", "--data-dir", str(data_dir), "--fake-llm"])
    assert code == 0
    out = capsys.readouterr().out
    assert "simulate" in out
    assert "profit=" in out
    assert "recommend" in out


def test_cli_archive_fake(tmp_path, capsys):
    data_dir = write_mini_olist(tmp_path / "olist")
    mem = tmp_path / "decisions"
    code = main(["archive", "--data-dir", str(data_dir), "--fake-llm", "--n", "2", "--decisions-dir", str(mem)])
    assert code == 0
    out = capsys.readouterr().out
    assert "decision=" in out
    assert "recommend" in out
    line = next(x for x in out.splitlines() if x.startswith("decision="))
    did = line.split("\t")[0].split("=", 1)[1]
    folder = mem / did
    for name in (
        "01_issue_brief.md",
        "02_diagnosis_report.md",
        "03_strategy_proposals.md",
        "04_simulation_report.md",
        "05_decision_record.md",
        "case.json",
        "provenance.json",
    ):
        assert (folder / name).exists()
    code = main(["cases", "--decisions-dir", str(mem)])
    assert code == 0
    listed = capsys.readouterr().out
    assert did in listed
    code = main(["case", did, "--decisions-dir", str(mem)])
    assert code == 0
    body = capsys.readouterr().out
    assert "document_type: decision_record" in body
    code = main(["trace", did, "--decisions-dir", str(mem)])
    assert code == 0
    trace = capsys.readouterr().out
    assert "edge\t" in trace
    assert "node\t" in trace
