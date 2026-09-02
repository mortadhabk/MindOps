import httpx
import pytest

from app.connectors.github.connector import GitHubConnector
from app.core.exceptions import ConnectorError

ISSUES_PAGE_1 = [
    {
        "number": 1,
        "title": "Le paiement echoue",
        "body": "Depassement du champ DECIMAL",
        "html_url": "https://github.com/acme/repo/issues/1",
        "comments": 1,
        "comments_url": "https://api.github.com/repos/acme/repo/issues/1/comments",
    },
    {
        "number": 2,
        "title": "Une pull request, pas une issue",
        "body": "",
        "html_url": "https://github.com/acme/repo/pull/2",
        "comments": 0,
        "comments_url": "https://api.github.com/repos/acme/repo/issues/2/comments",
        "pull_request": {"url": "https://api.github.com/repos/acme/repo/pulls/2"},
    },
]


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/repos/acme/repo/issues" and request.url.params.get("page") == "1":
        return httpx.Response(200, json=ISSUES_PAGE_1)
    if request.url.path == "/repos/acme/repo/issues" and request.url.params.get("page") == "2":
        return httpx.Response(200, json=[])
    if request.url.path == "/repos/acme/repo/issues/1/comments":
        return httpx.Response(200, json=[{"body": "Corrige en 2.3.1"}])
    return httpx.Response(404, json={"message": "not found"})


@pytest.fixture(autouse=True)
def _patch_client(monkeypatch):
    transport = httpx.MockTransport(_handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


async def test_fetch_items_filters_pull_requests_and_follows_pagination():
    connector = GitHubConnector()

    items = await connector.fetch_items(owner="acme", repo="repo")

    assert len(items) == 1
    assert items[0].issue.number == 1
    assert items[0].comments == ["Corrige en 2.3.1"]


async def test_to_document_includes_title_body_and_comments():
    connector = GitHubConnector()
    items = await connector.fetch_items(owner="acme", repo="repo")

    document = connector.to_document(items[0])

    assert document.source == "github:acme/repo#1"
    assert "Le paiement echoue" in document.content
    assert "Corrige en 2.3.1" in document.content


async def test_fetch_items_raises_connector_error_for_unknown_repo():
    connector = GitHubConnector()

    with pytest.raises(ConnectorError):
        await connector.fetch_items(owner="acme", repo="does-not-exist")
