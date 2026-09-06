import pytest
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.agent.llm_client import get_llm_client
from app.settings import store


@pytest.fixture(autouse=True)
def _clear_llm_client_cache():
    get_llm_client.cache_clear()
    yield
    get_llm_client.cache_clear()


def test_builds_a_chat_ollama_client_for_the_native_provider():
    store._overrides["agent"] = {
        "llm_provider_kind": "ollama",
        "llm_model": "llama3.1:8b",
        "base_url": "http://localhost:11434",
    }

    client = get_llm_client()

    assert isinstance(client, ChatOllama)
    assert client.model == "llama3.1:8b"


def test_ollama_uses_the_effective_base_url_from_settings():
    store._overrides["agent"] = {
        "llm_provider_kind": "ollama",
        "llm_model": "llama3.1:8b",
        "base_url": "http://overridden:11434",
    }

    client = get_llm_client()

    assert client.base_url == "http://overridden:11434"


def test_builds_a_chat_openai_client_for_an_openai_compatible_provider():
    from app.core.crypto import encrypt

    store._overrides["agent"] = {
        "llm_provider_kind": "openai_compatible",
        "llm_model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": encrypt("sk-test"),
    }

    client = get_llm_client()

    assert isinstance(client, ChatOpenAI)
    assert client.model_name == "deepseek-chat"


def test_builds_a_chat_anthropic_client_for_the_anthropic_kind():
    from app.core.crypto import encrypt

    store._overrides["agent"] = {
        "llm_provider_kind": "anthropic",
        "llm_model": "claude-opus-5",
        "api_key": encrypt("sk-ant-test"),
    }

    client = get_llm_client()

    assert isinstance(client, ChatAnthropic)
    assert client.model == "claude-opus-5"


def test_raises_a_clear_error_for_an_unknown_provider_kind():
    store._overrides["agent"] = {"llm_provider_kind": "does-not-exist", "llm_model": "x"}

    with pytest.raises(ValueError, match="does-not-exist"):
        get_llm_client()
