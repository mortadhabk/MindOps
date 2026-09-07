from app.connectors.sharepoint import settings as sharepoint_settings
from app.settings import store


def test_get_sharepoint_credentials_none_when_nothing_configured():
    assert sharepoint_settings.get_sharepoint_credentials("default") is None


def test_get_sharepoint_credentials_requires_all_three_fields():
    from app.core.crypto import encrypt

    store._overrides[sharepoint_settings.SECTION_KEY] = {
        "sharepoint_tenant_id": "tenant",
        "sharepoint_client_id": "",  # manquant
        "sharepoint_client_secret": encrypt("secret"),
    }

    assert sharepoint_settings.get_sharepoint_credentials("default") is None


def test_get_sharepoint_credentials_returns_decrypted_secret_when_complete():
    from app.core.crypto import encrypt

    store._overrides[sharepoint_settings.SECTION_KEY] = {
        "sharepoint_tenant_id": "tenant",
        "sharepoint_client_id": "client",
        "sharepoint_client_secret": encrypt("shhh"),
    }

    creds = sharepoint_settings.get_sharepoint_credentials("default")

    assert creds is not None
    assert creds.tenant_id == "tenant"
    assert creds.client_id == "client"
    assert creds.client_secret == "shhh"


def test_get_sharepoint_credentials_ignores_unknown_alias():
    from app.core.crypto import encrypt

    store._overrides[sharepoint_settings.SECTION_KEY] = {
        "sharepoint_tenant_id": "tenant",
        "sharepoint_client_id": "client",
        "sharepoint_client_secret": encrypt("shhh"),
    }

    assert sharepoint_settings.get_sharepoint_credentials("autre-alias") is None


def test_current_values_masks_only_the_secret():
    from app.core.crypto import encrypt

    store._overrides[sharepoint_settings.SECTION_KEY] = {
        "sharepoint_tenant_id": "tenant-123",
        "sharepoint_client_id": "",
        "sharepoint_client_secret": encrypt("shhh"),
    }

    values = sharepoint_settings._get_current_values()

    assert values["sharepoint_tenant_id"] == "tenant-123"
    assert values["sharepoint_client_secret"] == sharepoint_settings.MASKED_SECRET


def test_pre_store_keeps_existing_secret_when_submitted_empty():
    existing = {"sharepoint_client_secret": "already-encrypted"}

    result = sharepoint_settings._pre_store(
        {"sharepoint_tenant_id": "t1", "sharepoint_client_secret": ""}, existing=existing
    )

    assert result["sharepoint_client_secret"] == "already-encrypted"
    assert result["sharepoint_tenant_id"] == "t1"
