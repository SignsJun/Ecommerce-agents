from domain.base import FrozenModel
from domain.diagnosis.cause import CauseInvestigation
from domain.diagnosis.hypothesis import Hypothesis, RootCause, ToolCallRecord
from domain.issue.models import Issue


class DiagnosisState(FrozenModel):
    diagnosis_id: str
    issue: Issue
    hypotheses: list[Hypothesis] = []
    evidence_ids: list[str] = []
    unresolved_questions: list[str] = []
    tool_history: list[ToolCallRecord] = []
    root_causes: list[RootCause] = []
    causes: list[CauseInvestigation] = []
    diagnosis_status: str = "in_progress"
    step_count: int = 0
    gate_feedback: str | None = None
