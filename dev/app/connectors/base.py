from abc import ABC, abstractmethod
from typing import Any

from app.rag.schemas import DocumentIn


class Connector(ABC):
    """Port implémenté par chaque intégration externe (adapter)."""

    name: str

    @abstractmethod
    async def fetch_items(self, **params: Any) -> list[Any]:
        """Récupère les items bruts depuis la source externe."""

    @abstractmethod
    def to_document(self, item: Any) -> DocumentIn:
        """Convertit un item brut en document prêt à être ingéré par le module `rag`."""
