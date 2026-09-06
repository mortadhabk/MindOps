from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.agent.providers.base import LLMProvider
from app.config import get_settings


class OllamaProvider(LLMProvider):
    """Modèle local, aucune clé API — voir `Settings.llm_base_url` (.env, valeur de démarrage)."""

    kind = "ollama"
    display_name = "Ollama (local)"

    def build_client(self, *, model: str, credentials: dict[str, str]) -> BaseChatModel:
        base_url = credentials.get("base_url") or get_settings().llm_base_url
        return ChatOllama(model=model, base_url=base_url, temperature=0)
