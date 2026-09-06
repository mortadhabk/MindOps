import pytest
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.agent.providers.anthropic import AnthropicProvider
from app.agent.providers.ollama import OllamaProvider
from app.agent.providers.openai_compatible import OpenAICompatibleProvider
from app.agent.providers.registry import get_provider, list_provider_kinds


def test_list_provider_kinds_includes_all_three_families():
    kinds = {info.kind for info in list_provider_kinds()}
    assert kinds == {"ollama", "openai_compatible", "anthropic"}


def test_get_provider_returns_matching_implementation():
    assert isinstance(get_provider("ollama"), OllamaProvider)
    assert isinstance(get_provider("openai_compatible"), OpenAICompatibleProvider)
    assert isinstance(get_provider("anthropic"), AnthropicProvider)


def test_get_provider_raises_for_unknown_kind():
    with pytest.raises(ValueError, match="does-not-exist"):
        get_provider("does-not-exist")


def test_ollama_provider_falls_back_to_settings_when_no_base_url_given():
    client = OllamaProvider().build_client(model="llama3.1:8b", credentials={})
    assert isinstance(client, ChatOllama)


def test_ollama_provider_uses_the_given_base_url_when_present():
    client = OllamaProvider().build_client(
        model="llama3.1:8b", credentials={"base_url": "http://custom:11434"}
    )
    assert client.base_url == "http://custom:11434"


def test_openai_compatible_provider_builds_a_chat_openai_client():
    client = OpenAICompatibleProvider().build_client(
        model="deepseek-chat",
        credentials={"base_url": "https://api.deepseek.com/v1", "api_key": "sk-test"},
    )
    assert isinstance(client, ChatOpenAI)
    assert client.model_name == "deepseek-chat"


def test_anthropic_provider_builds_a_chat_anthropic_client():
    client = AnthropicProvider().build_client(
        model="claude-opus-5", credentials={"api_key": "sk-ant-test"}
    )
    assert isinstance(client, ChatAnthropic)
    assert client.model == "claude-opus-5"


def test_anthropic_provider_defaults_to_the_real_anthropic_endpoint_when_no_url_given():
    client = AnthropicProvider().build_client(
        model="claude-opus-5", credentials={"api_key": "sk-ant-test"}
    )
    assert client.anthropic_api_url == "https://api.anthropic.com"


def test_anthropic_provider_uses_a_custom_url_when_given():
    client = AnthropicProvider().build_client(
        model="claude-opus-5",
        credentials={"api_key": "sk-ant-test", "base_url": "https://proxy.example.com"},
    )
    assert client.anthropic_api_url == "https://proxy.example.com"
