from functools import lru_cache

from app.config import get_settings
from app.rag.reranking.base import Reranker
from app.rag.reranking.local import LocalCrossEncoderReranker

__all__ = ["Reranker", "get_reranker"]


@lru_cache
def get_reranker() -> Reranker:
    return LocalCrossEncoderReranker(model_name=get_settings().reranker_model)
