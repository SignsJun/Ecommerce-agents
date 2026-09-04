from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from agents.llm.client import LLMUnavailable

T = TypeVar("T", bound=BaseModel)


class FakeLLM:
    def __init__(self, responder: Callable[[str, str, type[BaseModel]], BaseModel]) -> None:
        self.model_name = "fake"
        self._responder = responder

    def complete(self, system: str, user: str, schema: type[T]) -> T:
        out = self._responder(system, user, schema)
        if isinstance(out, Exception):
            raise out
        if not isinstance(out, schema):
            raise LLMUnavailable("fake schema mismatch")
        return out
