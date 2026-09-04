from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domain.diagnosis.hypothesis import Hypothesis, RootCause

DiagnosisAction = Literal[
    "call_tool",
    "activate_cause",
    "reject_cause",
    "request_stop",
    "escalate",
]


class LLMModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class LLMHypothesis(LLMModel):
    hypothesis_id: str
    cause_type: str
    description: str
    confidence: float
    supporting_evidence_ids: list[str] = []
    contradicting_evidence_ids: list[str] = []
    status: str = "open"


class DiagnosisStep(LLMModel):
    hypotheses: list[LLMHypothesis] = []
    unresolved_questions: list[str] = []
    action: DiagnosisAction
    target_cause: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    reason: str | None = None
    evidence_ids: list[str] = []
    stop_reason: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _alias_stop(cls, data):
        if isinstance(data, dict) and data.get("action") == "stop":
            data = {**data, "action": "request_stop"}
        return data


class LLMRootCause(LLMModel):
    cause_type: str
    description: str
    confidence: float
    estimated_contribution: float | None = None
    supporting_evidence_ids: list[str] = []


class DiagnosisReportDraft(LLMModel):
    status: Literal["confirmed", "partial", "insufficient_evidence"]
    root_causes: list[LLMRootCause] = []
    uncertainties: list[str] = []
    overall_confidence: float = 0.0


def to_hypotheses(items: list[LLMHypothesis]) -> list[Hypothesis]:
    return [
        Hypothesis(
            hypothesis_id=h.hypothesis_id,
            cause_type=h.cause_type,
            description=h.description,
            confidence=max(0.0, min(1.0, h.confidence)),
            supporting_evidence_ids=list(h.supporting_evidence_ids),
            contradicting_evidence_ids=list(h.contradicting_evidence_ids),
            status=h.status,
        )
        for h in items
    ]


def to_root_causes(items: list[LLMRootCause]) -> list[RootCause]:
    return [
        RootCause(
            cause_type=c.cause_type,
            description=c.description,
            confidence=max(0.0, min(1.0, c.confidence)),
            estimated_contribution=c.estimated_contribution,
            supporting_evidence_ids=list(c.supporting_evidence_ids),
        )
        for c in items
    ]
