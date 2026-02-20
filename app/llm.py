from __future__ import annotations

import httpx

from app.config import (
    HUGGINGFACE_API_TOKEN,
    LLM_API_BASE,
    LLM_MAX_NEW_TOKENS,
    LLM_MODEL_NAME,
    LLM_MODEL_SUFFIX,
    LLM_PROVIDER,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
)


class LLMError(Exception):
    """Base error for LLM integration."""


class LLMRequestError(LLMError):
    """Raised when LLM API returns an error."""


class LLMClient:
    def __init__(
        self,
        base_url: str = LLM_API_BASE,
        model: str = LLM_MODEL_NAME,
        provider: str = LLM_PROVIDER,
        hf_token: str = HUGGINGFACE_API_TOKEN,
        timeout: float = LLM_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)
        self._model = model
        self._provider = provider
        self._hf_token = hf_token

    def generate(self, prompt: str) -> str:
        if self._provider == "hf":
            payload = {
                "inputs": prompt,
                "parameters": {
                    "temperature": LLM_TEMPERATURE,
                    "max_new_tokens": LLM_MAX_NEW_TOKENS,
                },
                "options": {"wait_for_model": True},
            }
            headers = {}
            if self._hf_token:
                headers["Authorization"] = f"Bearer {self._hf_token}"

            print(f"[llm] provider=hf base_url={self._client.base_url} path=")
            response = self._client.post("", json=payload, headers=headers)
            if response.status_code >= 400:
                body = response.text[:300]
                print(
                    "[llm] hf_error status=%s body=%s"
                    % (response.status_code, body)
                )
                raise LLMRequestError(f"LLM API error: {response.status_code}")

            data = response.json()
            if isinstance(data, list) and data and "generated_text" in data[0]:
                return data[0]["generated_text"]
            if isinstance(data, dict) and "generated_text" in data:
                return data["generated_text"]
            raise LLMRequestError("Invalid HF response format")

        if self._provider == "hf_router":
            model_id = (
                self._model
                if ":" in self._model
                else f"{self._model}:{LLM_MODEL_SUFFIX}"
            )
            payload = {
                "model": model_id,
                "messages": [
                    {"role": "user", "content": prompt},
                ],
                "temperature": LLM_TEMPERATURE,
                "stream": False,
            }
            headers = {"Content-Type": "application/json"}
            if self._hf_token:
                headers["Authorization"] = f"Bearer {self._hf_token}"

            print(
                f"[llm] provider=hf_router base_url={self._client.base_url} path=/v1/chat/completions"
            )
            response = self._client.post("/v1/chat/completions", json=payload, headers=headers)
            if response.status_code >= 400:
                body = response.text[:300]
                print(
                    "[llm] hf_router_error status=%s body=%s"
                    % (response.status_code, body)
                )
                raise LLMRequestError(f"LLM API error: {response.status_code}")

            data = response.json()
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise LLMRequestError("Invalid HF Router response format") from exc

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "You are a technical writer."},
                {"role": "user", "content": prompt},
            ],
            "temperature": LLM_TEMPERATURE,
        }

        print(f"[llm] provider=openai base_url={self._client.base_url} path=/v1/chat/completions")
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
