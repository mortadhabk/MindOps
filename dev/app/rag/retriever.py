from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.models import Chunk
from app.rag.vector_store import nearest_chunks


async def search(
    db: AsyncSession,
    query: str,
    provider: EmbeddingProvider,
    top_k: int = 5,
    similarity_threshold: float | None = None,
) -> list[tuple[Chunk, float]]:
    threshold = (
        similarity_threshold
        if similarity_threshold is not None
        else get_settings().rag_similarity_threshold
    )

    [query_vector] = await provider.embed([query])
    results = await nearest_chunks(db, query_vector, top_k)
    return [(chunk, score) for chunk, score in results if score >= threshold]
