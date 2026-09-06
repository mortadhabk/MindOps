from dataclasses import dataclass

from app.agent.providers.anthropic import AnthropicProvider
from app.agent.providers.base import LLMProvider
from app.agent.providers.ollama import OllamaProvider
from app.agent.providers.openai_compatible import OpenAICompatibleProvider

_PROVIDERS: dict[str, LLMProvider] = {
    "ollama": OllamaProvider(),
    "openai_compatible": OpenAICompatibleProvider(),
    "anthropic": AnthropicProvider(),
}


def get_provider(kind: str) -> LLMProvider:
    try:
        return _PROVIDERS[kind]
    except KeyError:
        raise ValueError(
            f"Type de fournisseur LLM inconnu : « {kind} » (valeurs possibles : "
            f"{', '.join(_PROVIDERS)})"
        ) from None


@dataclass
class LLMProviderKindInfo:
    kind: str
    display_name: str


def list_provider_kinds() -> list[LLMProviderKindInfo]:
    return [
        LLMProviderKindInfo(kind=provider.kind, display_name=provider.display_name)
        for provider in _PROVIDERS.values()
    ]
