import json
from pathlib import Path

from domain.simulation.envelope import RolloutObservation

PROMPT_VERSION = "rollout/system_v1"
_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "rollout" / "system_v1.md"


def load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def build_rollout_context(obs: RolloutObservation) -> str:
    body = {
        "task": "Choose one RolloutDecision. Prefer noop. Do not write percents, quantities, or profit.",
        "day": obs.day,
        "profit_margin": obs.profit_margin,
        "roas": obs.roas,
        "inventory_cover": obs.inventory_cover,
        "refund_rate": obs.refund_rate,
        "current_price": str(obs.current_price),
        "current_ad_budget": str(obs.current_ad_budget),
        "inventory": obs.inventory,
        "previous_actions": list(obs.previous_actions),
        "days_since_last_action": obs.days_since_last_action,
        "remaining_interventions": obs.remaining_interventions,
        "allowed_actions": list(obs.allowed_actions),
        "allowed_targets": list(obs.allowed_targets),
        "can_act": obs.can_act,
    }
    return json.dumps(body, ensure_ascii=False, default=str)
