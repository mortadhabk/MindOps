from app.connectors.github import settings as github_settings
from app.settings import store


def test_get_github_token_falls_back_to_env_when_no_override(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    get_settings.cache_clear()
    try:
        assert github_settings.get_github_token() == "env-token"
    finally:
        get_settings.cache_clear()


def test_get_github_token_prefers_decrypted_override():
    from app.core.crypto import encrypt

    store._overrides[github_settings.SECTION_KEY] = {"github_token": encrypt("stored-token")}

    assert github_settings.get_github_token() == "stored-token"


def test_current_values_masks_the_token():
    from app.core.crypto import encrypt

    store._overrides[github_settings.SECTION_KEY] = {"github_token": encrypt("secret")}

    values = github_settings._get_current_values()

    assert values["github_token"] == github_settings.MASKED_SECRET


def test_pre_store_encrypts_a_newly_submitted_token():
    from app.core.crypto import decrypt

    result = github_settings._pre_store({"github_token": "sk-new"}, existing=None)

    assert result["github_token"] != "sk-new"
    assert decrypt(result["github_token"]) == "sk-new"


def test_pre_store_keeps_existing_token_when_submitted_empty():
    existing = {"github_token": "already-encrypted"}

    result = github_settings._pre_store({"github_token": ""}, existing=existing)

    assert result["github_token"] == "already-encrypted"
