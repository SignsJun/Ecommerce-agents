from datetime import datetime

from domain.base import FrozenModel
from domain.common import TimeRange
from domain.enums import DataProvenance


class Evidence(FrozenModel):
    evidence_id: str
    source_type: str
    source_ref: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    metric: str | None = None
    value: str | int | float | bool | None = None
    comparison: str | None = None
    period: TimeRange | None = None
    description: str
    reliability: float
    provenance: DataProvenance
    tool_name: str | None = None
    tool_version: str | None = None
    snapshot_id: str | None = None
    created_at: datetime
