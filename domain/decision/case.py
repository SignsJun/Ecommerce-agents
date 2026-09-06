from domain.base import FrozenModel
from domain.business.snapshot import BusinessStateSnapshot
from domain.decision.provenance import ProvenanceGraph
from domain.decision.recommendation import StrategyRecommendation
from domain.decision.record import DecisionRecord
from domain.decision.state import DecisionArtifact
from domain.diagnosis.report import DiagnosisReport
from domain.issue.evidence import Evidence
from domain.issue.models import Issue
from domain.simulation.report import SimulationReport
from domain.strategy.models import Strategy
from domain.strategy.validation import StrategyValidationResult


class DecisionCase(FrozenModel):
    record: DecisionRecord
    snapshot: BusinessStateSnapshot
    issue: Issue
    evidence: list[Evidence] = []
    diagnosis: DiagnosisReport | None = None
    strategies: list[Strategy] = []
    validations: list[StrategyValidationResult] = []
    simulations: list[SimulationReport] = []
    recommendations: list[StrategyRecommendation] = []
    artifacts: list[DecisionArtifact] = []
    provenance: ProvenanceGraph
