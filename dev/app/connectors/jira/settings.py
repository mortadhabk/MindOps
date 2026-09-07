from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.config import JiraCloudCredentials, get_settings
from app.core.crypto import decrypt, encrypt
from app.settings import store
from app.settings.registry import SettingsSection, register_section

SECTION_KEY = "jira_credentials"
MASKED_SECRET = "••••••••"
PASSWORD_FIELDS = {"jira_cloud_api_token", "jira_server_token"}


class JiraCredentialsSchema(BaseModel):
    """Éditable depuis Admin > Connecteurs — remplace .env pour ces valeurs une fois enregistrées
    (voir `_get_effective`, qui retombe sur .env tant qu'aucun override n'existe). Les deux
    déploiements (Cloud/Server) partagent une seule section : c'est un seul connecteur Jira, la
    distinction se fait déjà via `deployment_type` dans la configuration de chaque instance."""

    model_config = ConfigDict(extra="forbid")

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
    settings = get_settings()
    return {
        "jira_cloud_email": settings.jira_cloud_email or "",
        "jira_cloud_api_token": settings.jira_cloud_api_token or "",
        "jira_server_token": settings.jira_server_token or "",
    }


def _get_effective() -> dict[str, str]:
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
            result[key] = existing[key]
        else:
            result[key] = ""
    return result


register_section(
    SettingsSection(
        key=SECTION_KEY,
        display_name="Jira",
        description=(
            "Identifiants Jira Cloud (email + API token) et/ou Jira Server/Data Center (Personal "
            "Access Token), chiffrés avant stockage — selon les instances configurées dans le "
            "Studio."
        ),
        schema=JiraCredentialsSchema,
        effect="immediate",
        get_current_values=_get_current_values,
        pre_store=_pre_store,
    )
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
