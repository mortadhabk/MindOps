from app.connectors.sharepoint.connector import SharePointConnector

SITE_URL = "https://acme.sharepoint.com/sites/support"


async def test_fetch_items_returns_fixed_items_tagged_with_the_given_site():
    connector = SharePointConnector()

    items = await connector.fetch_items(site_url=SITE_URL)

    assert len(items) == 2
    assert all(item.site_url == SITE_URL for item in items)


async def test_to_document_builds_a_stable_source_identifier():
    connector = SharePointConnector()
    items = await connector.fetch_items(site_url=SITE_URL, library_name="Documents partagés")

    document = connector.to_document(items[0])

    assert document.source == f"sharepoint:{SITE_URL}/Documents partagés#1"
    assert items[0].title in document.content
    assert items[0].text in document.content
