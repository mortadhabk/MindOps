from app.connectors.document.connector import DocumentConnector


async def test_fetch_items_returns_the_config_itself_as_a_single_item():
    connector = DocumentConnector()

    items = await connector.fetch_items(source="note-1", content="Le contenu du document.")

    assert items == [{"source": "note-1", "content": "Le contenu du document."}]


async def test_to_document_maps_source_and_content():
    connector = DocumentConnector()
    items = await connector.fetch_items(source="note-1", content="Le contenu du document.")

    document = connector.to_document(items[0])

    assert document.source == "note-1"
    assert document.content == "Le contenu du document."
