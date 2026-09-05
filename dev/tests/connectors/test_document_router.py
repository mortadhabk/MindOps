from httpx import AsyncClient


async def test_extract_text_from_plain_text_file(client: AsyncClient):
    response = await client.post(
        "/connectors/document/extract-text",
        files={"file": ("note.txt", b"Contenu du fichier", "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "Contenu du fichier"
    assert body["suggested_source"] == "note"


async def test_extract_text_rejects_unsupported_format(client: AsyncClient):
    response = await client.post(
        "/connectors/document/extract-text",
        files={"file": ("image.png", b"\x89PNG\r\n", "image/png")},
    )

    assert response.status_code == 422
