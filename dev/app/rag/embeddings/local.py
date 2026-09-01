import asyncio

from sentence_transformers import SentenceTransformer

from app.rag.embeddings.base import EmbeddingProvider


class LocalMiniLMEmbeddingProvider(EmbeddingProvider):
    dimension = 384

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2") -> None:
        self._model = SentenceTransformer(model_name)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_running_loop()
        vectors = await loop.run_in_executor(None, self._encode, texts)
        return vectors.tolist()

    def _encode(self, texts: list[str]):
        return self._model.encode(texts, normalize_embeddings=True)
