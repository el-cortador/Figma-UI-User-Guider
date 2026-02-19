from __future__ import annotations

from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
from app.generation import build_prompt, parse_llm_output
from app.llm import LLMClient, LLMRequestError
from app.config import FIGMA_API_TOKEN
from app.schemas import (
    FigmaFileRequest,
    FigmaFileResponse,
    FigmaFilteredResponse,
    GuideRequest,
    GuideExportResponse,
    GuideResponse,
)

app = FastAPI(title="Figma UI User Guider", version="0.1.0")

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
    except FigmaRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except FigmaRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


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
    except FigmaRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except FigmaRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


@app.post("/guide/generate", response_model=GuideResponse)
def generate_guide(
    payload: GuideRequest,
    client: FigmaClient = Depends(get_figma_client),
    llm: LLMClient = Depends(get_llm_client),
) -> GuideResponse:
    try:
        token = payload.figma_token or FIGMA_API_TOKEN
        if not token:
            raise HTTPException(status_code=400, detail="Figma token is required")
        file_id = extract_file_id(payload.figma_url)
        data = client.get_file(file_id, token)
        filtered = filter_figma_json(data)
        prompt = build_prompt(
            filtered,
            language=payload.language,
            detail_level=payload.detail_level,
            audience=payload.audience,
        )
        output = llm.generate(prompt)
        markdown, guide_json = parse_llm_output(output)
        return GuideResponse(file_id=file_id, markdown=markdown, guide_json=guide_json)
    except FigmaBadUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FigmaAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except FigmaNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FigmaRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except FigmaRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except LLMRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/guide/export", response_model=GuideExportResponse)
def export_guide(
    payload: GuideRequest,
    client: FigmaClient = Depends(get_figma_client),
    llm: LLMClient = Depends(get_llm_client),
) -> GuideExportResponse:
    try:
        token = payload.figma_token or FIGMA_API_TOKEN
        if not token:
            raise HTTPException(status_code=400, detail="Figma token is required")
        file_id = extract_file_id(payload.figma_url)
        data = client.get_file(file_id, token)
        filtered = filter_figma_json(data)
        prompt = build_prompt(
            filtered,
            language=payload.language,
            detail_level=payload.detail_level,
            audience=payload.audience,
        )
        output = llm.generate(prompt)
        markdown, guide_json = parse_llm_output(output)
        return GuideExportResponse(file_id=file_id, markdown=markdown, guide_json=guide_json)
    except FigmaBadUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FigmaAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except FigmaNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FigmaRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except FigmaRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except LLMRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
