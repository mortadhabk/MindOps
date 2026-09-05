from httpx import AsyncClient


async def test_demo_serves_the_static_page(client: AsyncClient) -> None:
    response = await client.get("/demo/")

    assert response.status_code == 200
    assert "Agent IA" in response.text


async def test_demo_serves_its_script_and_stylesheet(client: AsyncClient) -> None:
    js_response = await client.get("/demo/app.js")
    css_response = await client.get("/demo/style.css")

    assert js_response.status_code == 200
    assert css_response.status_code == 200
