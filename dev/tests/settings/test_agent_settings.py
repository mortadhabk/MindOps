from app.agent import settings as agent_settings
from app.agent.llm_client import get_llm_client
from app.agent.settings import get_effective_agent_settings
from app.settings import store


def test_get_effective_agent_settings_uses_override_when_present():
    store._overrides["agent"] = {
        "llm_model": "custom-model",
        "ollama_base_url": "http://custom:1234",
    }

    settings = get_effective_agent_settings()

    assert settings.llm_model == "custom-model"
    assert settings.ollama_base_url == "http://custom:1234"


def test_apply_invalidates_the_cached_llm_client(monkeypatch):
    calls = []
    monkeypatch.setattr(get_llm_client, "cache_clear", lambda: calls.append(True))

    agent_settings._apply({"llm_model": "x", "ollama_base_url": "y"})

    assert calls == [True]
