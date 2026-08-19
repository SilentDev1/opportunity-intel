from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./opportunity_intel.db"
    admin_api_key: str = ""
    artifact_root: Path = Path("data/artifacts")
    http_user_agent: str = "OpportunityIntel/0.1 (+contact@example.com)"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
