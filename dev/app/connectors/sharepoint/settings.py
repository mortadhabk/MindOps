from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.config import SharePointCredentials, get_settings
from app.core.crypto import decrypt, encrypt
from app.settings import store
from app.settings.registry import SettingsSection, register_section

SECTION_KEY = "sharepoint_credentials"
MASKED_SECRET = "••••••••"
PASSWORD_FIELDS = {"sharepoint_client_secret"}


class SharePointCredentialsSchema(BaseModel):
    """Éditable depuis Admin > Connecteurs — remplace .env pour ces valeurs une fois enregistrées
    (voir `_get_effective`, qui retombe sur .env tant qu'aucun override n'existe)."""

    model_config = ConfigDict(extra="forbid")

    sharepoint_tenant_id: str = Field(default="", description="Azure AD — Directory (tenant) ID")
    sharepoint_client_id: str = Field(default="", description="Azure AD — Application (client) ID")
    sharepoint_client_secret: str = Field(
        default="",
        json_schema_extra={"format": "password"},
        description="Azure AD — secret client",
    )


def _bootstrap_defaults() -> dict[str, str]:
    settings = get_settings()
    return {
        "sharepoint_tenant_id": settings.sharepoint_tenant_id or "",
        "sharepoint_client_id": settings.sharepoint_client_id or "",
        "sharepoint_client_secret": settings.sharepoint_client_secret or "",
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
        display_name="SharePoint",
        description=(
            "Identifiants Azure AD (client credentials) pour le connecteur SharePoint, "
            "chiffrés avant stockage."
        ),
        schema=SharePointCredentialsSchema,
        effect="immediate",
        get_current_values=_get_current_values,
        pre_store=_pre_store,
    )
)


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
