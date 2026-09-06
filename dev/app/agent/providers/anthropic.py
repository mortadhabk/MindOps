from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel

from app.agent.providers.base import LLMProvider


class AnthropicProvider(LLMProvider):
    """API native Anthropic (Claude) — format différent d'OpenAI, nécessite son propre client."""

    kind = "anthropic"
    display_name = "Claude (Anthropic, natif)"

    def build_client(self, *, model: str, credentials: dict[str, str]) -> BaseChatModel:
        return ChatAnthropic(model=model, api_key=credentials.get("api_key"), temperature=0)
