from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.rag.models import Chunk, Document


async def nearest_chunks(
    db: AsyncSession, query_embedding: list[float], top_k: int
) -> list[tuple[Chunk, float]]:
    distance = Chunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(Chunk, (1 - distance).label("similarity"))
        # Charge Document dans la même requête (JOIN) : le retriever expose la provenance
        # (source, connector_instance_id) sans lazy-load supplémentaire sur une session async.
        .options(joinedload(Chunk.document))
        .order_by(distance)
        .limit(top_k)
    )

    result = await db.execute(stmt)
    return [(chunk, similarity) for chunk, similarity in result.all()]


async def chunks_matching_source(db: AsyncSession, needle: str) -> list[Chunk]:
    """Tous les chunks d'un document dont `source` contient `needle` (ex: une clé de ticket comme
    "ENACMARCHE-161") — complète `nearest_chunks` pour les identifiants exacts. Un identifiant
    n'a aucune signification sémantique propre : il perd systématiquement face à des tickets
    voisins par le sujet (même vocabulaire "Flux", "erreur", ...) dans une recherche par
    similarité pure, même quand c'est littéralement lui qu'on demande (voir retriever.search)."""
    stmt = (
        select(Chunk)
        .join(Document)
        .where(Document.source.ilike(f"%{needle}%"))
        .options(joinedload(Chunk.document))
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique())
