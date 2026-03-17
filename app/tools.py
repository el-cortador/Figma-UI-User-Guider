from __future__ import annotations

from typing import Any

from app.figma import FigmaClient, FigmaError, FigmaRateLimitError, extract_file_id
from app.filtering import filter_figma_json


class ToolError(Exception):
    """Raised when a tool call fails."""


class ToolContext:
    """Request-scoped state shared between tool calls in an agent loop.

    Caches heavy Figma payloads so the LLM only passes lightweight
    ``file_id`` strings between tool calls instead of raw JSON.
    """

    def __init__(self, figma_client: FigmaClient) -> None:
        self.figma_client = figma_client
        self._figma_cache: dict[str, dict] = {}
        self._filtered_cache: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def fetch_figma_file(figma_url: str, figma_token: str, ctx: ToolContext) -> dict[str, Any]:
    """Fetch raw Figma file via the Figma API and cache it by file_id.

    Returns a lightweight summary so the LLM doesn't see the full JSON.
    Subsequent tools reference the file by ``file_id``.
    """
    file_id = extract_file_id(figma_url)

    if file_id not in ctx._figma_cache:
        ctx._figma_cache[file_id] = ctx.figma_client.get_file(file_id, figma_token)

    figma_json = ctx._figma_cache[file_id]
    document = figma_json.get("document") or {}
    frames = [c for c in document.get("children", []) if c.get("type") == "FRAME"]

    return {
        "file_id": file_id,
        "file_name": figma_json.get("name"),
        "screen_count": len(frames),
        "screen_names": [f.get("name") for f in frames],
    }


def filter_ui_elements(file_id: str, ctx: ToolContext) -> dict[str, Any]:
    """Filter and structure Figma elements from a previously fetched file.

    Extracts UI elements (buttons, inputs, headers, text) grouped by screen.
    Returns the full filtered structure that can be used for guide generation.
    """
    figma_json = ctx._figma_cache.get(file_id)
    if figma_json is None:
        return {
            "error": f"File '{file_id}' not fetched yet. Call fetch_figma_file first."
        }

    if file_id not in ctx._filtered_cache:
        ctx._filtered_cache[file_id] = filter_figma_json(figma_json)

    filtered = ctx._filtered_cache[file_id]

    # Return a summary so the LLM understands the structure without token overload.
    screens_summary = [
        {
            "name": s.get("name"),
            "element_count": len(s.get("elements", [])),
            "element_kinds": list({e.get("kind") for e in s.get("elements", [])}),
        }
        for s in filtered.get("screens", [])
    ]
    return {
        "file_name": filtered.get("file_name"),
        "screen_count": len(screens_summary),
        "screens": screens_summary,
    }


def get_screen_elements(
    file_id: str, screen_name: str, ctx: ToolContext
) -> dict[str, Any]:
    """Return all UI elements for a specific screen by name.

    Useful when generating detailed step-by-step instructions for one screen.
    Partial name matching is supported (case-insensitive).
    """
    filtered_json = ctx._filtered_cache.get(file_id)
    if filtered_json is None:
        return {
            "error": (
                f"File '{file_id}' not filtered yet. "
                "Call filter_ui_elements first."
            )
        }

    screens = filtered_json.get("screens", [])
    name_lower = screen_name.strip().lower()
    matched = [s for s in screens if name_lower in (s.get("name") or "").lower()]

    if not matched:
        return {
            "error": f"Screen '{screen_name}' not found.",
            "available_screens": [s.get("name") for s in screens],
        }

    return {"screens": matched}


# ---------------------------------------------------------------------------
# Tool definitions — OpenAI function-calling format
# (compatible with Fireworks AI and any OpenAI-compatible provider)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_figma_file",
            "description": (
                "Fetches a Figma file via the Figma API and caches it server-side. "
                "Returns file_id, file_name, screen_count, and screen_names. "
                "Must be called first, before any other tool. "
                "Use the returned file_id in subsequent tool calls."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "figma_url": {
                        "type": "string",
                        "description": (
                            "Figma file URL "
                            "(e.g. https://www.figma.com/file/AbCdEf1234/My-File) "
                            "or a raw file ID."
                        ),
                    },
                    "figma_token": {
                        "type": "string",
                        "description": "Figma personal access token for authentication.",
                    },
                },
                "required": ["figma_url", "figma_token"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "filter_ui_elements",
            "description": (
                "Processes a previously fetched Figma file and extracts structured "
                "UI elements (buttons, inputs, headers, text nodes) grouped by screen. "
                "Returns a summary of screens and element counts. "
                "Call fetch_figma_file first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "File ID returned by fetch_figma_file.",
                    },
                },
                "required": ["file_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_screen_elements",
            "description": (
                "Returns all UI elements for a specific screen by name, including "
                "element IDs, names, types, kinds, and text content. "
                "Use this when you need full detail about one screen to write "
                "step-by-step instructions for it. "
                "Supports partial, case-insensitive name matching. "
                "Call filter_ui_elements first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "File ID returned by fetch_figma_file.",
                    },
                    "screen_name": {
                        "type": "string",
                        "description": "Full or partial name of the screen to inspect.",
                    },
                },
                "required": ["file_id", "screen_name"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_TOOL_MAP = {
    "fetch_figma_file": fetch_figma_file,
    "filter_ui_elements": filter_ui_elements,
    "get_screen_elements": get_screen_elements,
}


def dispatch_tool(
    name: str,
    inputs: dict[str, Any],
    ctx: ToolContext,
) -> dict[str, Any]:
    """Execute a named tool, injecting the shared ToolContext.

    Wraps FigmaError exceptions as ToolError so the agent loop can
    handle them uniformly without knowing Figma internals.
    """
    fn = _TOOL_MAP.get(name)
    if fn is None:
        raise ToolError(f"Unknown tool: '{name}'")

    try:
        return fn(**inputs, ctx=ctx)
    except FigmaRateLimitError:
        raise  # propagate so main.py can return HTTP 429 with Retry-After
    except FigmaError as exc:
        raise ToolError(str(exc)) from exc
