import json
from pathlib import Path

from domain.diagnosis.report import DiagnosisReport
from domain.issue.models import Issue
from services.strategy.allowed import allowed_actions
from tools.diagnosis.base import ToolContext

PROMPT_VERSION = "main_decision/system_v1"
_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "main_decision" / "system_v1.md"


def load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_plan_context(issue: Issue, report: DiagnosisReport, ctx: ToolContext) -> str:
    snap = ctx.snapshot()
    sku_id = issue.entity_id
    campaigns = [
        {
            "campaign_id": c.campaign_id,
            "roas_7d": c.roas_7d,
            "daily_budget": str(c.daily_budget),
            "status": c.status,
        }
        for c in snap.campaigns.values()
        if c.sku_id == sku_id
    ]
    sku = snap.skus.get(sku_id)
    body = {
        "task": "Write StrategyPlanDraft JSON only. Copy target_id from campaign_ids or sku_id. intensity is mild|standard|strong. Do not write percents or quantities.",
        "issue": {
            "issue_id": issue.issue_id,
            "issue_type": issue.issue_type.value,
            "entity_id": sku_id,
            "severity": issue.severity,
        },
        "diagnosis": {
            "status": report.status,
            "overall_confidence": report.overall_confidence,
            "root_causes": [{"cause_type": c.cause_type, "confidence": c.confidence} for c in report.root_causes],
            "unresolved_causes": list(report.unresolved_causes),
        },
        "sku_id": sku_id,
        "campaign_ids": [c["campaign_id"] for c in campaigns],
        "campaigns": campaigns,
        "inventory_available": sku.inventory_available if sku else None,
        "units_sold_7d": sku.units_sold_7d if sku else None,
        "allowed_action_types": list(allowed_actions(issue.issue_type)),
    }
    return json.dumps(body, ensure_ascii=False, default=str)
