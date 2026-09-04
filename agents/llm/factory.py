from agents.llm.client import LLMUnavailable
from agents.llm.openai_compat import OpenAICompatClient
from app.config.settings import Settings


def llm_from_settings(settings: Settings) -> OpenAICompatClient:
    if not settings.llm_api_key:
        raise LLMUnavailable("missing ECOM_LLM_API_KEY")
    return OpenAICompatClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
    )
