from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from app.rag.schemas import DocumentIn


class Connector(ABC):
    """Port implémenté par chaque intégration externe (adapter)."""

    name: ClassVar[str]
    display_name: ClassVar[str]  # affiché dans la palette du Studio (Epic 8)
    description: ClassVar[str]
    # Décrit les paramètres attendus par fetch_items(**config) : valide la configuration d'une
    # ConnectorInstance à la création ET génère le formulaire du Studio (GET /connectors/types),
    # sans dupliquer la définition des champs entre back et front.
    config_schema: ClassVar[type[BaseModel]]

    @abstractmethod
    async def fetch_items(self, **params: Any) -> list[Any]:
        """Récupère les items bruts depuis la source externe."""

    @abstractmethod
    def to_document(self, item: Any) -> DocumentIn:
        """Convertit un item brut en document prêt à être ingéré par le module `rag`."""
