from abc import ABC, abstractmethod


class Reranker(ABC):
    @abstractmethod
    async def rerank(self, query: str, candidates: list[str]) -> list[float]:
        """Un score de pertinence par candidat, même ordre/longueur que `candidates` — plus haut
        = plus pertinent. L'échelle des scores dépend du modèle (pas garantie dans [0, 1]) : ils
        ne servent qu'à réordonner, jamais à remplacer un score déjà affiché à l'utilisateur
        (voir app/rag/retriever.py)."""
