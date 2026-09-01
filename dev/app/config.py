from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="ai-agent-poc", alias="APP_NAME")
    environment: str = Field(default="local", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    debug: bool = Field(default=False, alias="DEBUG")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent_poc",
        alias="DATABASE_URL",
    )

    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_model: str = Field(default="claude-sonnet-5", alias="LLM_MODEL")

    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")

    email_api_key: str | None = Field(default=None, alias="EMAIL_API_KEY")
    email_from: str | None = Field(default=None, alias="EMAIL_FROM")

    api_key: str | None = Field(default=None, alias="API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
