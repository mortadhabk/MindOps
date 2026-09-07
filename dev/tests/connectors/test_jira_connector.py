from datetime import datetime

import httpx
import pytest

from app.config import get_settings
from app.connectors.jira.connector import JiraConnector
from app.core.exceptions import ConnectorConfigError, ConnectorError

CLOUD_BASE_URL = "https://acme.atlassian.net"
SERVER_BASE_URL = "https://jira.internal.acme.com"

CLOUD_ISSUE = {
    "key": "SUP-1",
    "fields": {
        "summary": "Le paiement échoue",
        "description": {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Dépassement du champ DECIMAL."}],
                }
            ],
        },
        "status": {"name": "Ouvert"},
        "issuetype": {"name": "Bug"},
        "labels": ["paiement"],
        "assignee": {"displayName": "Alice"},
        "attachment": [
            {
                "filename": "notes.txt",
                "content": "https://acme.atlassian.net/attachments/notes.txt",
            },
            {"filename": "capture.png", "content": "https://acme.atlassian.net/attachments/x.png"},
        ],
    },
}
CLOUD_COMMENT = {
    "body": {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Corrigé en 2.3.1"}]}
        ],
    }
}


def _cloud_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/rest/api/3/search":
        return httpx.Response(200, json={"issues": [CLOUD_ISSUE], "total": 1})
    if path == "/rest/api/3/issue/SUP-1/comment":
        return httpx.Response(200, json={"comments": [CLOUD_COMMENT], "total": 1})
    if path == "/attachments/notes.txt":
        return httpx.Response(200, content=b"Contenu du fichier joint")
    return httpx.Response(404, json={"errorMessages": ["not found"]})


SERVER_ISSUE = {
    "key": "OPS-4",
    "fields": {
        "summary": "Redémarrage du service",
        "description": "Procédure standard de redémarrage.",
        "status": {"name": "Fermé"},
        "issuetype": {"name": "Tâche"},
        "labels": [],
        "assignee": None,
        "attachment": [],
    },
}


def _server_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/rest/api/2/search":
        if "invalid_client" in request.url.params.get("jql", ""):
            return httpx.Response(401, json={"errorMessages": ["invalid PAT"]})
        return httpx.Response(200, json={"issues": [SERVER_ISSUE], "total": 1})
    if path == "/rest/api/2/issue/OPS-4/comment":
        return httpx.Response(200, json={"comments": [], "total": 0})
    return httpx.Response(404)


@pytest.fixture(autouse=True)
def _jira_credentials(monkeypatch):
    monkeypatch.setenv("JIRA_CLOUD_EMAIL", "bot@acme.com")
    monkeypatch.setenv("JIRA_CLOUD_API_TOKEN", "cloud-token")
    monkeypatch.setenv("JIRA_SERVER_TOKEN", "server-pat")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _patch_transport(monkeypatch, handler) -> None:
    transport = httpx.MockTransport(handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


async def test_fetch_items_cloud_converts_adf_and_includes_comments_and_attachments(monkeypatch):
    _patch_transport(monkeypatch, _cloud_handler)
    connector = JiraConnector()

    items = await connector.fetch_items(base_url=CLOUD_BASE_URL, project_key="SUP")

    assert len(items) == 1
    text = items[0].text
    assert "[SUP-1] Le paiement échoue" in text
    assert "Dépassement du champ DECIMAL." in text
    assert "Corrigé en 2.3.1" in text
    assert "Contenu du fichier joint" in text
    assert "capture.png (non traité, format non pris en charge)" in text


async def test_to_document_builds_a_stable_source_identifier(monkeypatch):
    _patch_transport(monkeypatch, _cloud_handler)
    connector = JiraConnector()
    items = await connector.fetch_items(base_url=CLOUD_BASE_URL, project_key="SUP")

    document = connector.to_document(items[0])

    assert document.source == "jira:https://acme.atlassian.net/browse/SUP-1"


async def test_fetch_items_server_uses_plain_text_description_and_bearer_auth(monkeypatch):
    _patch_transport(monkeypatch, _server_handler)
    connector = JiraConnector()

    items = await connector.fetch_items(
        base_url=SERVER_BASE_URL, project_key="OPS", deployment_type="server"
    )

    assert len(items) == 1
    assert "Procédure standard de redémarrage." in items[0].text


async def test_fetch_items_passes_since_as_a_jql_filter(monkeypatch):
    captured_jql: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/api/3/search":
            captured_jql.append(request.url.params.get("jql", ""))
            return httpx.Response(200, json={"issues": [], "total": 0})
        return httpx.Response(404)

    _patch_transport(monkeypatch, handler)
    connector = JiraConnector()

    await connector.fetch_items(
        base_url=CLOUD_BASE_URL, project_key="SUP", since=datetime(2026, 1, 1, 8, 30)
    )

    assert 'updated >= "2026-01-01 08:30"' in captured_jql[0]


async def test_fetch_items_raises_connector_config_error_without_credentials(monkeypatch):
    monkeypatch.delenv("JIRA_CLOUD_EMAIL", raising=False)
    monkeypatch.delenv("JIRA_CLOUD_API_TOKEN", raising=False)
    get_settings.cache_clear()
    connector = JiraConnector()

    with pytest.raises(ConnectorConfigError):
        await connector.fetch_items(base_url=CLOUD_BASE_URL, project_key="SUP")

    get_settings.cache_clear()


async def test_fetch_items_raises_connector_error_on_auth_failure(monkeypatch):
    _patch_transport(monkeypatch, _server_handler)
    connector = JiraConnector()

    with pytest.raises(ConnectorError):
        await connector.fetch_items(
            base_url=SERVER_BASE_URL,
            project_key="invalid_client",
            deployment_type="server",
        )
