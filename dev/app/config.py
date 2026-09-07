from functools import lru_cache
from typing import NamedTuple

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SharePointCredentials(NamedTuple):
    tenant_id: str
    client_id: str
    client_secret: str


class JiraCloudCredentials(NamedTuple):
    email: str
    api_token: str


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

    # Connecteur SharePoint (Microsoft Graph API, app-only / client credentials) — un seul jeu
    # d'identifiants pour l'instant, résolu sous l'alias "default" (voir
    # app/connectors/sharepoint/schemas.py, champ credential_alias). Nécessite une App
    # Registration Azure AD avec la permission d'application Sites.Selected (recommandé, accès
    # limité au(x) site(s) explicitement autorisé(s) — voir README pour la procédure) ou
    # Sites.Read.All (plus large, plus simple à mettre en place).
    sharepoint_tenant_id: str | None = Field(default=None, alias="SHAREPOINT_TENANT_ID")
    sharepoint_client_id: str | None = Field(default=None, alias="SHAREPOINT_CLIENT_ID")
    sharepoint_client_secret: str | None = Field(default=None, alias="SHAREPOINT_CLIENT_SECRET")

    @property
    def sharepoint_credentials(self) -> dict[str, SharePointCredentials]:
        if not (
            self.sharepoint_tenant_id
            and self.sharepoint_client_id
            and self.sharepoint_client_secret
        ):
            return {}
        return {
            "default": SharePointCredentials(
                tenant_id=self.sharepoint_tenant_id,
                client_id=self.sharepoint_client_id,
                client_secret=self.sharepoint_client_secret,
            )
        }

    # Connecteur Jira (Epic 10) — deux jeux d'identifiants distincts selon `deployment_type`
    # (voir app/connectors/jira/schemas.py) : Jira Cloud s'authentifie par email + API token
    # (Basic Auth), Jira Server/Data Center par Personal Access Token (Bearer). Un seul alias
    # "default" par déploiement pour l'instant, même logique que sharepoint_credentials.
    jira_cloud_email: str | None = Field(default=None, alias="JIRA_CLOUD_EMAIL")
    jira_cloud_api_token: str | None = Field(default=None, alias="JIRA_CLOUD_API_TOKEN")
    jira_server_token: str | None = Field(default=None, alias="JIRA_SERVER_TOKEN")

    @property
    def jira_cloud_credentials(self) -> dict[str, JiraCloudCredentials]:
        if not (self.jira_cloud_email and self.jira_cloud_api_token):
            return {}
        return {
            "default": JiraCloudCredentials(
                email=self.jira_cloud_email, api_token=self.jira_cloud_api_token
            )
        }

    @property
    def jira_server_credentials(self) -> dict[str, str]:
        if not self.jira_server_token:
            return {}
        return {"default": self.jira_server_token}

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
    # Cross-encoder de reranking (app/rag/reranking) — multilingue (mMARCO) pour rester cohérent
    # avec l'embedding multilingue ci-dessus ; réordonne les candidats de la recherche vectorielle,
    # n'affecte jamais leur score de similarité affiché (voir app/rag/retriever.py).
    reranker_model: str = Field(
        default="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", alias="RERANKER_MODEL"
    )

    rag_chunk_max_tokens: int = Field(default=200, alias="RAG_CHUNK_MAX_TOKENS")
    rag_chunk_overlap: int = Field(default=20, alias="RAG_CHUNK_OVERLAP")
    rag_similarity_threshold: float = Field(default=0.2, alias="RAG_SIMILARITY_THRESHOLD")
    rag_rerank_enabled: bool = Field(default=True, alias="RAG_RERANK_ENABLED")


@lru_cache
def get_settings() -> Settings:
    return Settings()
