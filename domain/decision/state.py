from datetime import datetime

from domain.base import FrozenModel
from domain.decision.approval import ApprovalState
from domain.decision.monitoring import ExecutionState, MonitoringState
from domain.decision.recommendation import StrategyRecommendation
from domain.diagnosis.report import DiagnosisReport
from domain.enums import DecisionPhase
from domain.issue.models import Issue
from domain.simulation.report import SimulationReport
from domain.strategy.models import Strategy


class DecisionState(FrozenModel):
    decision_id: str
    phase: DecisionPhase
    issue: Issue
    diagnosis_report: DiagnosisReport | None = None
    candidate_strategies: list[Strategy] = []
    simulation_reports: list[SimulationReport] = []
    rejected_strategy_ids: list[str] = []
    initial_preferred_strategy_id: str | None = None
    experiment_status: str | None = None
    final_recommendations: list[StrategyRecommendation] = []
    rejected_after_eval: list[str] = []
    approval: ApprovalState | None = None
    execution: ExecutionState | None = None
    monitoring: MonitoringState | None = None
    trace_id: str
    created_at: datetime
    updated_at: datetime


class DecisionArtifact(FrozenModel):
    artifact_id: str
    artifact_type: str
    decision_id: str
    issue_id: str | None = None
    version: int
    status: str
    created_at: datetime
    created_by: str
    model_version: str | None = None
    source_snapshot_ids: list[str]
    evidence_ids: list[str]
    related_artifact_ids: list[str]
    document_uri: str
    content_hash: str = ""
