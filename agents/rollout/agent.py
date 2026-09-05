from agents.llm.client import LLMClient, LLMUnavailable
from agents.rollout.context import PROMPT_VERSION, build_rollout_context, load_system_prompt
from agents.rollout.policy import rule_decide
from agents.rollout.schema import RolloutDecision
from domain.simulation.envelope import RolloutObservation

AGENT_VERSION = "rollout-v1"


class RolloutPolicyAgent:
    def __init__(self, llm: LLMClient | None = None, *, roas_min: float = 2.0, cover_min: float = 7.0) -> None:
        self.llm = llm
        self.roas_min = roas_min
        self.cover_min = cover_min
        self.cache: dict[tuple, RolloutDecision] = {}
        self.decide_calls = 0
        self.llm_calls = 0
        self.prompt_version = PROMPT_VERSION

    def _key(self, obs: RolloutObservation) -> tuple:
        return (
            obs.day,
            round(obs.roas or 0.0, 1),
            int(obs.inventory_cover or 0),
            obs.remaining_interventions,
            obs.can_act,
            tuple(obs.allowed_actions),
        )

    def decide(self, obs: RolloutObservation) -> RolloutDecision:
        self.decide_calls += 1
        key = self._key(obs)
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        decision = self._fresh(obs)
        self.cache[key] = decision
        return decision

    def _fresh(self, obs: RolloutObservation) -> RolloutDecision:
        if self.llm is None:
            return rule_decide(obs, roas_min=self.roas_min, cover_min=self.cover_min)
        try:
            self.llm_calls += 1
            return self.llm.complete(load_system_prompt(), build_rollout_context(obs), RolloutDecision)
        except LLMUnavailable:
            return rule_decide(obs, roas_min=self.roas_min, cover_min=self.cover_min)
