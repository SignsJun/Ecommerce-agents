from agents.decision.schema import LLMActionDraft, LLMStrategyDraft, StrategyPlanDraft
from domain.business.snapshot import BusinessStateSnapshot
from domain.diagnosis.report import DiagnosisReport
from domain.enums import IssueType
from domain.issue.models import Issue


def _campaign(snapshot: BusinessStateSnapshot, sku_id: str) -> str | None:
    camps = [c for c in snapshot.campaigns.values() if c.sku_id == sku_id]
    if not camps:
        return None
    return min(camps, key=lambda c: c.roas_7d if c.roas_7d is not None else 0.0).campaign_id


def rule_plan_draft(issue: Issue, report: DiagnosisReport, snapshot: BusinessStateSnapshot) -> StrategyPlanDraft:
    sku_id = issue.entity_id
    cid = _campaign(snapshot, sku_id)
    causes = {c.cause_type for c in report.root_causes}
    rows: list[LLMStrategyDraft] = []
    if issue.issue_type in {IssueType.PROFIT_EROSION, IssueType.AD_INEFFICIENCY}:
        if cid and (not causes or "ad_efficiency" in causes or "campaign_mix" in causes):
            rows.append(
                LLMStrategyDraft(
                    name="Conservative ads",
                    strategy_type="conservative",
                    objective="cut inefficient ads",
                    actions=[LLMActionDraft(action_type="adjust_ad_budget", target_id=cid, intensity="strong")],
                )
            )
            rows.append(
                LLMStrategyDraft(
                    name="Balanced ads",
                    strategy_type="balanced",
                    objective="moderate ad cut",
                    actions=[LLMActionDraft(action_type="adjust_ad_budget", target_id=cid, intensity="standard")],
                )
            )
        if issue.issue_type == IssueType.PROFIT_EROSION and (not causes or "refunds" in causes):
            listing = LLMActionDraft(action_type="update_listing", target_id=sku_id, intensity="standard")
            if rows:
                bal = rows[-1]
                rows[-1] = LLMStrategyDraft(
                    name=bal.name,
                    strategy_type=bal.strategy_type,
                    objective=bal.objective,
                    actions=[*bal.actions, listing],
                )
            else:
                rows.append(
                    LLMStrategyDraft(
                        name="Fix listing",
                        strategy_type="conservative",
                        objective="refunds",
                        actions=[listing],
                    )
                )
            rows.append(
                LLMStrategyDraft(
                    name="Growth listing",
                    strategy_type="growth",
                    objective="fix listing keep spend",
                    actions=[listing],
                )
            )
    elif issue.issue_type == IssueType.STOCKOUT_RISK:
        rows = [
            LLMStrategyDraft(
                name="Conservative replenish",
                strategy_type="conservative",
                actions=[LLMActionDraft(action_type="replenish", target_id=sku_id, intensity="mild")],
            ),
            LLMStrategyDraft(
                name="Balanced replenish",
                strategy_type="balanced",
                actions=[LLMActionDraft(action_type="replenish", target_id=sku_id, intensity="standard")],
            ),
            LLMStrategyDraft(
                name="Growth replenish",
                strategy_type="growth",
                actions=[LLMActionDraft(action_type="replenish", target_id=sku_id, intensity="strong")],
            ),
        ]
    elif issue.issue_type == IssueType.EXCESS_INVENTORY:
        if cid:
            rows.append(
                LLMStrategyDraft(
                    name="Cut ads",
                    strategy_type="conservative",
                    actions=[LLMActionDraft(action_type="adjust_ad_budget", target_id=cid, intensity="strong")],
                )
            )
        rows.append(
            LLMStrategyDraft(
                name="Balanced markdown",
                strategy_type="balanced",
                actions=[LLMActionDraft(action_type="adjust_price", target_id=sku_id, intensity="mild")],
            )
        )
        rows.append(
            LLMStrategyDraft(
                name="Growth markdown",
                strategy_type="growth",
                actions=[LLMActionDraft(action_type="adjust_price", target_id=sku_id, intensity="strong")],
            )
        )
    return StrategyPlanDraft(strategies=rows)
