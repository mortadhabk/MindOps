from functools import lru_cache

from app.config import get_settings
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.embeddings.local import LocalMiniLMEmbeddingProvider

__all__ = ["EmbeddingProvider", "get_embedding_provider"]


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "local":
        return LocalMiniLMEmbeddingProvider(model_name=settings.embedding_model)
    raise ValueError(f"Fournisseur d'embeddings inconnu : {settings.embedding_provider}")
