from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel


class Tool(ABC):
    """Port implémenté par chaque outil exposé au LLM via function calling."""

    name: ClassVar[str]
    description: ClassVar[str]
    args_schema: ClassVar[type[BaseModel]]
    sensitive: ClassVar[bool] = False  # True : passe par la politique de confiance (Epic 4)

    @abstractmethod
    async def execute(self, **kwargs: object) -> str:
        """Exécute l'outil et renvoie un résultat textuel à réinjecter au LLM."""
