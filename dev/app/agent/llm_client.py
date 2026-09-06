from functools import lru_cache

from langchain_core.language_models import BaseChatModel

from app.agent.providers.registry import get_provider
from app.agent.settings import get_effective_agent_settings


@lru_cache
def get_llm_client() -> BaseChatModel:
    """Mis en cache car un vrai client est construit ici (pas juste de la config) : un changement
    de fournisseur/modèle/URL/clé sauvegardé depuis l'onglet Paramètres (Epic 9, interface-first)
    appelle `cache_clear()` pour forcer la reconstruction au prochain appel — voir
    `agent.settings._apply`.

    La construction elle-même est déléguée à `agent.providers` (un `LLMProvider` par famille de
    client) plutôt que codée ici en dur — ajouter un nouveau fournisseur ne touche jamais cette
    fonction, seulement une nouvelle classe `LLMProvider` si sa famille n'existe pas déjà.
    """
    settings = get_effective_agent_settings()
    credentials = {"base_url": settings.base_url, "api_key": settings.api_key}
    return get_provider(settings.llm_provider_kind).build_client(
        model=settings.llm_model, credentials=credentials
    )
