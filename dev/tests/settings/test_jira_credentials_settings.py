from app.connectors.jira import settings as jira_settings
from app.settings import store


def test_get_jira_cloud_credentials_none_when_incomplete():
    store._overrides[jira_settings.SECTION_KEY] = {
        "jira_cloud_email": "bot@acme.com",
        "jira_cloud_api_token": "",  # manquant
        "jira_server_token": "",
    }

    assert jira_settings.get_jira_cloud_credentials("default") is None


def test_get_jira_cloud_credentials_returns_decrypted_token_when_complete():
    from app.core.crypto import encrypt

    store._overrides[jira_settings.SECTION_KEY] = {
        "jira_cloud_email": "bot@acme.com",
        "jira_cloud_api_token": encrypt("tok-123"),
        "jira_server_token": "",
    }

    creds = jira_settings.get_jira_cloud_credentials("default")

    assert creds is not None
    assert creds.email == "bot@acme.com"
    assert creds.api_token == "tok-123"


def test_get_jira_server_token_returns_decrypted_token():
    from app.core.crypto import encrypt

    store._overrides[jira_settings.SECTION_KEY] = {
        "jira_cloud_email": "",
        "jira_cloud_api_token": "",
        "jira_server_token": encrypt("pat-456"),
    }

    assert jira_settings.get_jira_server_token("default") == "pat-456"


def test_credential_accessors_ignore_unknown_alias():
    from app.core.crypto import encrypt

    store._overrides[jira_settings.SECTION_KEY] = {
        "jira_cloud_email": "bot@acme.com",
        "jira_cloud_api_token": encrypt("tok"),
        "jira_server_token": encrypt("pat"),
    }

    assert jira_settings.get_jira_cloud_credentials("autre-alias") is None
    assert jira_settings.get_jira_server_token("autre-alias") is None


def test_pre_store_encrypts_each_secret_field_independently():
    from app.core.crypto import decrypt

    result = jira_settings._pre_store(
        {
            "jira_cloud_email": "bot@acme.com",
            "jira_cloud_api_token": "new-cloud-token",
            "jira_server_token": "",
        },
        existing={"jira_server_token": "already-encrypted-pat"},
    )

    assert decrypt(result["jira_cloud_api_token"]) == "new-cloud-token"
    assert result["jira_server_token"] == "already-encrypted-pat"
    assert result["jira_cloud_email"] == "bot@acme.com"
