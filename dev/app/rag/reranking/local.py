import asyncio

from sentence_transformers import CrossEncoder

from app.rag.reranking.base import Reranker


class LocalCrossEncoderReranker(Reranker):
    """Cross-encoder (compare directement question+fragment, plus précis mais plus coûteux
    qu'une similarité cosinus sur deux embeddings séparés) — appliqué à un petit lot de
    candidats déjà présélectionnés par la recherche vectorielle, jamais à toute la base."""

    def __init__(self, model_name: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1") -> None:
        self._model = CrossEncoder(model_name)

    async def rerank(self, query: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        loop = asyncio.get_running_loop()
        scores = await loop.run_in_executor(None, self._predict, query, candidates)
        return scores.tolist()

    def _predict(self, query: str, candidates: list[str]):
        pairs = [(query, candidate) for candidate in candidates]
        return self._model.predict(pairs)
