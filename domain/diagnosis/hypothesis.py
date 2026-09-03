from datetime import datetime

from domain.base import FrozenModel


class ToolCallRecord(FrozenModel):
    tool_name: str
    tool_version: str | None = None
    arguments: dict[str, str | int | float | bool | None]
    success: bool
    error_code: str | None = None
    evidence_ids: list[str]
    called_at: datetime


class Hypothesis(FrozenModel):
    hypothesis_id: str
    cause_type: str
    description: str
    confidence: float
    supporting_evidence_ids: list[str] = []
    contradicting_evidence_ids: list[str] = []
    status: str


class RootCause(FrozenModel):
    cause_type: str
    description: str
    confidence: float
    estimated_contribution: float | None = None
    supporting_evidence_ids: list[str]
