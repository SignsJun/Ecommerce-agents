from datetime import UTC, datetime

from app.config.settings import Settings
from services.daily_run import DailyRunResult, run_daily
from tests.fixtures.make_olist import AS_OF, write_mini_olist
from tools.diagnosis.base import ToolResult
from tools.diagnosis.handlers import project_horizon_dates
from tools.diagnosis.investigate import context_from_run, investigate_issue
from tools.diagnosis.payloads import (
    InventoryProjectionPayload,
    ProfitDecomposePayload,
    PromotionHistoryPayload,
)
from tools.diagnosis.registry import TOOL_NAMES, invoke


def _run(tmp_path) -> DailyRunResult:
    data_dir = write_mini_olist(tmp_path / "olist")
    settings = Settings(as_of_date=AS_OF, store_seller_id="seller_demo", timezone="UTC")
    return run_daily(data_dir, settings=settings, now=datetime(2018, 3, 16, tzinfo=UTC))


def _dump(result: ToolResult) -> None:
    dumped = result.model_dump(mode="json")
    restored = ToolResult.model_validate(dumped)
    assert restored.success == result.success
    assert restored.tool_name == result.tool_name
    text = str(dumped)
    assert "Traceback" not in text
    assert "traceback" not in text


def test_each_tool_contract_success_and_missing(tmp_path):
    result = _run(tmp_path)
    ctx = context_from_run(result)
    issue = next(i for i in result.issues if i.entity_id == "sku_profit_erosion")
    sku_id = "sku_profit_erosion"
    campaign_id = ctx.business_repo.list_campaigns_for_sku(sku_id)[0]
    a0, a1, b0, b1 = project_horizon_dates(ctx.as_of)
    calls = {
        "get_issue_context": {"issue_id": issue.issue_id},
        "get_sku_summary": {"sku_id": sku_id},
        "get_metric_trend": {
            "entity_type": "sku",
            "entity_id": sku_id,
            "metric": "profit_margin",
            "window_name": "7d",
        },
        "decompose_profit": {
            "sku_id": sku_id,
            "period_a_start": a0,
            "period_a_end": a1,
            "period_b_start": b0,
            "period_b_end": b1,
        },
        "get_conversion_funnel": {"sku_id": sku_id},
        "get_campaign_breakdown": {"sku_id": sku_id},
        "get_campaign_trend": {"campaign_id": campaign_id},
        "get_inventory_projection": {"sku_id": sku_id},
        "get_refund_breakdown": {"sku_id": sku_id},
        "analyze_reviews": {"sku_id": sku_id, "window_name": "7d"},
        "compare_peer_skus": {"sku_id": sku_id, "metrics": "profit_margin,roas,days_of_cover"},
        "get_price_history": {"sku_id": sku_id},
        "get_promotion_history": {"sku_id": sku_id},
    }
    assert set(calls) == set(TOOL_NAMES)
    for name, kwargs in calls.items():
        out = invoke(ctx, name, **kwargs)
        _dump(out)
        assert out.success, (name, out.error)
        if name == "get_promotion_history":
            assert out.produces_evidence is False
            assert out.evidence == []
            assert isinstance(out.payload, PromotionHistoryPayload)
            assert out.payload.promotions == []
        else:
            assert out.produces_evidence is True
            assert out.evidence
            assert out.call.evidence_ids
            assert all(e.tool_name == name and e.snapshot_id == ctx.snapshot_id for e in out.evidence)

    missing_issue = invoke(ctx, "get_issue_context", issue_id="ISSUE_missing")
    _dump(missing_issue)
    assert missing_issue.success is False
    assert missing_issue.error is not None
    assert missing_issue.error.error_code == "not_found"
    assert "Traceback" not in missing_issue.error.message

    missing_sku = invoke(ctx, "get_sku_summary", sku_id="sku_missing")
    _dump(missing_sku)
    assert missing_sku.success is False
    assert missing_sku.error is not None
    assert missing_sku.error.error_code == "not_found"

    missing_campaign = invoke(ctx, "get_campaign_trend", campaign_id="CMP_missing")
    _dump(missing_campaign)
    assert missing_campaign.success is False
    assert missing_campaign.error is not None
    assert missing_campaign.error.error_code == "not_found"


def test_decompose_profit_numeric(tmp_path):
    result = _run(tmp_path)
    ctx = context_from_run(result)
    a0, a1, b0, b1 = project_horizon_dates(ctx.as_of)
    out = invoke(
        ctx,
        "decompose_profit",
        sku_id="sku_profit_erosion",
        period_a_start=a0,
        period_a_end=a1,
        period_b_start=b0,
        period_b_end=b1,
    )
    assert out.success
    payload = out.payload
    assert isinstance(payload, ProfitDecomposePayload)
    assert payload.period_a.profit_margin < payload.period_b.profit_margin
    assert payload.delta_ad_spend > 0 or payload.delta_refund_loss > 0


def test_inventory_projection_numeric(tmp_path):
    result = _run(tmp_path)
    ctx = context_from_run(result)
    out = invoke(ctx, "get_inventory_projection", sku_id="sku_stockout_risk")
    assert out.success
    payload = out.payload
    assert isinstance(payload, InventoryProjectionPayload)
    assert payload.first_stockout_day is not None
    assert payload.first_stockout_day <= 7
    assert payload.days[payload.first_stockout_day - 1].stockout


def test_investigate_runs_all_tools(tmp_path):
    result = _run(tmp_path)
    ctx = context_from_run(result)
    issue = next(i for i in result.issues if i.entity_id == "sku_profit_erosion")
    outputs = investigate_issue(ctx, issue.issue_id)
    assert [o.tool_name for o in outputs] == list(TOOL_NAMES)
    assert all(o.success for o in outputs)
