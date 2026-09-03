from datetime import datetime
from typing import Literal

from domain.base import FrozenModel
from domain.diagnosis.hypothesis import RootCause


class DiagnosisReport(FrozenModel):
    diagnosis_id: str
    issue_id: str
    status: Literal["confirmed", "partial", "insufficient_evidence"]
    root_causes: list[RootCause]
    overall_confidence: float
    key_evidence_ids: list[str]
    uncertainties: list[str]
    generated_at: datetime
    agent_version: str
    model_version: str
