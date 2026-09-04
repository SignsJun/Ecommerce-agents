from enum import Enum
from typing import Literal

from domain.base import FrozenModel


class CauseStatus(str, Enum):
    UNSCREENED = "unscreened"
    SCREENED_NON_MATERIAL = "screened_non_material"
    SCREENED_POSSIBLE = "screened_possible"
    ACTIVE = "active"
    INVESTIGATED_SUPPORTED = "investigated_supported"
    INVESTIGATED_REJECTED = "investigated_rejected"
    BLOCKED_BY_DATA = "blocked_by_data"


class CauseInvestigation(FrozenModel):
    cause_type: str
    status: CauseStatus
    screening_score: float | None = None
    materiality_score: float | None = None
    confidence: float = 0.0
    evidence_ids: list[str] = []
    investigation_tool_calls: int = 0
    activation_reason: str | None = None
    resolution_reason: str | None = None
    was_activated: bool = False


class CauseAssessment(FrozenModel):
    cause_type: str
    conclusion: Literal["supported", "rejected", "uncertain"]
    confidence: float = 0.0
    evidence_ids: list[str] = []
