from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.models import Chunk, Document

DEFAULT_MAX_TOKENS = 200
DEFAULT_OVERLAP = 20


def chunk_text(
    text: str, max_tokens: int = DEFAULT_MAX_TOKENS, overlap: int = DEFAULT_OVERLAP
) -> list[str]:
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")
    if overlap < 0 or overlap >= max_tokens:
        raise ValueError("overlap must be within [0, max_tokens)")

    words = text.split()
    if not words:
        return []

    step = max_tokens - overlap
    return [" ".join(words[start : start + max_tokens]) for start in range(0, len(words), step)]


async def embed_chunks(texts: list[str], provider: EmbeddingProvider) -> list[list[float]]:
    if not texts:
        return []
    return await provider.embed(texts)


async def ingest_document(
    db: AsyncSession,
    *,
    source: str,
    content: str,
    provider: EmbeddingProvider,
    max_tokens: int | None = None,
    overlap: int | None = None,
) -> tuple[Document, int]:
    settings = get_settings()
    max_tokens = max_tokens if max_tokens is not None else settings.rag_chunk_max_tokens
    overlap = overlap if overlap is not None else settings.rag_chunk_overlap

    document = Document(source=source, content=content, status="pending")
    db.add(document)
    await db.flush()

    chunk_texts = chunk_text(content, max_tokens=max_tokens, overlap=overlap)

    try:
        vectors = await embed_chunks(chunk_texts, provider)
    except Exception:
        document.status = "partial"
        await db.commit()
        await db.refresh(document)
        return document, 0

    for text, vector in zip(chunk_texts, vectors, strict=True):
        db.add(Chunk(document_id=document.id, text=text, embedding=vector))

    document.status = "complete"
    await db.commit()
    await db.refresh(document)
    return document, len(chunk_texts)
