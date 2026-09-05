from dataclasses import dataclass
from uuid import uuid4

from agents.decision.schema import LLMStrategyDraft
from domain.business.snapshot import BusinessStateSnapshot
from domain.common import BusinessPolicyConfig
from domain.diagnosis.report import DiagnosisReport
from domain.issue.models import Issue
from domain.strategy.actions import AdjustAdBudget, AdjustPrice, BusinessAction, PauseCampaign, ReplenishInventory, UpdateListing
from domain.strategy.models import Strategy


@dataclass(frozen=True)
class MaterializedStrategy:
    strategy: Strategy
    intensities: tuple[str, ...]


def _ad_pct(intensity: str, policy: BusinessPolicyConfig) -> float:
    if intensity == "strong":
        return policy.ad_budget_change_min
    if intensity == "mild":
        return max(policy.ad_budget_change_min, -0.05)
    return max(policy.ad_budget_change_min, -0.10)


def _price_pct(intensity: str, policy: BusinessPolicyConfig) -> float:
    if intensity == "strong":
        return policy.price_change_min
    if intensity == "mild":
        return max(policy.price_change_min, -0.03)
    return max(policy.price_change_min, -0.08)


def _replenish_qty(snapshot: BusinessStateSnapshot, sku_id: str, intensity: str, policy: BusinessPolicyConfig) -> int:
    sku = snapshot.skus[sku_id]
    daily = sku.units_sold_7d / 7
    if intensity == "mild":
        days = policy.target_cover_days_min
    elif intensity == "strong":
        days = policy.target_cover_days_max
    else:
        days = (policy.target_cover_days_min + policy.target_cover_days_max) // 2
    needed = int(daily * days) - sku.inventory_available - sku.incoming_inventory
    qty = max(1, needed)
    if sku.unit_cost > 0:
        cap = int(snapshot.store.cash_balance / sku.unit_cost)
        if cap > 0:
            qty = min(qty, cap)
    return qty


def _listing_issue(report: DiagnosisReport) -> str:
    for c in report.root_causes:
        if c.cause_type in {"refunds", "quality", "size"}:
            return c.cause_type
    return "listing"


def materialize_draft(
    draft: LLMStrategyDraft,
    issue: Issue,
    snapshot: BusinessStateSnapshot,
    policy: BusinessPolicyConfig,
    report: DiagnosisReport,
    *,
    strategy_id: str | None = None,
) -> MaterializedStrategy:
    sku_id = issue.entity_id
    actions: list[BusinessAction] = []
    intensities: list[str] = []
    for item in draft.actions:
        intensity = item.intensity
        if item.action_type == "adjust_ad_budget":
            actions.append(
                AdjustAdBudget(
                    action_type="adjust_ad_budget",
                    campaign_id=item.target_id,
                    change_pct=_ad_pct(intensity, policy),
                )
            )
        elif item.action_type == "pause_campaign":
            actions.append(PauseCampaign(action_type="pause_campaign", campaign_id=item.target_id))
        elif item.action_type == "replenish":
            actions.append(
                ReplenishInventory(
                    action_type="replenish",
                    sku_id=item.target_id,
                    quantity=_replenish_qty(snapshot, item.target_id, intensity, policy) if item.target_id in snapshot.skus else 1,
                )
            )
        elif item.action_type == "adjust_price":
            actions.append(
                AdjustPrice(action_type="adjust_price", sku_id=item.target_id, change_pct=_price_pct(intensity, policy))
            )
        elif item.action_type == "update_listing":
            actions.append(
                UpdateListing(action_type="update_listing", sku_id=item.target_id, target_issue=_listing_issue(report))
            )
        else:
            continue
        intensities.append(intensity)
    return MaterializedStrategy(
        strategy=Strategy(
            strategy_id=strategy_id or f"ST_{uuid4().hex[:10]}",
            issue_id=issue.issue_id,
            name=draft.name,
            strategy_type=draft.strategy_type,
            objective=draft.objective or draft.name,
            actions=actions,
            assumptions=[],
            horizon_days=policy.impact_horizon_days,
            based_on_snapshot_id=snapshot.snapshot_id,
            based_on_state_version=snapshot.version,
            status="draft",
        ),
        intensities=tuple(intensities),
    )


def do_nothing_strategy(issue: Issue, snapshot: BusinessStateSnapshot, policy: BusinessPolicyConfig) -> MaterializedStrategy:
    return MaterializedStrategy(
        strategy=Strategy(
            strategy_id="ST_do_nothing",
            issue_id=issue.issue_id,
            name="Do Nothing",
            strategy_type="custom",
            objective="baseline",
            actions=[],
            assumptions=[],
            horizon_days=policy.impact_horizon_days,
            based_on_snapshot_id=snapshot.snapshot_id,
            based_on_state_version=snapshot.version,
            status="draft",
        ),
        intensities=(),
    )
