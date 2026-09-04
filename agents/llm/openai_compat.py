import json
import re
import urllib.error
import urllib.request
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from agents.llm.client import LLMUnavailable

T = TypeVar("T", bound=BaseModel)


def _candidate_urls(base_url: str) -> list[str]:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return [base]
    if base.endswith("/v1"):
        return [base + "/chat/completions"]
    return [base + "/v1/chat/completions", base + "/chat/completions"]


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


class OpenAICompatClient:
    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 90) -> None:
        if not api_key:
            raise LLMUnavailable("missing api key")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model
        self.timeout = timeout

    def complete(self, system: str, user: str, schema: type[T]) -> T:
        schema_txt = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        sys_msg = system + "\nJSON schema:\n" + schema_txt
        last_err = "unavailable"
        for _ in range(2):
            try:
                raw = self._chat(sys_msg, user)
                return schema.model_validate_json(_strip_fence(raw))
            except (LLMUnavailable, ValidationError, json.JSONDecodeError, urllib.error.URLError, TimeoutError) as exc:
                last_err = str(exc)
        raise LLMUnavailable(last_err)

    def _chat(self, system: str, user: str) -> str:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_code = 0
        for url in _candidate_urls(self.base_url):
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                exc.read()
                last_code = exc.code
                if exc.code != 404:
                    raise LLMUnavailable(f"http {exc.code}") from None
        else:
            raise LLMUnavailable(f"http {last_code or 404}")
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise LLMUnavailable("bad llm response") from None
        if not content:
            raise LLMUnavailable("empty llm content")
        return content
