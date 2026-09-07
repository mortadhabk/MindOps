import pytest
from pydantic import ValidationError

from app.agent import settings as agent_settings
from app.agent.llm_client import get_llm_client
from app.agent.settings import MASKED_SECRET, AgentSettingsSchema, get_effective_agent_settings
from app.settings import store


def test_get_effective_agent_settings_uses_override_when_present():
    store._overrides["agent"] = {
        "llm_vendor": "ollama",
        "llm_model": "custom-model",
        "base_url": "http://custom:1234",
    }

    settings = get_effective_agent_settings()

    assert settings.llm_model == "custom-model"
    assert settings.base_url == "http://custom:1234"


def test_get_effective_agent_settings_decrypts_the_stored_api_key():
    from app.core.crypto import encrypt

    store._overrides["agent"] = {
        "llm_vendor": "deepseek",
        "llm_model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": encrypt("sk-real-secret"),
    }

    settings = get_effective_agent_settings()

    assert settings.api_key == "sk-real-secret"


def test_current_values_masks_the_api_key_instead_of_returning_it_in_clear():
    from app.core.crypto import encrypt

    store._overrides["agent"] = {
        "llm_vendor": "deepseek",
        "llm_model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": encrypt("sk-real-secret"),
    }

    values = agent_settings._get_current_values()

    assert values["api_key"] == MASKED_SECRET
    assert "sk-real-secret" not in str(values)


def test_current_values_reports_empty_api_key_when_none_is_stored():
    store._overrides["agent"] = {
        "llm_vendor": "ollama",
        "llm_model": "llama3.1:8b",
        "base_url": "http://localhost:11434",
    }

    values = agent_settings._get_current_values()

    assert values["api_key"] == ""


def test_pre_store_encrypts_a_newly_submitted_key():
    from app.core.crypto import decrypt

    result = agent_settings._pre_store(
        {"llm_vendor": "anthropic", "llm_model": "claude-opus-5", "api_key": "sk-ant-new"},
        existing=None,
    )

    assert result["api_key"] != "sk-ant-new"  # jamais stocké en clair
    assert decrypt(result["api_key"]) == "sk-ant-new"


def test_pre_store_keeps_the_existing_key_when_submitted_empty():
    existing = {"api_key": "already-encrypted-value"}

    result = agent_settings._pre_store(
        {"llm_vendor": "anthropic", "llm_model": "claude-opus-5", "api_key": ""},
        existing=existing,
    )

    assert result["api_key"] == "already-encrypted-value"


def test_pre_store_leaves_api_key_empty_when_nothing_was_ever_stored():
    result = agent_settings._pre_store(
        {"llm_vendor": "ollama", "llm_model": "llama3.1:8b", "api_key": ""}, existing=None
    )

    assert result["api_key"] == ""


def test_config_schema_exposes_vendors_as_enum():
    schema = agent_settings._get_config_schema()

    assert set(schema["properties"]["llm_vendor"]["enum"]) == {
        "ollama",
        "openai",
        "deepseek",
        "kimi",
        "openrama",
        "llmproxy",
        "anthropic",
    }


def test_config_schema_marks_api_key_as_a_password_field():
    schema = agent_settings._get_config_schema()

    assert schema["properties"]["api_key"]["format"] == "password"


def test_read_only_exposes_the_full_vendor_catalog_for_the_frontend():
    read_only = agent_settings._get_read_only()

    assert set(read_only["vendors"]) == {
        "ollama",
        "openai",
        "deepseek",
        "kimi",
        "openrama",
        "llmproxy",
        "anthropic",
    }
    assert "deepseek-chat" in read_only["vendors"]["deepseek"]["known_models"]
    assert read_only["vendors"]["ollama"]["default_base_url"] is None


def test_schema_rejects_an_unknown_vendor():
    with pytest.raises(ValidationError):
        AgentSettingsSchema(llm_vendor="does-not-exist", llm_model="x")


def test_schema_accepts_every_cataloged_vendor():
    for vendor_key in ("ollama", "openai", "deepseek", "kimi", "openrama", "llmproxy", "anthropic"):
        AgentSettingsSchema(llm_vendor=vendor_key, llm_model="some-model")


def test_apply_invalidates_the_cached_llm_client(monkeypatch):
    calls = []
    monkeypatch.setattr(get_llm_client, "cache_clear", lambda: calls.append(True))

    agent_settings._apply({"llm_model": "x"})

    assert calls == [True]
