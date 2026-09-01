import hashlib

from app.rag.embeddings.base import EmbeddingProvider


class FakeEmbeddingProvider(EmbeddingProvider):
    # dimension alignee sur LocalMiniLMEmbeddingProvider pour rester compatible
    # avec la colonne chunks.embedding (Vector(384))
    dimension = 384

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._fake_vector(text) for text in texts]

    def _fake_vector(self, text: str) -> list[float]:
        values: list[float] = []
        block = text.encode()
        while len(values) < self.dimension:
            block = hashlib.sha256(block).digest()
            values.extend(byte / 255 for byte in block)
        return values[: self.dimension]
