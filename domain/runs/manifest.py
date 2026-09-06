from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from domain.base import FrozenModel


class RunKPI(FrozenModel):
    gmv: Decimal
    profit: Decimal
    roas: float | None
    inventory_health: float
    ad_spend: Decimal


class RunManifest(FrozenModel):
    run_id: str
    status: Literal["pending", "running", "done", "failed"]
    source: Literal["bundled", "upload"]
    fake_llm: bool
    llm: str
    n: int = 2
    as_of: date | None = None
    snapshot_id: str | None = None
    issue_ids: list[str] = []
    decision_ids: list[str] = []
    issue_decisions: dict[str, str] = {}
    created_at: datetime
    finished_at: datetime | None = None
    error: str | None = None
    kpi: RunKPI | None = None
    data_dir: str = ""
    store_id: str = ""
    store_name: str = ""
