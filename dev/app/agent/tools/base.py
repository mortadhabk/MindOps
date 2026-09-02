from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel


class Tool(ABC):
    """Port implémenté par chaque outil exposé au LLM via function calling."""

    name: ClassVar[str]
    description: ClassVar[str]
    args_schema: ClassVar[type[BaseModel]]

    @abstractmethod
    async def execute(self, **kwargs: object) -> str:
        """Exécute l'outil et renvoie un résultat textuel à réinjecter au LLM."""
