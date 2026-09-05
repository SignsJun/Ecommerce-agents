from decimal import Decimal

from domain.business.snapshot import BusinessStateSnapshot
from domain.common import BusinessPolicyConfig
from domain.issue.models import Issue
from domain.strategy.actions import AdjustAdBudget, AdjustPrice, PauseCampaign, ReplenishInventory, UpdateListing
from domain.strategy.models import Strategy
from domain.strategy.validation import StrategyValidationResult, ValidationIssue
from services.strategy.allowed import allowed_actions


def _err(code: str, message: str, field: str | None = None) -> ValidationIssue:
    return ValidationIssue(code=code, field=field, message=message, severity="error")


def _warn(code: str, message: str, field: str | None = None) -> ValidationIssue:
    return ValidationIssue(code=code, field=field, message=message, severity="warning")


def validate_strategy(
    strategy: Strategy,
    snapshot: BusinessStateSnapshot,
    policy: BusinessPolicyConfig,
    issue: Issue,
) -> StrategyValidationResult:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    allowed = set(allowed_actions(issue.issue_type))
    sku_id = issue.entity_id
    paused: set[str] = set()
    adjusted: set[str] = set()
    prices: list[float] = []

    if strategy.based_on_snapshot_id != snapshot.snapshot_id or strategy.based_on_state_version != snapshot.version:
        errors.append(_err("SNAPSHOT_MISMATCH", "strategy snapshot does not match current snapshot"))

    if not strategy.actions:
        if strategy.strategy_type != "custom":
            errors.append(_err("EMPTY_ACTIONS", "non do-nothing strategy has no actions"))
        feasible = not errors
        return StrategyValidationResult(
            strategy_id=strategy.strategy_id,
            feasible=feasible,
            errors=errors,
            warnings=warnings,
            normalized_strategy=strategy.model_copy(update={"status": "validated"}) if feasible else None,
        )

    for i, action in enumerate(strategy.actions):
        field = f"actions[{i}]"
        if action.action_type not in allowed:
            errors.append(_err("DISALLOWED_ACTION", f"{action.action_type} not allowed", field))
            continue
        if isinstance(action, (AdjustAdBudget, PauseCampaign)):
            camp = snapshot.campaigns.get(action.campaign_id)
            if camp is None or camp.sku_id != sku_id:
                errors.append(_err("UNKNOWN_TARGET_ID", f"unknown campaign {action.campaign_id}", field))
            if isinstance(action, AdjustAdBudget):
                if action.change_pct < policy.ad_budget_change_min or action.change_pct > policy.ad_budget_change_max:
                    errors.append(_err("OUT_OF_BOUNDS", "ad budget change out of policy", field))
                adjusted.add(action.campaign_id)
                if action.change_pct <= -0.20:
                    warnings.append(_warn("HIGH_RISK_AD", "large ad budget change", field))
            else:
                paused.add(action.campaign_id)
                warnings.append(_warn("HIGH_RISK_PAUSE", "pause campaign", field))
        elif isinstance(action, ReplenishInventory):
            if action.sku_id not in snapshot.skus:
                errors.append(_err("UNKNOWN_TARGET_ID", f"unknown sku {action.sku_id}", field))
            elif action.sku_id != sku_id:
                errors.append(_err("UNKNOWN_TARGET_ID", f"sku {action.sku_id} is not the issue entity", field))
            else:
                sku = snapshot.skus[action.sku_id]
                cost = sku.unit_cost * Decimal(action.quantity)
                if cost > snapshot.store.cash_balance:
                    errors.append(_err("INSUFFICIENT_CASH", "replenish exceeds cash", field))
            warnings.append(_warn("HIGH_RISK_REPLENISH", "replenish", field))
        elif isinstance(action, AdjustPrice):
            if action.sku_id not in snapshot.skus or action.sku_id != sku_id:
                errors.append(_err("UNKNOWN_TARGET_ID", f"unknown sku {action.sku_id}", field))
            if action.change_pct < policy.price_change_min or action.change_pct > policy.price_change_max:
                errors.append(_err("OUT_OF_BOUNDS", "price change out of policy", field))
            prices.append(action.change_pct)
            warnings.append(_warn("HIGH_RISK_PRICE", "price change", field))
        elif isinstance(action, UpdateListing):
            if action.sku_id not in snapshot.skus or action.sku_id != sku_id:
                errors.append(_err("UNKNOWN_TARGET_ID", f"unknown sku {action.sku_id}", field))

    overlap = paused & adjusted
    if overlap:
        errors.append(_err("CONFLICT", f"pause and adjust on {sorted(overlap)[0]}"))
    if len(prices) >= 2 and any(a * b < 0 for a in prices for b in prices):
        errors.append(_err("CONFLICT", "opposing price changes"))

    feasible = not errors
    return StrategyValidationResult(
        strategy_id=strategy.strategy_id,
        feasible=feasible,
        errors=errors,
        warnings=warnings,
        normalized_strategy=strategy.model_copy(update={"status": "validated"}) if feasible else None,
    )
