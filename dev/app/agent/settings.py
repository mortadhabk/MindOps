from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.agent.providers.catalog import get_vendor, list_vendors
from app.config import get_settings
from app.core.crypto import decrypt, encrypt
from app.settings import store
from app.settings.registry import SettingsSection, register_section

SECTION_KEY = "agent"
MASKED_SECRET = "••••••••"
DEFAULT_VENDOR = "ollama"


class AgentSettingsSchema(BaseModel):
    llm_vendor: str = Field(
        default=DEFAULT_VENDOR,
        description="Fournisseur — voir app/agent/providers/catalog.py",
        examples=["ollama", "openai", "deepseek", "kimi", "anthropic"],
    )
    llm_model: str = Field(
        description=(
            "Nom du modèle chez le fournisseur choisi (liste suggérée, saisie libre acceptée)"
        ),
        examples=["llama3.1:8b", "gpt-4o", "deepseek-chat", "moonshot-v1-8k", "claude-opus-5"],
    )
    base_url: str = Field(
        default="",
        description="URL du serveur — préremplie par défaut selon le fournisseur, modifiable",
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

    @model_validator(mode="after")
    def _validate_vendor_is_known(self) -> "AgentSettingsSchema":
        get_vendor(self.llm_vendor)  # lève ValueError (-> 422) si inconnu
        return self


def get_effective_agent_settings() -> AgentSettingsSchema:
    """Valeurs réellement utilisées par `get_llm_client()` — `api_key` en clair, jamais exposée
    telle quelle par l'API (voir `_get_current_values`, qui la masque avant de la renvoyer).
    `model_construct()` plutôt que le constructeur normal : une lecture ne doit jamais échouer
    (la validation "fournisseur connu" ne s'applique qu'à l'écriture, via le router)."""
    base = get_settings()
    override = store.get_override(SECTION_KEY) or {}
    vendor_key = override.get("llm_vendor", DEFAULT_VENDOR)
    encrypted_key = override.get("api_key", "")
    return AgentSettingsSchema.model_construct(
        llm_vendor=vendor_key,
        llm_model=override.get("llm_model", base.llm_model),
        # Vide plutôt que Settings.llm_base_url ici : ce dernier ne doit s'appliquer qu'au
        # fournisseur "ollama" (voir get_llm_client(), qui complète dans cet ordre : override
        # explicite -> défaut du fournisseur choisi -> Settings.llm_base_url en tout dernier
        # recours). Le retomber ici casserait l'URL par défaut de tout fournisseur distant tant
        # qu'aucun override de base_url n'a jamais été sauvegardé.
        base_url=override.get("base_url", ""),
        api_key=decrypt(encrypted_key) if encrypted_key else "",
    )


def _get_current_values() -> dict[str, Any]:
    values = get_effective_agent_settings().model_dump()
    values["api_key"] = MASKED_SECRET if values["api_key"] else ""
    return values


def _get_config_schema() -> dict[str, Any]:
    schema = AgentSettingsSchema.model_json_schema()
    schema["properties"]["llm_vendor"]["enum"] = [vendor.key for vendor in list_vendors()]
    return schema


def _get_read_only() -> dict[str, Any]:
    # Catalogue complet transmis au front (Epic 9) : le choix du fournisseur détermine
    # dynamiquement les modèles suggérés et l'URL par défaut, sans aller-retour supplémentaire.
    return {
        "vendors": {
            vendor.key: {
                "display_name": vendor.display_name,
                "default_base_url": vendor.default_base_url,
                "known_models": vendor.known_models,
            }
            for vendor in list_vendors()
        }
    }


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
            "Choisir directement le fournisseur et le modèle à utiliser (local ou distant) "
            "depuis l'interface — la clé API est chiffrée avant stockage, jamais réaffichée en "
            "clair. S'applique au prochain message, pas au tour de conversation en cours."
        ),
        schema=AgentSettingsSchema,
        effect="deferred",
        get_current_values=_get_current_values,
        get_read_only=_get_read_only,
        get_config_schema=_get_config_schema,
        pre_store=_pre_store,
        apply=_apply,
    )
)
