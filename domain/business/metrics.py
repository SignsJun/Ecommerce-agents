from datetime import datetime

from domain.base import FrozenModel
from domain.enums import DataProvenance


class MetricState(FrozenModel):
    metric_name: str
    entity_type: str
    entity_id: str
    current_value: float
    baseline_7d: float | None = None
    baseline_30d: float | None = None
    trend_7d: float | None = None
    trend_30d: float | None = None
    expected_low: float | None = None
    expected_high: float | None = None
    peer_median: float | None = None
    provenance: DataProvenance
    calculated_at: datetime
