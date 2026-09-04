from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(Exception):
    pass


class LLMClient(Protocol):
    model_name: str

    def complete(self, system: str, user: str, schema: type[T]) -> T: ...
