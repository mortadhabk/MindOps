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

    @property
    def psycopg_database_url(self) -> str:
        # Le checkpointer LangGraph Postgres (app/agent/memory.py) parle psycopg3, pas asyncpg —
        # même base, juste un DSN sans le qualificatif de driver SQLAlchemy.
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")

    # Valeurs de démarrage avant toute personnalisation depuis l'onglet Paramètres (Epic 9,
    # interface-first) : le fournisseur/modèle/clé effectifs vivent ensuite dans `app_settings`
    # (base de données, clé chiffrée) — voir app/agent/settings.py.
    llm_provider_kind: str = Field(default="ollama", alias="LLM_PROVIDER_KIND")
    llm_model: str = Field(default="llama3.1:8b", alias="LLM_MODEL")
    llm_base_url: str = Field(default="http://localhost:11434", alias="LLM_BASE_URL")
    # Clé de chiffrement symétrique (Fernet) pour les secrets saisis depuis l'UI (ex : clé API
    # d'un modèle distant) — le seul secret qui doit encore vivre dans .env. Générer avec :
    # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    settings_encryption_key: str | None = Field(default=None, alias="SETTINGS_ENCRYPTION_KEY")

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
