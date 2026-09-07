from dataclasses import dataclass, field


@dataclass
class LLMVendor:
    """Un fournisseur commercial concret (Epic 9) — distinct de `LLMProvider` (`app.agent.
    providers.base`), qui ne représente qu'une *famille de client* (`client_kind`). Plusieurs
    vendeurs partagent la même famille : OpenAI, DeepSeek et Kimi parlent tous le protocole
    OpenAI (`client_kind="openai_compatible"`), seuls `default_base_url`/`known_models` changent.
    """

    key: str
    display_name: str
    client_kind: str
    default_base_url: str | None  # None : pas d'URL fixe (ex. Ollama lit Settings.llm_base_url)
    known_models: list[str] = field(default_factory=list)


_VENDORS: dict[str, LLMVendor] = {
    "ollama": LLMVendor(
        key="ollama",
        display_name="Ollama (local)",
        client_kind="ollama",
        default_base_url=None,
        known_models=[
            "llama3.1:8b",
            "llama3.2:3b",
            "llama3.2:1b",
            "qwen2.5:7b",
            "qwen2.5:14b",
            "mistral",
            "phi3",
            "gemma2:9b",
        ],
    ),
    "openai": LLMVendor(
        key="openai",
        display_name="OpenAI (GPT)",
        client_kind="openai_compatible",
        default_base_url="https://api.openai.com/v1",
        known_models=["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o3", "o3-mini"],
    ),
    "deepseek": LLMVendor(
        key="deepseek",
        display_name="DeepSeek",
        client_kind="openai_compatible",
        default_base_url="https://api.deepseek.com/v1",
        known_models=["deepseek-chat", "deepseek-reasoner"],
    ),
    "kimi": LLMVendor(
        key="kimi",
        display_name="Kimi (Moonshot AI)",
        client_kind="openai_compatible",
        default_base_url="https://api.moonshot.cn/v1",
        known_models=["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k", "kimi-latest"],
    ),
    "openrama": LLMVendor(
        key="openrama",
        display_name="OpenRama (Orange interne)",
        client_kind="openai_compatible",
        default_base_url="https://llm.openrama.tech.orange",
        known_models=[
            "minimax-m2.5-229b",
            "qwen3.5-122b-instruct",
            "gemma-3-12b-instruct",
            "qwen2.5-coder-7b-instruct",
            "devstral-small-2-24b-instruct",
        ],
    ),
    "llmproxy": LLMVendor(
        key="llmproxy",
        display_name="LLM Proxy",
        client_kind="openai_compatible",
        default_base_url="https://llmproxy.ai.orange",
        known_models=[
            "openai/gpt-5.4",
            "openai/gpt-5.4-mini",
            "openai/gpt-5.4-nano",
            "openai/gpt-5.2",
            "openai/gpt-5.1",
            "openai/gpt-5",
            "openai/gpt-5-chat",
            "openai/gpt-5-mini",
            "openai/gpt-5-nano",
            "openai/gpt-4.1",
            "openai/gpt-4.1-mini",
            "openai/gpt-4.1-nano",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "openai/o1",
            "openai/o1-preview",
            "openai/o3",
            "openai/o3-mini",
            "openai/o4-mini",
            "openai/o4-mini-deep-research",
        ],
    ),
    "anthropic": LLMVendor(
        key="anthropic",
        display_name="Claude (Anthropic)",
        client_kind="anthropic",
        default_base_url=None,
        known_models=[
            "claude-opus-5",
            "claude-sonnet-5",
            "claude-fable-5-1",
            "claude-haiku-4-5-20251001",
        ],
    ),
}


def get_vendor(key: str) -> LLMVendor:
    try:
        return _VENDORS[key]
    except KeyError:
        raise ValueError(
            f"Fournisseur LLM inconnu : « {key} » (valeurs possibles : {', '.join(_VENDORS)})"
        ) from None


def list_vendors() -> list[LLMVendor]:
    return list(_VENDORS.values())
