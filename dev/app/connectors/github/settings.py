from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.core.crypto import decrypt, encrypt
from app.settings import store
from app.settings.registry import SettingsSection, register_section

SECTION_KEY = "github_credentials"
MASKED_SECRET = "••••••••"


class GitHubCredentialsSchema(BaseModel):
    """Éditable depuis Admin > Connecteurs — remplace .env pour cette valeur une fois enregistrée
    (voir `_get_effective`, qui retombe sur .env tant qu'aucun override n'existe)."""

    model_config = ConfigDict(extra="forbid")

    github_token: str = Field(
        default="",
        json_schema_extra={"format": "password"},
        description="Token GitHub (connecteur Issues) — inutile pour un dépôt public",
    )


def _get_effective() -> dict[str, str]:
    override = store.get_override(SECTION_KEY) or {}
    default = get_settings().github_token or ""
    if "github_token" not in override:
        return {"github_token": default}
    raw = override["github_token"]
    return {"github_token": decrypt(raw) if raw else raw}


def _get_current_values() -> dict[str, Any]:
    value = _get_effective()["github_token"]
    return {"github_token": MASKED_SECRET if value else ""}


def _pre_store(validated: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    existing = existing or {}
    submitted = validated.get("github_token", "")
    if submitted:
        return {"github_token": encrypt(submitted)}
    if existing.get("github_token"):
        return {"github_token": existing["github_token"]}
    return {"github_token": ""}


register_section(
    SettingsSection(
        key=SECTION_KEY,
        display_name="GitHub",
        description="Token d'accès pour le connecteur GitHub Issues, chiffré avant stockage.",
        schema=GitHubCredentialsSchema,
        effect="immediate",
        get_current_values=_get_current_values,
        pre_store=_pre_store,
    )
)


def get_github_token() -> str | None:
    return _get_effective()["github_token"] or None
