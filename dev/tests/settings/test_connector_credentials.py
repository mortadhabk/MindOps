from app.connectors import credential_settings
from app.settings import store


def test_get_effective_falls_back_to_env_when_no_override(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        assert credential_settings.get_github_token() == "env-token"
    finally:
        get_settings.cache_clear()


def test_get_effective_prefers_override_and_decrypts_password_fields():
    from app.core.crypto import encrypt

    store._overrides[credential_settings.SECTION_KEY] = {
        "github_token": encrypt("stored-token"),
        "sharepoint_tenant_id": "",
        "sharepoint_client_id": "",
        "sharepoint_client_secret": "",
        "jira_cloud_email": "",
        "jira_cloud_api_token": "",
        "jira_server_token": "",
    }

    assert credential_settings.get_github_token() == "stored-token"


def test_current_values_masks_password_fields_only():
    from app.core.crypto import encrypt

    store._overrides[credential_settings.SECTION_KEY] = {
        "github_token": encrypt("secret-token"),
        "sharepoint_tenant_id": "tenant-123",
        "sharepoint_client_id": "",
        "sharepoint_client_secret": "",
        "jira_cloud_email": "",
        "jira_cloud_api_token": "",
        "jira_server_token": "",
    }

    values = credential_settings._get_current_values()

    assert values["github_token"] == credential_settings.MASKED_SECRET
    assert values["sharepoint_tenant_id"] == "tenant-123"  # champ non secret : jamais masqué
    assert "secret-token" not in str(values)


def test_pre_store_encrypts_a_newly_submitted_secret():
    from app.core.crypto import decrypt

    result = credential_settings._pre_store(
        {"github_token": "sk-new", "sharepoint_tenant_id": "t1"}, existing=None
    )

    assert result["github_token"] != "sk-new"
    assert decrypt(result["github_token"]) == "sk-new"
    assert result["sharepoint_tenant_id"] == "t1"


def test_pre_store_keeps_existing_secret_when_submitted_empty():
    existing = {"github_token": "already-encrypted"}

    result = credential_settings._pre_store({"github_token": ""}, existing=existing)

    assert result["github_token"] == "already-encrypted"


def test_pre_store_leaves_secret_empty_when_nothing_was_ever_stored():
    result = credential_settings._pre_store({"github_token": ""}, existing=None)

    assert result["github_token"] == ""


def test_get_sharepoint_credentials_requires_all_three_fields():
    from app.core.crypto import encrypt

    store._overrides[credential_settings.SECTION_KEY] = {
        "github_token": "",
        "sharepoint_tenant_id": "tenant",
        "sharepoint_client_id": "",  # manquant
        "sharepoint_client_secret": encrypt("secret"),
        "jira_cloud_email": "",
        "jira_cloud_api_token": "",
        "jira_server_token": "",
    }

    assert credential_settings.get_sharepoint_credentials("default") is None


def test_get_sharepoint_credentials_returns_decrypted_secret_when_complete():
    from app.core.crypto import encrypt

    store._overrides[credential_settings.SECTION_KEY] = {
        "github_token": "",
        "sharepoint_tenant_id": "tenant",
        "sharepoint_client_id": "client",
        "sharepoint_client_secret": encrypt("shhh"),
        "jira_cloud_email": "",
        "jira_cloud_api_token": "",
        "jira_server_token": "",
    }

    creds = credential_settings.get_sharepoint_credentials("default")

    assert creds is not None
    assert creds.tenant_id == "tenant"
    assert creds.client_secret == "shhh"


def test_credential_accessors_ignore_unknown_aliases():
    store._overrides[credential_settings.SECTION_KEY] = {
        "github_token": "",
        "sharepoint_tenant_id": "tenant",
        "sharepoint_client_id": "client",
        "sharepoint_client_secret": "secret",
        "jira_cloud_email": "bot@acme.com",
        "jira_cloud_api_token": "tok",
        "jira_server_token": "pat",
    }

    assert credential_settings.get_sharepoint_credentials("autre-alias") is None
    assert credential_settings.get_jira_cloud_credentials("autre-alias") is None
    assert credential_settings.get_jira_server_token("autre-alias") is None
