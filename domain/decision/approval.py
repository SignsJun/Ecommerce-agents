from datetime import datetime
from typing import Literal

from domain.base import FrozenModel


class ApprovalState(FrozenModel):
    required: bool
    status: Literal["not_required", "pending", "granted", "rejected"]
    risk_level: str
    approver: str | None = None
    decided_at: datetime | None = None
