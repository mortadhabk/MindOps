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

    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_model: str = Field(default="llama3.1:8b", alias="LLM_MODEL")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")

    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")

    email_api_key: str | None = Field(default=None, alias="EMAIL_API_KEY")
    email_from: str | None = Field(default=None, alias="EMAIL_FROM")
    # Sandbox Mailtrap (Email Testing) : e-mails capturés dans une boîte fictive, jamais
    # réellement délivrés — https://mailtrap.io/inboxes, onglet "Integration" > API.
    mailtrap_inbox_id: str | None = Field(default=None, alias="MAILTRAP_INBOX_ID")

    api_key: str | None = Field(default=None, alias="API_KEY")

    gating_policy: dict[str, str] = Field(
        default_factory=lambda: {"send_email": "require_validation"}, alias="GATING_POLICY"
    )
    gating_min_confidence: float = Field(default=0.8, alias="GATING_MIN_CONFIDENCE")

    embedding_provider: str = Field(default="local", alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(
        default="paraphrase-multilingual-MiniLM-L12-v2", alias="EMBEDDING_MODEL"
    )

    rag_chunk_max_tokens: int = Field(default=200, alias="RAG_CHUNK_MAX_TOKENS")
    rag_chunk_overlap: int = Field(default=20, alias="RAG_CHUNK_OVERLAP")
    rag_similarity_threshold: float = Field(default=0.2, alias="RAG_SIMILARITY_THRESHOLD")


@lru_cache
def get_settings() -> Settings:
    return Settings()
