from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExperimentKind = Literal["stress", "sensitivity", "stop"]


class ExperimentChoice(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    kind: ExperimentKind = "stop"
    name: str = ""
    strategy_ids: list[str] = Field(default_factory=list)
