from app.connectors.mock.connector import MockConnector


async def test_fetch_items_returns_fixed_items():
    connector = MockConnector()

    items = await connector.fetch_items()

    assert len(items) == 2


def test_to_document_maps_title_and_body():
    connector = MockConnector()
    item = {"id": 1, "title": "Titre", "body": "Corps"}

    document = connector.to_document(item)

    assert document.source == "mock#1"
    assert "Titre" in document.content
    assert "Corps" in document.content
