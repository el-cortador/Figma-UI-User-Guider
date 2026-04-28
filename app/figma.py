from __future__ import annotations

import logging
import re

import httpx

from app.config import FIGMA_API_BASE, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class FigmaError(Exception):
    """Base error for Figma integration."""


class FigmaAuthError(FigmaError):
    """Raised when Figma token is invalid or unauthorized."""


class FigmaNotFoundError(FigmaError):
    """Raised when Figma file is not found."""


class FigmaRequestError(FigmaError):
    """Raised for unexpected Figma API errors."""


class FigmaBadUrlError(FigmaError):
    """Raised when Figma file id cannot be extracted from URL."""


class FigmaRateLimitError(FigmaError):
    """Raised when Figma API rate limit is exceeded.

    Attributes:
        retry_after: seconds until the client may retry, or ``None`` if unknown.
    """

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def extract_file_id(value: str) -> str:
    if not value:
        raise FigmaBadUrlError("URL is empty")

    raw = value.strip()

    if re.fullmatch(r"[A-Za-z0-9]{10,}", raw):
        return raw

    match = re.search(
        r"https?://(?:www\.)?figma\.com/(?:file|proto|design)/([A-Za-z0-9]+)",
        raw,
    )
    if match:
        return match.group(1)

    raise FigmaBadUrlError("Cannot extract file id from URL")


def extract_node_id(url: str) -> str | None:
    """Extract and normalize node-id from a Figma selection URL.

    Figma URLs encode node IDs with hyphens (e.g. ``node-id=123-456``);
    the REST API expects colons (``123:456``).
    Returns ``None`` if no node-id is found.
    """
    match = re.search(r"[?&]node-id=([^&\s]+)", url)
    if not match:
        return None
    return match.group(1).replace("-", ":")


def normalize_nodes_to_file(nodes_data: dict) -> dict:
    """Convert a Figma nodes API response into a full-file-like structure.

    The nodes API returns ``{"nodes": {id: {"document": {...}}}, "name": "..."}``
    This wraps the node documents into a synthetic DOCUMENT root so the rest
    of the pipeline (filtering, tools) can treat it identically to a full file.
    """
    nodes = nodes_data.get("nodes") or {}
    children = [info["document"] for info in nodes.values() if info.get("document")]
    return {
        "name": nodes_data.get("name", ""),
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "name": "Document",
            "children": children,
        },
    }


class FigmaClient:
    def __init__(
        self,
        base_url: str = FIGMA_API_BASE,
        timeout: float = REQUEST_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def get_file(self, file_id: str, token: str) -> dict:
        response = self._client.get(
            f"/files/{file_id}",
            headers={"X-FIGMA-TOKEN": token},
        )
        self._log_response(response)
        self._raise_for_status(response)
        return response.json()

    def get_file_nodes(self, file_id: str, node_id: str, token: str) -> dict:
        """Fetch specific nodes from a Figma file via the nodes API.

        Preferred over ``get_file`` when a ``node-id`` is present in the URL,
        because it downloads only the selected section/frame instead of the
        entire (potentially huge) file.
        """
        response = self._client.get(
            f"/files/{file_id}/nodes",
            params={"ids": node_id},
            headers={"X-FIGMA-TOKEN": token},
        )
        self._log_response(response)
        self._raise_for_status(response)
        return response.json()

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_response(self, response: httpx.Response) -> None:
        rate_headers = {
            k: v
            for k, v in response.headers.items()
            if "ratelimit" in k.lower() or k.lower() == "retry-after"
        }
        logger.debug(
            "[figma] path=%s status=%s rate=%s",
            response.request.url.path,
            response.status_code,
            rate_headers,
        )

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code in (401, 403):
            raise FigmaAuthError("Invalid or unauthorized token")
        if response.status_code == 404:
            raise FigmaNotFoundError("File not found")
        if response.status_code == 429:
            raw = response.headers.get("retry-after", "")
            retry_after = int(raw) if raw.isdigit() else None
            msg = (
                f"Figma API rate limit exceeded. Try again in {retry_after} seconds."
                if retry_after is not None
                else "Figma API rate limit exceeded."
            )
            logger.warning("[figma] rate limit exceeded retry_after=%s", retry_after)
            raise FigmaRateLimitError(msg, retry_after=retry_after)
        if response.status_code == 400:
            try:
                detail = response.json().get("message", "")
            except Exception:
                detail = ""
            hint = (
                " Если файл очень большой — выделите нужный фрейм или секцию в Figma,"
                " ПКМ → Copy/Paste as → Copy link to selection, и вставьте эту ссылку."
            )
            raise FigmaRequestError(f"Figma API вернул 400.{hint} ({detail})" if detail else f"Figma API вернул 400.{hint}")
        if response.status_code >= 400:
            raise FigmaRequestError(f"Figma API error: {response.status_code}")
