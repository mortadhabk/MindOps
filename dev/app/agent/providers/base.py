from abc import ABC, abstractmethod
from typing import ClassVar

from langchain_core.language_models import BaseChatModel


class LLMProvider(ABC):
    """Port implémenté par chaque famille de client LLM (adapter) — même pattern que
    `connectors.base.Connector` (Epic 2/8) : une classe par famille de client, un registre pour
    les retrouver par nom, aucune ramification `if/else` qui grossit à chaque nouveau fournisseur.

    Une *famille* (`kind`) couvre potentiellement plusieurs fournisseurs commerciaux : un seul
    `OpenAICompatibleProvider` sait parler à OpenAI (GPT), DeepSeek, Kimi/Moonshot, OpenRouter,
    Groq, ... — seuls `base_url`/`api_key` changent, pas le protocole. Le choix du `kind` et les
    identifiants sont saisis directement dans l'onglet Paramètres (Epic 9, interface-first),
    chiffrés avant stockage — voir `agent.settings`.
    """

    kind: ClassVar[str]
    display_name: ClassVar[str]

    @abstractmethod
    def build_client(self, *, model: str, credentials: dict[str, str]) -> BaseChatModel:
        """Construit le client LangChain pour ce modèle. `credentials` porte les champs propres
        à cette famille (ex: `api_key`, `base_url`) — `base_url` retombe sur `Settings.llm_base_url`
        pour Ollama si absent (voir `OllamaProvider`)."""
