from enum import Enum


class DataProvenance(str, Enum):
    OBSERVED = "observed"
    DERIVED = "derived"
    MODEL_ESTIMATED = "model_estimated"
    AGENT_INFERRED = "agent_inferred"
    SIMULATED = "simulated"


class IssueType(str, Enum):
    PROFIT_EROSION = "profit_erosion"
    AD_INEFFICIENCY = "ad_inefficiency"
    STOCKOUT_RISK = "stockout_risk"
    EXCESS_INVENTORY = "excess_inventory"


class DecisionPhase(str, Enum):
    ISSUE_OPENED = "issue_opened"
    DIAGNOSING = "diagnosing"
    DIAGNOSED = "diagnosed"
    PLANNING = "planning"
    VALIDATING = "validating"
    SIMULATING = "simulating"
    EVALUATING = "evaluating"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    FAILED = "failed"
