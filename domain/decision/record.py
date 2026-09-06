from datetime import datetime

from domain.base import FrozenModel
from domain.decision.recommendation import StrategyRecommendation
from domain.enums import IssueType


class DecisionRecord(FrozenModel):
    decision_id: str
    issue_id: str
    issue_type: IssueType
    snapshot_id: str
    diagnosis_id: str | None = None
    experiment_status: str | None = None
    recommendations: list[StrategyRecommendation] = []
    rejected_after_eval: list[str] = []
    rejected_strategy_ids: list[str] = []
    created_at: datetime
