from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import Tool
from app.rag.embeddings.base import EmbeddingProvider
from app.rag.reranking.base import Reranker
from app.rag.retriever import search as search_chunks


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(
        description="La question ou le sujet à rechercher dans la base de connaissances"
    )


class SearchKnowledgeTool(Tool):
    """Outil de lecture seule : cherche dans la base de connaissances RAG (Epic 1)."""

    name = "search_knowledge"
    description = (
        "Cherche dans la base de connaissances les fragments les plus pertinents pour une "
        "requête donnée. Rappelable plusieurs fois, mais chaque appel doit chercher quelque "
        "chose de QUALITATIVEMENT DIFFÉRENT du précédent (ex : le symptôme, puis le nom du flux/"
        "module seul, puis « spécifications » + ce nom, puis un filtre sur un ticket résolu) — "
        "reformuler la même question avec des synonymes retombe presque toujours sur le même "
        "document et n'apporte rien. Rappeler aussi dès qu'un message de l'utilisateur apporte "
        "une information concrète nouvelle (contenu d'email, date, extrait) plutôt que de "
        "répondre depuis des résultats déjà obtenus plus tôt dans la conversation."
    )
    args_schema = SearchKnowledgeArgs

    def __init__(
        self,
        db: AsyncSession,
        provider: EmbeddingProvider,
        top_k: int = 5,
        reranker: Reranker | None = None,
    ):
        self._db = db
        self._provider = provider
        self._top_k = top_k
        self._reranker = reranker

    async def execute(self, *, query: str) -> str:
        results = await search_chunks(
            self._db, query, self._provider, top_k=self._top_k, reranker=self._reranker
        )
        if not results:
            return "Aucun fragment pertinent trouvé dans la base de connaissances."
        return "\n\n".join(
            f"[source: document#{chunk.document_id}] {chunk.text}" for chunk, _score in results
        )
