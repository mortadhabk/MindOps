import httpx
import pytest

from app.config import get_settings
from app.connectors.sharepoint import graph_client
from app.connectors.sharepoint.connector import SharePointConnector
from app.core.exceptions import ConnectorConfigError, ConnectorError

HOSTNAME = "orange0.sharepoint.com"
SITE_URL = (
    "https://orange0.sharepoint.com/sites/ENACWebFactory-TMAPowerPlatform/"
    "Documents%20partages/Forms/AllItems.aspx?FolderCTID=0x0120004D087DF5E6F59741A8EA50B6A3216FDB"
    "&id=%2Fsites%2FENACWebFactory%2DTMAPowerPlatform%2FDocuments%20partages%2FGeneral"
    "%2FDocumentations%2FPortail%20ENIX"
)


def test_parse_sharepoint_url_extracts_site_library_and_folder():
    location = graph_client.parse_sharepoint_url(SITE_URL)

    assert location.hostname == HOSTNAME
    assert location.site_path == "/sites/ENACWebFactory-TMAPowerPlatform"
    assert location.library_name == "Documents partages"
    assert location.folder_path == "General/Documentations/Portail ENIX"


def test_parse_sharepoint_url_rejects_non_sharepoint_host():
    with pytest.raises(ConnectorConfigError):
        graph_client.parse_sharepoint_url("https://example.com/sites/foo")


FILE_1 = {
    "id": "file-1",
    "name": "guide.pdf",
    "webUrl": "https://orange0.sharepoint.com/.../guide.pdf",
    "file": {},
    "@microsoft.graph.downloadUrl": "https://download.example/guide.pdf",
}
FILE_IGNORED = {
    "id": "file-2",
    "name": "diagramme.vsdx",  # extension non supportée : doit être ignorée, pas en erreur
    "webUrl": "https://orange0.sharepoint.com/.../diagramme.vsdx",
    "file": {},
    "@microsoft.graph.downloadUrl": "https://download.example/diagramme.vsdx",
}
SUBFOLDER = {"id": "folder-1", "name": "Sous-dossier", "folder": {"childCount": 1}}
FILE_2 = {
    "id": "file-3",
    "name": "notes.txt",
    "webUrl": "https://orange0.sharepoint.com/.../notes.txt",
    "file": {},
    "@microsoft.graph.downloadUrl": "https://download.example/notes.txt",
}


def _handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    path = request.url.path

    if host == "login.microsoftonline.com":
        if request.url.path == "/tenant-invalid/oauth2/v2.0/token":
            return httpx.Response(401, json={"error": "invalid_client"})
        return httpx.Response(200, json={"access_token": "fake-token", "expires_in": 3600})

    if host == "graph.microsoft.com":
        if path == "/v1.0/sites/orange0.sharepoint.com:/sites/ENACWebFactory-TMAPowerPlatform":
            return httpx.Response(200, json={"id": "site-1"})
        if path == "/v1.0/sites/site-1/drives":
            return httpx.Response(
                200, json={"value": [{"id": "drive-1", "name": "Documents partages"}]}
            )
        if path == "/v1.0/drives/drive-1/root:/General/Documentations/Portail ENIX:/children":
            return httpx.Response(200, json={"value": [FILE_1, FILE_IGNORED, SUBFOLDER]})
        subfolder_path = (
            "/v1.0/drives/drive-1/root:/General/Documentations/Portail ENIX"
            "/Sous-dossier:/children"
        )
        if path == subfolder_path:
            return httpx.Response(200, json={"value": [FILE_2]})
        return httpx.Response(404, json={"error": "not found"})

    if host == "download.example":
        if path == "/guide.pdf":
            return httpx.Response(200, content=b"%PDF-1.4 fake but unused in this test")
        if path == "/notes.txt":
            return httpx.Response(200, content=b"Contenu du sous-dossier")
        return httpx.Response(404)

    return httpx.Response(404)


@pytest.fixture(autouse=True)
def _sharepoint_credentials(monkeypatch):
    monkeypatch.setenv("SHAREPOINT_TENANT_ID", "tenant-1")
    monkeypatch.setenv("SHAREPOINT_CLIENT_ID", "client-1")
    monkeypatch.setenv("SHAREPOINT_CLIENT_SECRET", "secret-1")
    get_settings.cache_clear()
    graph_client._token_cache.clear()
    yield
    get_settings.cache_clear()
    graph_client._token_cache.clear()


@pytest.fixture(autouse=True)
def _patch_client(monkeypatch):
    transport = httpx.MockTransport(_handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

    # extract_text() n'a pas besoin d'un vrai PDF pour ce test : on court-circuite l'extraction
    # PDF (pypdf lèverait sur ce faux contenu) pour se concentrer sur le parcours récursif.
    import app.connectors.document.extraction as extraction_module

    monkeypatch.setattr(extraction_module, "_extract_pdf", lambda raw_bytes: "Contenu du guide")


async def test_fetch_items_walks_subfolders_and_skips_unsupported_extensions():
    connector = SharePointConnector()

    items = await connector.fetch_items(site_url=SITE_URL)

    assert {item.name for item in items} == {"guide.pdf", "notes.txt"}


async def test_to_document_builds_a_stable_source_identifier():
    connector = SharePointConnector()
    items = await connector.fetch_items(site_url=SITE_URL)
    guide = next(item for item in items if item.name == "guide.pdf")

    document = connector.to_document(guide)

    assert document.source == "sharepoint:https://orange0.sharepoint.com/.../guide.pdf"
    assert "guide.pdf" in document.content
    assert "Contenu du guide" in document.content


async def test_fetch_items_raises_connector_config_error_for_unknown_library():
    connector = SharePointConnector()

    with pytest.raises(ConnectorConfigError):
        await connector.fetch_items(site_url=SITE_URL, library_name="Bibliothèque inexistante")


async def test_get_access_token_raises_connector_config_error_without_credentials(monkeypatch):
    monkeypatch.delenv("SHAREPOINT_TENANT_ID", raising=False)
    monkeypatch.delenv("SHAREPOINT_CLIENT_ID", raising=False)
    monkeypatch.delenv("SHAREPOINT_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()

    with pytest.raises(ConnectorConfigError):
        await graph_client.get_access_token("default")

    get_settings.cache_clear()


async def test_get_access_token_raises_connector_error_on_auth_failure(monkeypatch):
    monkeypatch.setenv("SHAREPOINT_TENANT_ID", "tenant-invalid")
    get_settings.cache_clear()

    with pytest.raises(ConnectorError):
        await graph_client.get_access_token("default")

    get_settings.cache_clear()
