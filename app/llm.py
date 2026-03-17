from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import openai

from app.config import (
    LLM_API_BASE,
    LLM_MAX_TOKENS,
    LLM_MODEL_NAME,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
    OPENROUTER_API_KEY,
    OPENROUTER_APP_NAME,
    OPENROUTER_SITE_URL,
)

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base error for LLM integration."""


class LLMRequestError(LLMError):
    """Raised when the OpenRouter / OpenAI-compatible API returns an error."""


class LLMClient:
    """OpenRouter client using the OpenAI-compatible API.

    Implements the ``ChatClient`` protocol expected by ``agent.run_agent``.

    Args:
        api_key:     OpenRouter API key. Falls back to ``OPENROUTER_API_KEY`` env var.
        base_url:    API base URL. Defaults to ``https://openrouter.ai/api/v1``.
        model:       Model ID in OpenRouter format (e.g. ``"meta-llama/llama-3.3-70b-instruct"``).
        max_tokens:  Maximum tokens in the response.
        temperature: Sampling temperature.
        http_client: Optional custom ``httpx.Client`` for injecting mock transports
                     in tests (passed through to the underlying OpenAI client).
    """

    def __init__(
        self,
        api_key: str = OPENROUTER_API_KEY,
        base_url: str = LLM_API_BASE,
        model: str = LLM_MODEL_NAME,
        max_tokens: int = LLM_MAX_TOKENS,
        temperature: float = LLM_TEMPERATURE,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise LLMRequestError(
                "OPENROUTER_API_KEY is not set. "
                "Add it to your .env file and restart the server."
            )

        # OpenRouter recommends these headers for request attribution.
        default_headers: dict[str, str] = {}
        if OPENROUTER_SITE_URL:
            default_headers["HTTP-Referer"] = OPENROUTER_SITE_URL
        if OPENROUTER_APP_NAME:
            default_headers["X-Title"] = OPENROUTER_APP_NAME

        client_kwargs: dict[str, Any] = {
            "api_key": api_key,
            "base_url": base_url,
            "timeout": LLM_TIMEOUT,
            "default_headers": default_headers,
        }
        if http_client is not None:
            client_kwargs["http_client"] = http_client

        self._client = openai.OpenAI(**client_kwargs)
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature

    # ------------------------------------------------------------------
    # ChatClient protocol
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str,
    ) -> dict[str, Any]:
        """Send a conversation turn to OpenRouter and return a normalised response.

        The system prompt is prepended as the first message so the caller
        (``agent.run_agent``) can keep its message list tool-turn-only.

        Return value shape::

            {
                "stop_reason":       "tool_calls" | "stop",
                "assistant_message": dict,             # OpenAI-format, for history
                "text":              str,              # text content (may be "")
                "tool_calls":        list | None,      # parsed calls with id/name/input
            }

        Args:
            messages: Conversation history **without** the system message.
            tools:    Tool definitions in OpenAI function-calling format.
                      Pass ``[]`` to disable tool use.
            system:   System prompt (prepended internally).
        """
        all_messages = [{"role": "system", "content": system}, *messages]

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": all_messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        logger.debug(
            "[llm] chat model=%s messages=%d tools=%d",
            self._model,
            len(all_messages),
            len(tools),
        )

        try:
            response = self._client.chat.completions.create(**kwargs)
        except openai.APIConnectionError as exc:
            raise LLMRequestError(f"Connection error: {exc}") from exc
        except openai.RateLimitError as exc:
            raise LLMRequestError(f"Rate limit exceeded: {exc}") from exc
        except openai.APIStatusError as exc:
            raise LLMRequestError(
                f"API error {exc.status_code}: {exc.message}"
            ) from exc

        if not response.choices:
            raise LLMRequestError(
                "Empty response from API: choices is None or empty. "
                "The model may not support tool use or returned an unexpected format."
            )

        choice = response.choices[0]
        finish_reason: str = choice.finish_reason or "stop"
        message = choice.message

        logger.debug(
            "[llm] response finish_reason=%s text_length=%d tool_calls=%d",
            finish_reason,
            len(message.content or ""),
            len(message.tool_calls or []),
        )
        logger.debug("[llm] raw content=%r", message.content)

        if finish_reason == "length":
            raise LLMRequestError(
                "Response truncated: max_tokens limit reached. "
                "Increase LLM_MAX_TOKENS or reduce the prompt."
            )

        return _build_response(finish_reason, message)

    # ------------------------------------------------------------------
    # Convenience wrapper for single-turn calls (no tools)
    # ------------------------------------------------------------------

    def generate(self, prompt: str) -> str:
        """Single-turn generation without tool use.

        Kept for lightweight use-cases and testing.
        Internally delegates to ``chat()``.
        """
        response = self.chat(
            messages=[{"role": "user", "content": prompt}],
            tools=[],
            system="You are a technical writer.",
        )
        return response["text"]

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_response(
    finish_reason: str,
    message: Any,  # openai.types.chat.ChatCompletionMessage
) -> dict[str, Any]:
    """Normalise an OpenAI SDK message object into the dict format the agent expects."""
    text: str = message.content or ""
    raw_tool_calls = message.tool_calls or []

    # Build the assistant message for history (OpenAI wire format).
    assistant_message: dict[str, Any] = {"role": "assistant", "content": text or None}
    if raw_tool_calls:
        assistant_message["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in raw_tool_calls
        ]

    # Parse tool calls into a friendlier shape for the agent loop.
    tool_calls: list[dict[str, Any]] | None = None
    if raw_tool_calls:
        tool_calls = []
        for tc in raw_tool_calls:
            try:
                parsed_input = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                parsed_input = {}
            tool_calls.append(
                {"id": tc.id, "name": tc.function.name, "input": parsed_input}
            )

    return {
        "stop_reason": "tool_calls" if finish_reason == "tool_calls" else "stop",
        "assistant_message": assistant_message,
        "text": text,
        "tool_calls": tool_calls,
    }
