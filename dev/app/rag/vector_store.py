from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.rag.models import Chunk


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
