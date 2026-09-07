from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.config import JiraCloudCredentials, SharePointCredentials, get_settings
from app.core.crypto import decrypt, encrypt
from app.settings import store
from app.settings.registry import SettingsSection, register_section

SECTION_KEY = "connector_credentials"
MASKED_SECRET = "••••••••"

# Champs chiffrés avant stockage (Epic 9, même contrat que agent.settings) — les autres champs
# (tenant_id, client_id, email...) ne sont pas des secrets à eux seuls, stockés en clair comme le
# reste d'un AppSetting.value (JSON), inutile de les chiffrer.
PASSWORD_FIELDS = {
    "github_token",
    "sharepoint_client_secret",
    "jira_cloud_api_token",
    "jira_server_token",
}


class ConnectorCredentialsSchema(BaseModel):
    """Identifiants des connecteurs externes (GitHub, SharePoint, Jira), éditables depuis l'onglet
    Paramètres — remplace .env pour ces valeurs une fois enregistrées ici (voir `_get_effective`,
    qui retombe sur .env tant qu'aucun override n'existe). Laisser un champ chiffré vide au
    moment de sauvegarder conserve la valeur déjà enregistrée, jamais ne l'efface."""

    model_config = ConfigDict(extra="forbid")

    github_token: str = Field(
        default="",
        json_schema_extra={"format": "password"},
        description="Token GitHub (connecteur Issues) — inutile pour un dépôt public",
    )

    sharepoint_tenant_id: str = Field(default="", description="Azure AD — Directory (tenant) ID")
    sharepoint_client_id: str = Field(default="", description="Azure AD — Application (client) ID")
    sharepoint_client_secret: str = Field(
        default="", json_schema_extra={"format": "password"}, description="Azure AD — secret client"
    )

    jira_cloud_email: str = Field(default="", description="Jira Cloud — email du compte")
    jira_cloud_api_token: str = Field(
        default="", json_schema_extra={"format": "password"}, description="Jira Cloud — API token"
    )
    jira_server_token: str = Field(
        default="",
        json_schema_extra={"format": "password"},
        description="Jira Server/Data Center — Personal Access Token",
    )


def _bootstrap_defaults() -> dict[str, str]:
    """Valeurs `.env` — utilisées tant qu'aucun override n'a jamais été enregistré depuis l'UI,
    même logique que `LLM_PROVIDER_KIND`/`LLM_MODEL`/`LLM_BASE_URL` pour l'agent (Epic 9)."""
    settings = get_settings()
    return {
        "github_token": settings.github_token or "",
        "sharepoint_tenant_id": settings.sharepoint_tenant_id or "",
        "sharepoint_client_id": settings.sharepoint_client_id or "",
        "sharepoint_client_secret": settings.sharepoint_client_secret or "",
        "jira_cloud_email": settings.jira_cloud_email or "",
        "jira_cloud_api_token": settings.jira_cloud_api_token or "",
        "jira_server_token": settings.jira_server_token or "",
    }


def _get_effective() -> dict[str, str]:
    """Valeurs réellement utilisées à l'exécution — override déchiffré si présent, sinon .env.
    Jamais exposées telles quelles par l'API (voir `_get_current_values`, qui masque les
    champs secrets avant de les renvoyer)."""
    override = store.get_override(SECTION_KEY) or {}
    defaults = _bootstrap_defaults()
    result: dict[str, str] = {}
    for key, default in defaults.items():
        if key not in override:
            result[key] = default
            continue
        raw = override[key]
        result[key] = decrypt(raw) if key in PASSWORD_FIELDS and raw else raw
    return result


def _get_current_values() -> dict[str, Any]:
    values = _get_effective()
    for key in PASSWORD_FIELDS:
        values[key] = MASKED_SECRET if values[key] else ""
    return values


def _pre_store(validated: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    existing = existing or {}
    result = dict(validated)
    for key in PASSWORD_FIELDS:
        submitted = validated.get(key, "")
        if submitted:
            result[key] = encrypt(submitted)
        elif existing.get(key):
            result[key] = existing[key]  # conserve la valeur déjà chiffrée
        else:
            result[key] = ""
    return result


register_section(
    SettingsSection(
        key=SECTION_KEY,
        display_name="Connecteurs — identifiants",
        description=(
            "Identifiants des connecteurs externes (GitHub, SharePoint, Jira), chiffrés avant "
            "stockage. Remplace .env pour ces valeurs dès qu'elles sont enregistrées ici — "
            "réinitialiser une section revient à .env. S'applique immédiatement, sans "
            "redémarrage : chaque synchronisation relit la valeur effective courante."
        ),
        schema=ConnectorCredentialsSchema,
        effect="immediate",
        get_current_values=_get_current_values,
        pre_store=_pre_store,
    )
)


# --- Accesseurs utilisés par les connecteurs (github/sharepoint/jira) au moment de l'exécution ---
# Un seul alias "default" pour l'instant, comme les .env qu'ils remplacent — le paramètre `alias`
# est conservé pour rester compatible avec `credential_alias` (Epic 8/10) si plusieurs jeux
# d'identifiants par connecteur sont introduits plus tard.


def get_github_token() -> str | None:
    return _get_effective()["github_token"] or None


def get_sharepoint_credentials(alias: str) -> SharePointCredentials | None:
    if alias != "default":
        return None
    values = _get_effective()
    if not (
        values["sharepoint_tenant_id"]
        and values["sharepoint_client_id"]
        and values["sharepoint_client_secret"]
    ):
        return None
    return SharePointCredentials(
        tenant_id=values["sharepoint_tenant_id"],
        client_id=values["sharepoint_client_id"],
        client_secret=values["sharepoint_client_secret"],
    )


def get_jira_cloud_credentials(alias: str) -> JiraCloudCredentials | None:
    if alias != "default":
        return None
    values = _get_effective()
    if not (values["jira_cloud_email"] and values["jira_cloud_api_token"]):
        return None
    return JiraCloudCredentials(
        email=values["jira_cloud_email"], api_token=values["jira_cloud_api_token"]
    )


def get_jira_server_token(alias: str) -> str | None:
    if alias != "default":
        return None
    return _get_effective()["jira_server_token"] or None
