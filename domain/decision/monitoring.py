from datetime import datetime
from typing import Literal

from domain.base import FrozenModel


class ExecutionState(FrozenModel):
    status: Literal["not_started", "in_progress", "completed", "failed", "partial"]
    idempotency_key: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class MonitoringState(FrozenModel):
    status: Literal["not_started", "active", "deviated", "resolved"]
    last_checked_at: datetime | None = None
    expected_vs_actual: list[str] = []
