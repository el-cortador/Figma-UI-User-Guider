import httpx
from fastapi.testclient import TestClient

from app.figma import FigmaClient
from app.main import app, get_figma_client


def override_client():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"name": "Demo"})

    transport = httpx.MockTransport(handler)
    client = FigmaClient(transport=transport)
    try:
        yield client
    finally:
        client.close()


app.dependency_overrides[get_figma_client] = override_client


def test_fetch_figma_file_success() -> None:
    client = TestClient(app)
    response = client.post(
        "/figma/file",
        json={
            "figma_url": "https://www.figma.com/file/AbCdEf1234/My-File",
            "figma_token": "token",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == "AbCdEf1234"
    assert data["figma_json"]["name"] == "Demo"


def test_fetch_figma_file_bad_url() -> None:
    client = TestClient(app)
    response = client.post(
        "/figma/file",
        json={"figma_url": "https://example.com", "figma_token": "token"},
    )
    assert response.status_code == 400
