from pathlib import Path

from services.ingestion.olist_loader import load_olist
from tests.fixtures.make_olist import SELLER_ID, write_mini_olist
from zoneinfo import ZoneInfo


def test_load_olist_selects_seller(tmp_path: Path):
    dest = write_mini_olist(tmp_path / "olist")
    lines = load_olist(dest, ZoneInfo("UTC"), seller_id=SELLER_ID, top_sku_count=10)
    assert lines
    assert {ln.seller_id for ln in lines} == {SELLER_ID}
    assert "sku_healthy" in {ln.sku_id for ln in lines}
    assert all(ln.purchased_at.tzinfo is not None for ln in lines)
