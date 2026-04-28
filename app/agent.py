from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol

from app.generation import parse_llm_output
from app.prompts import BRIEF_SYSTEM_PROMPT
from app.tools import TOOL_DEFINITIONS, ToolContext, ToolError, dispatch_tool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AgentError(Exception):
    """Raised when the agent loop encounters an unrecoverable error."""


class MaxIterationsError(AgentError):
    """Raised when the agent exceeds the allowed number of iterations."""


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    markdown: str
    guide_json: dict


# ---------------------------------------------------------------------------
# ChatClient protocol
# ---------------------------------------------------------------------------


class ChatClient(Protocol):
    """Minimal interface the agent expects from an LLM client.

    ``chat()`` must return a dict with these keys:

    * ``stop_reason``:       ``"tool_calls"`` | ``"stop"``
    * ``assistant_message``: dict in OpenAI wire format (for appending to history)
    * ``text``:              str — concatenated text content (may be ``""`` on tool turns)
    * ``tool_calls``:        ``list[dict] | None`` — each item has ``id``, ``name``,
                             and ``input`` (already parsed from JSON string)

    The system prompt is passed as a separate ``system`` parameter so the caller
    does not need to inject it into the message list manually.
    """

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: str,
    ) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_vision_request(language: str, detail_level: str) -> str:
    """Construct the user message for a vision-based (image upload) agent call."""
    return (
        "Проанализируй изображение макета интерфейса и создай руководство пользователя.\n\n"
        f"Язык руководства: {language}\n"
        f"Уровень детализации: {detail_level}\n"
        "Структура:\n- Назначение интерфейса;\n- Порядок шагов;\n- Ожидаемый результат."
    )


def run_vision_agent(
    image_base64: str,
    mime_type: str,
    language: str,
    detail_level: str,
    llm: ChatClient,
    system_prompt: str,
) -> AgentResult:
    """Single-turn vision LLM call — no tool loop needed for image uploads."""
    user_message: dict[str, Any] = {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
            },
            {"type": "text", "text": build_vision_request(language, detail_level)},
        ],
    }

    response = llm.chat(messages=[user_message], tools=[], system=system_prompt)

    text: str = response["text"]
    if not text.strip():
        raise AgentError(
            "Модель не вернула ответ на изображение. "
            "Убедитесь, что выбранная модель поддерживает анализ изображений (vision)."
        )

    markdown, guide_json = parse_llm_output(text)
    return AgentResult(markdown=markdown, guide_json=guide_json)


def build_user_request(
    figma_url: str,
    figma_token: str,
    language: str,
    detail_level: str,
) -> str:
    """Construct the initial user message for the agent."""
    return (
        "Создай руководство пользователя на макет интерфейса из Figma-файла.\n\n"
        f"URL файла: {figma_url}\n"
        f"Токен Figma: {figma_token}\n"
        f"Язык руководства: {language}\n"
        f"Уровень детализации: {detail_level}\n"
        "Структура руководства пользователя:\n\n- Назначение интерфейса;\n - Порядок шагов, выполняемых пользователем;\n - Какой возможный результат после выполнения этих шагов."
    )


def run_agent(
    user_request: str,
    ctx: ToolContext,
    llm: ChatClient,
    system_prompt: str = BRIEF_SYSTEM_PROMPT,
    max_iterations: int = 10,
) -> AgentResult:
    """Run the agent loop until a final answer is produced.

    Each iteration either:

    * Receives ``stop_reason == "tool_calls"``: executes every requested tool,
      appends OpenAI-format tool-result messages, and continues.
    * Receives ``stop_reason == "stop"``: parses the final text and returns.

    Messages are kept in **OpenAI format** throughout:

    * Tool-call turns:   ``{"role": "assistant", "content": None, "tool_calls": [...]}``
    * Tool-result turns: ``{"role": "tool", "tool_call_id": ..., "content": ...}``
      — one message per call (``extend``, not ``append``).

    Args:
        user_request:   The initial user message (use ``build_user_request``).
        ctx:            Request-scoped tool context holding caches and clients.
        llm:            Any object implementing ``ChatClient``.
        system_prompt:  System prompt controlling the guide style. Use
                        ``app.prompts.get_system_prompt(detail_level)`` to
                        select between brief and detailed variants.
        max_iterations: Safety cap on the number of LLM round-trips.

    Raises:
        MaxIterationsError: Agent did not finish within ``max_iterations`` turns.
        AgentError:         Unexpected ``stop_reason`` from the LLM.
    """
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_request}]

    for iteration in range(max_iterations):
        logger.debug("[agent] iteration=%d messages=%d", iteration + 1, len(messages))

        response = llm.chat(messages=messages, tools=TOOL_DEFINITIONS, system=system_prompt)

        # Always record the assistant turn before branching.
        messages.append(response["assistant_message"])

        stop_reason: str = response["stop_reason"]

        if stop_reason == "tool_calls":
            tool_calls: list[dict[str, Any]] = response["tool_calls"] or []
            tool_messages = _execute_tool_calls(tool_calls, ctx)
            # One message per tool call — extend, not append.
            messages.extend(tool_messages)
            continue

        if stop_reason == "stop":
            text: str = response["text"]
            logger.info(
                "[agent] final text iteration=%d length=%d preview=%r",
                iteration + 1,
                len(text),
                text[:200],
            )
            if not text.strip():
                raise AgentError(
                    "Модель вернула пустой ответ на финальном шаге. "
                    "Возможно, модель не поддерживает вызов инструментов или не смогла "
                    "сгенерировать руководство. Попробуйте сменить модель в настройках."
                )
            markdown, guide_json = parse_llm_output(text)
            logger.info("[agent] finished in %d iteration(s)", iteration + 1)
            return AgentResult(markdown=markdown, guide_json=guide_json)

        raise AgentError(f"Unexpected stop_reason from LLM: '{stop_reason}'")

    raise MaxIterationsError(
        f"Agent did not produce a final answer within {max_iterations} iterations"
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _execute_tool_calls(
    tool_calls: list[dict[str, Any]],
    ctx: ToolContext,
) -> list[dict[str, Any]]:
    """Execute every tool call and return one ``role: "tool"`` message each.

    Uses OpenAI / Fireworks tool-result format.
    Errors are returned as JSON content so the model can decide how to recover
    without breaking the agent loop.
    """
    messages: list[dict[str, Any]] = []

    for tc in tool_calls:
        tool_id: str = tc["id"]
        tool_name: str = tc["name"]
        tool_input: dict[str, Any] = tc["input"]

        logger.info("[agent] tool_call name=%s input_keys=%s", tool_name, list(tool_input))

        try:
            output = dispatch_tool(tool_name, tool_input, ctx)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": json.dumps(output, ensure_ascii=False),
                }
            )
            logger.info("[agent] tool_result name=%s status=ok", tool_name)
        except ToolError as exc:
            logger.warning(
                "[agent] tool_result name=%s status=error error=%s", tool_name, exc
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": json.dumps({"error": str(exc)}, ensure_ascii=False),
                }
            )

    return messages
