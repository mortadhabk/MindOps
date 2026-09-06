from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.agent.settings import get_effective_agent_settings
from app.config import get_settings


@lru_cache
def get_llm_client() -> BaseChatModel:
    """Mis en cache car un vrai client est construit ici (pas juste de la config) : un changement
    de modèle/URL sauvegardé depuis l'onglet Paramètres (Epic 9) appelle `cache_clear()` pour
    forcer la reconstruction au prochain appel — voir `agent.settings._apply`."""
    provider = get_settings().llm_provider
    if provider != "ollama":
        raise ValueError(f"Fournisseur LLM non supporté : {provider}")
    settings = get_effective_agent_settings()
    return ChatOllama(model=settings.llm_model, base_url=settings.ollama_base_url, temperature=0)
