import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embeddings.base import EmbeddingProvider
from app.rag.models import Chunk
from app.rag.reranking.base import Reranker
from app.rag.settings import get_effective_rag_settings
from app.rag.vector_store import chunks_matching_source, nearest_chunks

# Motif générique d'identifiant de ticket ("ENACMARCHE-161", "SUP-42", ...) — un tel identifiant
# n'a aucune signification sémantique propre, donc perd systématiquement face à des documents
# voisins par le sujet dans une recherche par similarité pure, même quand c'est littéralement lui
# qui est demandé. Détecté dans la requête pour compléter la recherche vectorielle par une
# correspondance exacte sur `Document.source` (voir `search` ci-dessous).
_TICKET_KEY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,15}-\d+\b")

# Nombre de candidats soumis au reranker — plus large que `top_k` : tout l'intérêt du reranking
# est de repêcher un candidat mal classé par la similarité cosinus seule (voir management, "le
# ticket existait mais son meilleur chunk n'entrait jamais dans le top-5 cosinus").
RERANK_POOL_SIZE = 20


async def search(
    db: AsyncSession,
    query: str,
    provider: EmbeddingProvider,
    top_k: int = 5,
    similarity_threshold: float | None = None,
    reranker: Reranker | None = None,
) -> list[tuple[Chunk, float]]:
    settings = get_effective_rag_settings()
    if similarity_threshold is not None:
        threshold = similarity_threshold
    else:
        threshold = settings.rag_similarity_threshold
    use_rerank = reranker is not None and settings.rag_rerank_enabled

    [query_vector] = await provider.embed([query])
    pool_size = max(top_k, RERANK_POOL_SIZE) if use_rerank else top_k
    semantic_pool = await nearest_chunks(db, query_vector, pool_size)
    semantic_results = [(chunk, score) for chunk, score in semantic_pool if score >= threshold]

    if use_rerank and semantic_results:
        chunks = [chunk for chunk, _ in semantic_results]
        rerank_scores = await reranker.rerank(query, [chunk.text for chunk in chunks])
        # Le reranker ne fait que réordonner : le score renvoyé reste la similarité cosinus
        # d'origine (échelle stable, comparable à `rag_similarity_threshold`), jamais le score
        # brut du cross-encoder (échelle qui dépend du modèle, pas garantie dans [0, 1]).
        order = sorted(range(len(semantic_results)), key=lambda i: rerank_scores[i], reverse=True)
        semantic_results = [semantic_results[i] for i in order]

    results = semantic_results[:top_k]

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
