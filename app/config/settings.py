from datetime import date
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from domain.common import BusinessPolicyConfig


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ECOM_", env_file=".env", extra="ignore")

    timezone: str = "America/Sao_Paulo"
    data_dir: Path = Path("data/raw/olist")
    store_seller_id: str | None = None
    top_sku_count: int = 50
    as_of_date: date | None = None
    store_id: str = "STORE_001"
    store_name: str = "WorkBuddy Demo Store"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str | None = None
    llm_model: str = "deepseek-chat"
    decisions_dir: Path = Path("data/decisions")


def default_policy() -> BusinessPolicyConfig:
    return BusinessPolicyConfig()
