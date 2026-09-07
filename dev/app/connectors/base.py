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
    # Epic 10 : si True, `instance_service.run_sync()` injecte `since=instance.last_synced_at`
    # dans les kwargs de `fetch_items()` (jamais un champ de `config_schema`, donc jamais dans le
    # formulaire du Studio — c'est une valeur que seul `instance_service` connaît). Un connecteur
    # qui ne déclare pas ce flag continue de fonctionner exactement comme avant (sync complète à
    # chaque fois) : ajouter le flag ailleurs (ex. GitHub) n'impose donc aucune migration groupée.
    supports_incremental_sync: ClassVar[bool] = False

    @abstractmethod
    async def fetch_items(self, **params: Any) -> list[Any]:
        """Récupère les items bruts depuis la source externe."""

    @abstractmethod
    def to_document(self, item: Any) -> DocumentIn:
        """Convertit un item brut en document prêt à être ingéré par le module `rag`."""
