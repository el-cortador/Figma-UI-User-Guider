"""API endpoint tests.

Strategy
--------
* ``/figma/file`` and ``/figma/file/filtered``: mock FigmaClient via FastAPI
  dependency override using httpx.MockTransport (unchanged approach).
* ``/guide/generate`` and ``/guide/export``: patch ``app.main.run_agent``
  directly — this is the correct boundary now that the endpoints delegate to
  the agent loop rather than calling Figma/LLM inline.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agent import AgentError, AgentResult, MaxIterationsError
from app.figma import FigmaClient
from app.llm import LLMClient, LLMRequestError
from app.main import app, get_figma_client, get_llm_client

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_FIGMA_RESPONSE = {"name": "Demo", "document": {"id": "0:0", "children": []}}

_AGENT_RESULT = AgentResult(
    markdown="# Руководство\n\nШаг 1: Откройте приложение.",
    guide_json={"title": "Demo", "steps": [{"index": 1, "title": "Шаг 1", "description": "Откройте приложение."}]},
)

_GUIDE_PAYLOAD = {
    "figma_url": "https://www.figma.com/file/AbCdEf1234/My-File",
    "figma_token": "token",
    "language": "ru",
    "detail_level": "brief",
}


# ---------------------------------------------------------------------------
# Dependency overrides
# ---------------------------------------------------------------------------


def _figma_override():
    """FigmaClient that returns a minimal valid Figma JSON."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_FIGMA_RESPONSE)

    transport = httpx.MockTransport(handler)
    client = FigmaClient(transport=transport)
    try:
        yield client
    finally:
        client.close()


def _llm_override():
    """LLMClient placeholder — guide endpoints are tested by patching run_agent."""
    from unittest.mock import MagicMock
    yield MagicMock(spec=LLMClient)


app.dependency_overrides[get_figma_client] = _figma_override
app.dependency_overrides[get_llm_client] = _llm_override


# ---------------------------------------------------------------------------
# /figma/file
# ---------------------------------------------------------------------------


def test_fetch_figma_file_success() -> None:
    client = TestClient(app)
    response = client.post(
        "/figma/file",
        json={"figma_url": "https://www.figma.com/file/AbCdEf1234/My-File", "figma_token": "token"},
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


def test_fetch_figma_file_auth_error() -> None:
    def auth_fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    def override():
        client = FigmaClient(transport=httpx.MockTransport(auth_fail))
        try:
            yield client
        finally:
            client.close()

    app.dependency_overrides[get_figma_client] = override
    try:
        response = TestClient(app).post(
            "/figma/file",
            json={"figma_url": "https://www.figma.com/file/AbCdEf1234/X", "figma_token": "bad"},
        )
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_figma_client] = _figma_override


def test_fetch_figma_file_not_found() -> None:
    def not_found(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    def override():
        client = FigmaClient(transport=httpx.MockTransport(not_found))
        try:
            yield client
        finally:
            client.close()

    app.dependency_overrides[get_figma_client] = override
    try:
        response = TestClient(app).post(
            "/figma/file",
            json={"figma_url": "https://www.figma.com/file/AbCdEf1234/X", "figma_token": "t"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides[get_figma_client] = _figma_override


# ---------------------------------------------------------------------------
# /figma/file/filtered
# ---------------------------------------------------------------------------


def test_fetch_filtered_figma_file_success() -> None:
    client = TestClient(app)
    response = client.post(
        "/figma/file/filtered",
        json={"figma_url": "https://www.figma.com/file/AbCdEf1234/My-File", "figma_token": "token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == "AbCdEf1234"
    assert "filtered_json" in data


# ---------------------------------------------------------------------------
# /guide/generate
# ---------------------------------------------------------------------------


def test_generate_guide_success() -> None:
    with patch("app.main.run_agent", return_value=_AGENT_RESULT):
        client = TestClient(app)
        response = client.post("/guide/generate", json=_GUIDE_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == "AbCdEf1234"
    assert data["markdown"] == _AGENT_RESULT.markdown
    assert data["guide_json"] == _AGENT_RESULT.guide_json


def test_generate_guide_bad_url() -> None:
    client = TestClient(app)
    response = client.post(
        "/guide/generate",
        json={**_GUIDE_PAYLOAD, "figma_url": "https://example.com"},
    )
    assert response.status_code == 400


def test_generate_guide_missing_token() -> None:
    # Patch the module-level constant so a real FIGMA_API_TOKEN in .env
    # does not silently satisfy the token check during this test.
    with patch("app.main.FIGMA_API_TOKEN", ""):
        client = TestClient(app)
        response = client.post(
            "/guide/generate",
            json={**_GUIDE_PAYLOAD, "figma_token": ""},
        )
    assert response.status_code == 400


def test_generate_guide_llm_error() -> None:
    with patch("app.main.run_agent", side_effect=LLMRequestError("API unavailable")):
        response = TestClient(app).post("/guide/generate", json=_GUIDE_PAYLOAD)
    assert response.status_code == 502


def test_generate_guide_max_iterations() -> None:
    with patch("app.main.run_agent", side_effect=MaxIterationsError("too many")):
        response = TestClient(app).post("/guide/generate", json=_GUIDE_PAYLOAD)
    assert response.status_code == 504


def test_generate_guide_agent_error() -> None:
    with patch("app.main.run_agent", side_effect=AgentError("unexpected stop_reason")):
        response = TestClient(app).post("/guide/generate", json=_GUIDE_PAYLOAD)
    assert response.status_code == 502


# ---------------------------------------------------------------------------
# /guide/export
# ---------------------------------------------------------------------------


def test_export_guide_success() -> None:
    with patch("app.main.run_agent", return_value=_AGENT_RESULT):
        response = TestClient(app).post("/guide/export", json=_GUIDE_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == "AbCdEf1234"
    assert "markdown" in data
    assert "guide_json" in data


def test_export_guide_max_iterations() -> None:
    with patch("app.main.run_agent", side_effect=MaxIterationsError("too many")):
        response = TestClient(app).post("/guide/export", json=_GUIDE_PAYLOAD)
    assert response.status_code == 504