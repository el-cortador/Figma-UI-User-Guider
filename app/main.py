from __future__ import annotations

from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.agent import AgentError, MaxIterationsError, build_user_request, run_agent, run_vision_agent
from app.config import FIGMA_API_TOKEN
from app.file_handler import process_uploaded_file
from app.generation import build_prompt, parse_llm_output
from app.prompts import get_data_system_prompt, get_system_prompt, get_vision_system_prompt
from app.figma import (
    FigmaAuthError,
    FigmaBadUrlError,
    FigmaClient,
    FigmaNotFoundError,
    FigmaRequestError,
    FigmaRateLimitError,
    extract_file_id,
)
from app.filtering import filter_figma_json
from app.llm import LLMClient, LLMRequestError
from app.schemas import (
    FigmaFileRequest,
    FigmaFileResponse,
    FigmaFilteredResponse,
    GuideRequest,
    GuideResponse,
)
from app.tools import ToolContext

app = FastAPI(title="Figma UI User Guider Agent", version="0.2.0")

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    print(f"[request] {request.method} {request.url.path} -> {response.status_code}")
    return response


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


# ---------------------------------------------------------------------------
# Dependency providers
# ---------------------------------------------------------------------------


def get_figma_client() -> Generator[FigmaClient, None, None]:
    client = FigmaClient()
    try:
        yield client
    finally:
        client.close()


def get_llm_client() -> Generator[LLMClient, None, None]:
    client = LLMClient()
    try:
        yield client
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Figma utility endpoints (unchanged — useful for debugging)
# ---------------------------------------------------------------------------


@app.post("/figma/file", response_model=FigmaFileResponse)
def fetch_figma_file(
    payload: FigmaFileRequest,
    client: FigmaClient = Depends(get_figma_client),
) -> FigmaFileResponse:
    try:
        file_id = extract_file_id(payload.figma_url)
        data = client.get_file(file_id, payload.figma_token)
        return FigmaFileResponse(file_id=file_id, figma_json=data)
    except FigmaBadUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FigmaAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except FigmaNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FigmaRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except FigmaRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/figma/file/filtered", response_model=FigmaFilteredResponse)
def fetch_filtered_figma_file(
    payload: FigmaFileRequest,
    client: FigmaClient = Depends(get_figma_client),
) -> FigmaFilteredResponse:
    try:
        file_id = extract_file_id(payload.figma_url)
        data = client.get_file(file_id, payload.figma_token)
        filtered = filter_figma_json(data)
        return FigmaFilteredResponse(file_id=file_id, filtered_json=filtered)
    except FigmaBadUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FigmaAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except FigmaNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FigmaRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except FigmaRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Guide endpoints — backed by the agent loop
# ---------------------------------------------------------------------------


@app.post("/guide/generate", response_model=GuideResponse)
def generate_guide(
    payload: GuideRequest,
    figma: FigmaClient = Depends(get_figma_client),
    llm: LLMClient = Depends(get_llm_client),
) -> GuideResponse:
    return _run_guide_agent(payload, figma, llm)


# ---------------------------------------------------------------------------
# File upload endpoint
# ---------------------------------------------------------------------------


@app.post("/guide/upload", response_model=GuideResponse)
async def upload_guide(
    file: UploadFile = File(...),
    language: str = Form("ru"),
    detail_level: str = Form("brief"),
    llm: LLMClient = Depends(get_llm_client),
) -> GuideResponse:
    content = await file.read()
    filename = file.filename or "upload"

    try:
        processed = process_uploaded_file(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if processed["mode"] == "image":
        return await run_in_threadpool(
            _run_vision_guide,
            processed["base64"],
            processed["mime_type"],
            filename,
            language,
            detail_level,
            llm,
        )

    return await run_in_threadpool(
        _run_fig_json_guide,
        processed["data"],
        processed["file_id"],
        language,
        detail_level,
        llm,
    )


def _run_vision_guide(
    image_base64: str,
    mime_type: str,
    filename: str,
    language: str,
    detail_level: str,
    llm: LLMClient,
) -> GuideResponse:
    try:
        result = run_vision_agent(
            image_base64=image_base64,
            mime_type=mime_type,
            language=language,
            detail_level=detail_level,
            llm=llm,
            system_prompt=get_vision_system_prompt(detail_level),
        )
    except LLMRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except AgentError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return GuideResponse(file_id=filename, markdown=result.markdown)


def _run_fig_json_guide(
    figma_data: dict,
    file_id: str,
    language: str,
    detail_level: str,
    llm: LLMClient,
) -> GuideResponse:
    filtered = filter_figma_json(figma_data)
    prompt_text = build_prompt(filtered, language, detail_level)
    try:
        response = llm.chat(
            messages=[{"role": "user", "content": prompt_text}],
            tools=[],
            system=get_data_system_prompt(detail_level),
        )
    except LLMRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    text = response["text"]
    if not text.strip():
        raise HTTPException(status_code=502, detail="Модель вернула пустой ответ.")
    markdown = parse_llm_output(text)
    return GuideResponse(file_id=file_id, markdown=markdown)


# ---------------------------------------------------------------------------
# Shared agent runner
# ---------------------------------------------------------------------------


def _run_guide_agent(
    payload: GuideRequest,
    figma: FigmaClient,
    llm: LLMClient,
) -> GuideResponse:
    """Validate inputs, run the agent loop, and return a GuideResponse.

    Separating this from the endpoint handlers lets both /generate and /export
    share one implementation without code duplication.
    """
    token = payload.figma_token or FIGMA_API_TOKEN
    if not token:
        raise HTTPException(status_code=400, detail="Figma token is required")

    # Validate the URL before starting the agent so bad URLs get a 400,
    # not a 502 wrapped inside a ToolError.
    try:
        file_id = extract_file_id(payload.figma_url)
    except FigmaBadUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ctx = ToolContext(figma_client=figma)
    user_request = build_user_request(
        figma_url=payload.figma_url,
        figma_token=token,
        language=payload.language,
        detail_level=payload.detail_level,
    )

    try:
        result = run_agent(
                user_request=user_request,
                ctx=ctx,
                llm=llm,
                system_prompt=get_system_prompt(payload.detail_level),
            )
    except FigmaRateLimitError as exc:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after is not None else {}
        raise HTTPException(status_code=429, detail=str(exc), headers=headers) from exc
    except LLMRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except MaxIterationsError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except AgentError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return GuideResponse(
        file_id=file_id,
        markdown=result.markdown,
    )
