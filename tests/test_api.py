import httpx
from fastapi.testclient import TestClient

from app.figma import FigmaClient
from app.llm import LLMClient
from app.main import app, get_figma_client, get_llm_client


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


def override_llm_client():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = [
            {
                "generated_text": "MARKDOWN:\nШаг 1. Тест\n\nJSON:\n{\"title\": \"Demo\", \"steps\": []}"
            }
        ]
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = LLMClient(
        transport=transport,
        provider="hf",
        base_url="https://router.huggingface.co/hf-inference/models/HuggingFaceTB/SmolLM3-3B",
    )
    try:
        yield client
    finally:
        client.close()


app.dependency_overrides[get_llm_client] = override_llm_client


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


def test_fetch_filtered_figma_file_success() -> None:
    client = TestClient(app)
    response = client.post(
        "/figma/file/filtered",
        json={
            "figma_url": "https://www.figma.com/file/AbCdEf1234/My-File",
            "figma_token": "token",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == "AbCdEf1234"
    assert "filtered_json" in data


def test_generate_guide_success() -> None:
    client = TestClient(app)
    response = client.post(
        "/guide/generate",
        json={
            "figma_url": "https://www.figma.com/file/AbCdEf1234/My-File",
            "figma_token": "token",
            "language": "ru",
            "detail_level": "brief",
            "audience": "user",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == "AbCdEf1234"
    assert "markdown" in data
    assert "guide_json" in data


def test_export_guide_success() -> None:
    client = TestClient(app)
    response = client.post(
        "/guide/export",
        json={
            "figma_url": "https://www.figma.com/file/AbCdEf1234/My-File",
            "figma_token": "token",
            "language": "ru",
            "detail_level": "brief",
            "audience": "user",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == "AbCdEf1234"
    assert "markdown" in data
    assert "guide_json" in data
