import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embeddings.base import EmbeddingProvider
from app.rag.models import Chunk
from app.rag.settings import get_effective_rag_settings
from app.rag.vector_store import chunks_matching_source, nearest_chunks

# Motif générique d'identifiant de ticket ("ENACMARCHE-161", "SUP-42", ...) — un tel identifiant
# n'a aucune signification sémantique propre, donc perd systématiquement face à des documents
# voisins par le sujet dans une recherche par similarité pure, même quand c'est littéralement lui
# qui est demandé. Détecté dans la requête pour compléter la recherche vectorielle par une
# correspondance exacte sur `Document.source` (voir `search` ci-dessous).
_TICKET_KEY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,15}-\d+\b")


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
        else get_effective_rag_settings().rag_similarity_threshold
    )

    [query_vector] = await provider.embed([query])
    semantic_results = await nearest_chunks(db, query_vector, top_k)
    results = [(chunk, score) for chunk, score in semantic_results if score >= threshold]

    ticket_key = _TICKET_KEY_PATTERN.search(query.upper())
    if ticket_key:
        already_included = {chunk.id for chunk, _ in results}
        exact_matches = await chunks_matching_source(db, ticket_key.group())
        # En tête de liste (score 1.0, correspondance exacte) : un identifiant demandé
        # explicitement prime sur des résultats seulement proches sémantiquement.
        results = [
            (chunk, 1.0) for chunk in exact_matches if chunk.id not in already_included
        ] + results

    return results
