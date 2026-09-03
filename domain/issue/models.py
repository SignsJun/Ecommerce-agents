from datetime import datetime
from decimal import Decimal

from domain.base import FrozenModel
from domain.enums import IssueType


class Issue(FrozenModel):
    issue_id: str
    issue_type: IssueType
    entity_type: str
    entity_id: str
    detected_at: datetime
    severity: str
    confidence: float
    estimated_impact: Decimal | None = None
    impact_horizon_days: int | None = None
    evidence_ids: list[str]
    status: str
    based_on_snapshot_id: str
    priority: float | None = None
