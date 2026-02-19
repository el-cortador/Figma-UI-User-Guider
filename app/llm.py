from __future__ import annotations

import httpx

from app.config import LLM_API_BASE, LLM_MODEL_NAME, LLM_TIMEOUT


class LLMError(Exception):
    """Base error for LLM integration."""


class LLMRequestError(LLMError):
    """Raised when LLM API returns an error."""


class LLMClient:
    def __init__(
        self,
        base_url: str = LLM_API_BASE,
        model: str = LLM_MODEL_NAME,
        timeout: float = LLM_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)
        self._model = model

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "You are a technical writer."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        response = self._client.post("/v1/chat/completions", json=payload)
        if response.status_code >= 400:
            raise LLMRequestError(f"LLM API error: {response.status_code}")

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMRequestError("Invalid LLM response format") from exc

    def close(self) -> None:
        self._client.close()
