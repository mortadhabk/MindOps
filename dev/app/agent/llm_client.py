from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.config import get_settings


@lru_cache
def get_llm_client() -> BaseChatModel:
    settings = get_settings()
    if settings.llm_provider != "ollama":
        raise ValueError(f"Fournisseur LLM non supporté : {settings.llm_provider}")
    return ChatOllama(model=settings.llm_model, base_url=settings.ollama_base_url, temperature=0)
