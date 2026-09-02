from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import Tool
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.retriever import search as search_chunks


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(
        description="La question ou le sujet à rechercher dans la base de connaissances"
    )


class SearchKnowledgeTool(Tool):
    """Outil de lecture seule : cherche dans la base de connaissances RAG (Epic 1)."""

    name = "search_knowledge"
    description = (
        "Cherche dans la base de connaissances les fragments les plus pertinents pour répondre "
        "à une question factuelle. À utiliser avant de répondre sur un sujet du domaine."
    )
    args_schema = SearchKnowledgeArgs

    def __init__(self, db: AsyncSession, provider: EmbeddingProvider, top_k: int = 5):
        self._db = db
        self._provider = provider
        self._top_k = top_k

    async def execute(self, *, query: str) -> str:
        results = await search_chunks(self._db, query, self._provider, top_k=self._top_k)
        if not results:
            return "Aucun fragment pertinent trouvé dans la base de connaissances."
        return "\n\n".join(
            f"[source: document#{chunk.document_id}] {chunk.text}" for chunk, _score in results
        )
