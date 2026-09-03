from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from domain.business.snapshot import BusinessStateSnapshot
from domain.decision.state import DecisionState
from domain.diagnosis.report import DiagnosisReport
from domain.diagnosis.state import DiagnosisState
from domain.issue.evidence import Evidence
from domain.issue.models import Issue
from domain.simulation.models import SimulatedBusinessState, SimulationJob, SimulationRequest
from domain.simulation.report import SimulationReport
from domain.strategy.actions import (
    AdjustAdBudget,
    AdjustPrice,
    BusinessAction,
    PauseCampaign,
    ReplenishInventory,
    UpdateListing,
)
from domain.strategy.models import Strategy
from tests.unit import factories as f


def _roundtrip(model_cls, obj):
    dumped = obj.model_dump(mode="json")
    restored = model_cls.model_validate(dumped)
    assert restored == obj


def test_snapshot_roundtrip_decimal_timezone():
    obj = f.snapshot()
    dumped = obj.model_dump(mode="json")
    restored = BusinessStateSnapshot.model_validate(dumped)
    assert restored == obj
    assert restored.store.cash_balance == Decimal("100000.00")
    assert restored.created_at.tzinfo is not None
    assert restored.skus["SKU_A"].price == Decimal("100.00")


def test_snapshot_frozen():
    obj = f.snapshot()
    with pytest.raises(ValidationError):
        obj.version = 185


def test_issue_evidence_roundtrip():
    _roundtrip(Issue, f.issue())
    _roundtrip(Evidence, f.evidence())
    assert f.evidence().created_at.tzinfo is not None


def test_diagnosis_strategy_decision_roundtrip():
    _roundtrip(DiagnosisReport, f.diagnosis_report())
    _roundtrip(Strategy, f.strategy())
    _roundtrip(SimulationReport, f.simulation_report())
    _roundtrip(SimulationRequest, f.simulation_request())
    _roundtrip(DecisionState, f.decision_state())
    state = DiagnosisState(
        diagnosis_id="DX1",
        issue=f.issue(),
        hypotheses=[f.hypothesis()],
        evidence_ids=["E101"],
        root_causes=f.diagnosis_report().root_causes,
    )
    restored = DiagnosisState.model_validate(state.model_dump(mode="json"))
    assert restored == state


def test_business_action_union():
    adapter = TypeAdapter(BusinessAction)
    budget = adapter.validate_python(
        {"action_type": "adjust_ad_budget", "campaign_id": "C1", "change_pct": -0.2}
    )
    assert isinstance(budget, AdjustAdBudget)
    pause = adapter.validate_python({"action_type": "pause_campaign", "campaign_id": "C1"})
    assert isinstance(pause, PauseCampaign)
    replenish = adapter.validate_python({"action_type": "replenish", "sku_id": "S1", "quantity": 10})
    assert isinstance(replenish, ReplenishInventory)
    price = adapter.validate_python({"action_type": "adjust_price", "sku_id": "S1", "change_pct": 0.05})
    assert isinstance(price, AdjustPrice)
    listing = adapter.validate_python(
        {"action_type": "update_listing", "sku_id": "S1", "target_issue": "size"}
    )
    assert isinstance(listing, UpdateListing)


def test_business_action_bounds():
    with pytest.raises(ValidationError):
        AdjustAdBudget(action_type="adjust_ad_budget", campaign_id="C1", change_pct=0.5)
    with pytest.raises(ValidationError):
        AdjustPrice(action_type="adjust_price", sku_id="S1", change_pct=-0.2)
    with pytest.raises(ValidationError):
        ReplenishInventory(action_type="replenish", sku_id="S1", quantity=0)


def test_simulated_state_not_snapshot():
    sim = SimulatedBusinessState(
        simulation_id="SIM_1",
        simulated_day=3,
        source_snapshot_id="SNAP_184",
        expected_sales=12.5,
        expected_inventory=40.0,
        expected_revenue=Decimal("1200.00"),
        expected_profit=Decimal("300.00"),
    )
    restored = SimulatedBusinessState.model_validate(sim.model_dump(mode="json"))
    assert restored == sim
    assert not isinstance(sim, BusinessStateSnapshot)


def test_simulation_job_and_money_types():
    job = SimulationJob(
        job_id="J1",
        simulation_id="SIM_1",
        status="queued",
        submitted_at=datetime(2026, 9, 3, tzinfo=UTC),
    )
    restored = SimulationJob.model_validate(job.model_dump(mode="json"))
    assert restored.status == "queued"
    assert isinstance(f.sku().unit_cost, Decimal)
