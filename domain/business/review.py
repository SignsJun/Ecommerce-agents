from datetime import datetime

from domain.base import FrozenModel
from domain.enums import DataProvenance


class ReviewRecord(FrozenModel):
    sku_id: str
    reviewed_at: datetime
    score: int
    provenance: DataProvenance
