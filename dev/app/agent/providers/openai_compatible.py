from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.agent.providers.base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    """Tout fournisseur exposant l'API HTTP d'OpenAI : GPT (OpenAI lui-même), DeepSeek,
    Kimi/Moonshot, OpenRouter, Groq, Together, LM Studio, ... — un seul client, seuls
    `base_url`/`api_key` changent d'un alias `LLM_PROVIDER_CREDENTIALS` à l'autre."""

    kind = "openai_compatible"
    display_name = "Compatible OpenAI (GPT, DeepSeek, Kimi, ...)"

    def build_client(self, *, model: str, credentials: dict[str, str]) -> BaseChatModel:
        return ChatOpenAI(
            model=model,
            base_url=credentials.get("base_url"),
            api_key=credentials.get("api_key"),
            temperature=0,
        )
