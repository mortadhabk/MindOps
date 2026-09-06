from typing import Any

from pydantic import BaseModel, Field

from app.agent.providers.registry import list_provider_kinds
from app.config import get_settings
from app.core.crypto import decrypt, encrypt
from app.settings import store
from app.settings.registry import SettingsSection, register_section

SECTION_KEY = "agent"
MASKED_SECRET = "••••••••"


class AgentSettingsSchema(BaseModel):
    llm_provider_kind: str = Field(
        description="Famille de client — voir app/agent/providers/",
        examples=["ollama", "openai_compatible", "anthropic"],
    )
    llm_model: str = Field(
        description="Nom du modèle chez le fournisseur choisi",
        examples=["llama3.1:8b", "gpt-4o", "deepseek-chat", "moonshot-v1-8k", "claude-opus-5"],
    )
    base_url: str = Field(
        default="",
        description=(
            "URL du serveur — requis pour 'ollama' et 'openai_compatible', ignoré pour "
            "'anthropic'"
        ),
        examples=["http://localhost:11434", "https://api.deepseek.com/v1"],
    )
    api_key: str = Field(
        default="",
        json_schema_extra={"format": "password"},
        description=(
            "Clé API — inutile pour 'ollama'. Laisser vide pour conserver la clé déjà "
            "enregistrée : jamais réaffichée en clair une fois sauvegardée."
        ),
    )


def get_effective_agent_settings() -> AgentSettingsSchema:
    """Valeurs réellement utilisées par `get_llm_client()` — `api_key` en clair, jamais exposée
    telle quelle par l'API (voir `_get_current_values`, qui la masque avant de la renvoyer)."""
    base = get_settings()
    override = store.get_override(SECTION_KEY) or {}
    encrypted_key = override.get("api_key", "")
    return AgentSettingsSchema.model_construct(
        llm_provider_kind=override.get("llm_provider_kind", base.llm_provider_kind),
        llm_model=override.get("llm_model", base.llm_model),
        base_url=override.get("base_url", base.llm_base_url),
        api_key=decrypt(encrypted_key) if encrypted_key else "",
    )


def _get_current_values() -> dict[str, Any]:
    values = get_effective_agent_settings().model_dump()
    values["api_key"] = MASKED_SECRET if values["api_key"] else ""
    return values


def _get_config_schema() -> dict[str, Any]:
    schema = AgentSettingsSchema.model_json_schema()
    schema["properties"]["llm_provider_kind"]["enum"] = [
        info.kind for info in list_provider_kinds()
    ]
    return schema


def _pre_store(validated: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    """Chiffre une clé API nouvellement saisie ; un champ soumis vide conserve la clé déjà
    stockée plutôt que de l'effacer — c'est le contrat "vide = ne pas changer" côté formulaire."""
    submitted_key = validated.get("api_key", "")
    if submitted_key:
        validated["api_key"] = encrypt(submitted_key)
    elif existing and existing.get("api_key"):
        validated["api_key"] = existing["api_key"]
    else:
        validated["api_key"] = ""
    return validated


def _apply(_values: dict[str, Any]) -> None:
    # get_llm_client() est en cache (@lru_cache) car elle construit un client réel, pas juste de
    # la config — l'invalider ici force sa reconstruction avec les nouvelles valeurs au prochain
    # message, sans redémarrer l'API. Import local : évite un import circulaire au chargement du
    # module (agent.llm_client importe agent.settings).
    from app.agent.llm_client import get_llm_client

    get_llm_client.cache_clear()


register_section(
    SettingsSection(
        key=SECTION_KEY,
        display_name="Agent / LLM",
        description=(
            "Choisir directement le modèle à utiliser (local ou distant) depuis l'interface — "
            "la clé API est chiffrée avant stockage, jamais réaffichée en clair. S'applique au "
            "prochain message, pas au tour de conversation en cours."
        ),
        schema=AgentSettingsSchema,
        effect="deferred",
        get_current_values=_get_current_values,
        get_config_schema=_get_config_schema,
        pre_store=_pre_store,
        apply=_apply,
    )
)
