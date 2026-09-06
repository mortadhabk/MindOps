from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.settings import store
from app.settings.registry import SettingsSection, register_section

SECTION_KEY = "agent"


class AgentSettingsSchema(BaseModel):
    llm_model: str = Field(description="Modèle Ollama", examples=["llama3.1:8b"])
    ollama_base_url: str = Field(
        description="URL du serveur Ollama", examples=["http://localhost:11434"]
    )


def get_effective_agent_settings() -> AgentSettingsSchema:
    base = get_settings()
    override = store.get_override(SECTION_KEY) or {}
    return AgentSettingsSchema(
        llm_model=override.get("llm_model", base.llm_model),
        ollama_base_url=override.get("ollama_base_url", base.ollama_base_url),
    )


def _apply(_values: dict[str, Any]) -> None:
    # get_llm_client() est en cache (@lru_cache) car elle construit un client réel, pas juste de
    # la config — l'invalider ici force sa reconstruction avec les nouvelles valeurs au prochain
    # message, sans redémarrer l'API. Import local : évite un import circulaire au chargement du
    # module (agent.llm_client importe app.config, pas agent.settings).
    from app.agent.llm_client import get_llm_client

    get_llm_client.cache_clear()


register_section(
    SettingsSection(
        key="agent",
        display_name="Agent / LLM",
        description=(
            "S'applique au prochain message, pas au tour de conversation en cours "
            "(le client LLM en cache est reconstruit à la sauvegarde)."
        ),
        schema=AgentSettingsSchema,
        effect="deferred",
        get_current_values=lambda: get_effective_agent_settings().model_dump(),
        apply=_apply,
    )
)
