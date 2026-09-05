import re

from httpx import AsyncClient


async def test_demo_serves_the_static_page(client: AsyncClient) -> None:
    response = await client.get("/demo/")

    assert response.status_code == 200
    assert "Agent IA" in response.text


async def test_demo_serves_its_built_assets(client: AsyncClient) -> None:
    """Les noms de fichiers du build Vite sont hashés (ex: assets/index-BG7IHB6r.js) et changent
    à chaque build : on les extrait de l'index servi plutôt que de les coder en dur."""
    index = await client.get("/demo/")
    asset_paths = re.findall(r'(?:src|href)="(/demo/assets/[^"]+)"', index.text)

    assert asset_paths, (
        "aucun asset référencé dans app/static/index.html — le front a-t-il été buildé ?"
    )
    for path in asset_paths:
        response = await client.get(path)
        assert response.status_code == 200
