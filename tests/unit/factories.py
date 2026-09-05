from datetime import UTC, datetime
from decimal import Decimal

from domain.business.campaign import CampaignState
from domain.business.sku import SKUState
from domain.business.snapshot import BusinessStateSnapshot
from domain.common import DataQualityReport, StoreState, TimeRange
from domain.decision.approval import ApprovalState
from domain.decision.monitoring import ExecutionState, MonitoringState
from domain.decision.state import DecisionState
from domain.diagnosis.hypothesis import Hypothesis, RootCause
from domain.diagnosis.report import DiagnosisReport
from domain.enums import DataProvenance, DecisionPhase, IssueType
from domain.issue.evidence import Evidence
from domain.issue.models import Issue
from domain.simulation.models import FailureTrigger, ScenarioResult, SensitivityResult, SimulationRequest
from domain.simulation.report import SimulationReport
from domain.simulation.scenario import SimulationScenario
from domain.strategy.actions import AdjustAdBudget
from domain.strategy.models import Assumption, Strategy

NOW = datetime(2026, 9, 3, 10, 32, tzinfo=UTC)


def store() -> StoreState:
    return StoreState(
        store_id="STORE_001",
        seller_id="seller_demo",
        name="Demo",
        cash_balance=Decimal("100000.00"),
    )


def sku(sku_id: str = "SKU_A") -> SKUState:
    return SKUState(
        sku_id=sku_id,
        category="cool_stuff",
        price=Decimal("100.00"),
        base_price=Decimal("100.00"),
        unit_cost=Decimal("40.00"),
        inventory_on_hand=80,
        inventory_available=80,
        incoming_inventory=0,
        lead_time_days=10,
        units_sold_7d=70,
        units_sold_30d=300,
        revenue_7d=Decimal("7000.00"),
        profit_7d=Decimal("2100.00"),
        profit_margin_7d=0.30,
        conversion_rate_7d=0.03,
        refund_rate_7d=0.04,
        avg_rating_30d=4.5,
    )


def campaign(sku_id: str = "SKU_A") -> CampaignState:
    return CampaignState(
        campaign_id="CMP_A",
        sku_id=sku_id,
        status="active",
        daily_budget=Decimal("100.00"),
        spend_7d=Decimal("700.00"),
        attributed_revenue_7d=Decimal("2100.00"),
        impressions_7d=100000,
        clicks_7d=2000,
        conversions_7d=60,
        cpc_7d=Decimal("0.35"),
        cvr_7d=0.03,
        roas_7d=3.0,
        acos_7d=0.33,
    )


def snapshot() -> BusinessStateSnapshot:
    s = sku()
    c = campaign()
    return BusinessStateSnapshot(
        snapshot_id="SNAP_184",
        version=184,
        created_at=NOW,
        data_freshness_at=NOW,
        store=store(),
        skus={s.sku_id: s},
        campaigns={c.campaign_id: c},
        data_quality=DataQualityReport(
            completeness_score=0.9,
            freshness_score=1.0,
            consistency_score=1.0,
            missing_sources=[],
            warnings=[],
        ),
    )


def issue() -> Issue:
    return Issue(
        issue_id="ISSUE_018",
        issue_type=IssueType.PROFIT_EROSION,
        entity_type="sku",
        entity_id="SKU_A",
        detected_at=NOW,
        severity="high",
        confidence=0.88,
        estimated_impact=Decimal("18200.00"),
        impact_horizon_days=14,
        evidence_ids=["E101"],
        status="open",
        based_on_snapshot_id="SNAP_184",
        priority=1.0,
    )


def evidence() -> Evidence:
    return Evidence(
        evidence_id="E101",
        source_type="metric_state",
        source_ref="profit_engine",
        entity_type="sku",
        entity_id="SKU_A",
        metric="profit_margin",
        value=0.23,
        comparison="7d 0.23 vs 30d 0.31",
        period=TimeRange(start=NOW, end=NOW),
        description="margin drop",
        reliability=0.9,
        provenance=DataProvenance.DERIVED,
        tool_name="decompose_profit",
        tool_version="v1",
        snapshot_id="SNAP_184",
        created_at=NOW,
    )


def strategy() -> Strategy:
    return Strategy(
        strategy_id="STRAT_B",
        issue_id="ISSUE_018",
        name="Balanced",
        strategy_type="balanced",
        objective="restore margin",
        actions=[
            AdjustAdBudget(action_type="adjust_ad_budget", campaign_id="CMP_A", change_pct=-0.10),
        ],
        assumptions=[
            Assumption(
                assumption_id="A1",
                description="ROAS holds",
                parameter="roas",
                assumed_value=2.5,
                confidence=0.7,
                source="baseline",
                provenance=DataProvenance.DERIVED,
            )
        ],
        horizon_days=14,
        based_on_snapshot_id="SNAP_184",
        based_on_state_version=184,
        status="draft",
    )


def diagnosis_report() -> DiagnosisReport:
    return DiagnosisReport(
        diagnosis_id="D18",
        issue_id="ISSUE_018",
        status="confirmed",
        root_causes=[
            RootCause(
                cause_type="ad_efficiency",
                description="campaign b",
                confidence=0.91,
                estimated_contribution=0.6,
                supporting_evidence_ids=["E101"],
            )
        ],
        overall_confidence=0.86,
        key_evidence_ids=["E101"],
        uncertainties=[],
        generated_at=NOW,
        agent_version="v0.3",
        model_version="model-x",
    )


def simulation_report() -> SimulationReport:
    return SimulationReport(
        simulation_id="SIM_27",
        strategy_id="STRAT_B",
        base_snapshot_id="SNAP_184",
        horizon_days=14,
        expected_profit=Decimal("1000.00"),
        baseline_profit=Decimal("800.00"),
        expected_revenue=Decimal("5000.00"),
        profit_p10=Decimal("600.00"),
        profit_p50=Decimal("1000.00"),
        profit_p90=Decimal("1400.00"),
        stockout_probability=0.08,
        expected_end_inventory=40,
        cash_required=Decimal("0.00"),
        stability_horizon_days=18,
        failure_triggers=[
            FailureTrigger(day=19, constraint="ROAS below 2.2", actual_value=2.0, threshold=2.2)
        ],
        scenario_results=[
            ScenarioResult(
                scenario_id="base",
                expected_profit=Decimal("1000.00"),
                profit_p10=Decimal("600.00"),
                profit_p50=Decimal("1000.00"),
                profit_p90=Decimal("1400.00"),
                stockout_probability=0.08,
            )
        ],
        sensitivity=[SensitivityResult(parameter="roas", delta_pct=-0.2, profit_delta=Decimal("-200.00"))],
        simulator_version="v1",
        parameter_version="p1",
        created_at=NOW,
    )


def decision_state() -> DecisionState:
    return DecisionState(
        decision_id="DEC_018",
        phase=DecisionPhase.EVALUATING,
        issue=issue(),
        diagnosis_report=diagnosis_report(),
        candidate_strategies=[strategy()],
        simulation_reports=[simulation_report()],
        rejected_strategy_ids=[],
        initial_preferred_strategy_id="STRAT_B",
        approval=ApprovalState(
            required=True,
            status="pending",
            risk_level="L3",
        ),
        execution=ExecutionState(status="not_started", idempotency_key="DEC18-ACT02"),
        monitoring=MonitoringState(status="not_started"),
        trace_id="tr-018",
        created_at=NOW,
        updated_at=NOW,
    )


def simulation_request() -> SimulationRequest:
    return SimulationRequest(
        simulation_id="SIM_27",
        base_snapshot_id="SNAP_184",
        strategy=strategy(),
        horizon_days=14,
        scenario=SimulationScenario(
            scenario_id="base",
            name="base forecast",
            scenario_type="base",
            description="normal future",
        ),
        rollout_count=100,
        random_seed=42,
    )


def hypothesis() -> Hypothesis:
    return Hypothesis(
        hypothesis_id="H1",
        cause_type="ads",
        description="ads",
        confidence=0.5,
        status="open",
    )
