from __future__ import annotations

from typing import Generator

from fastapi import Depends, FastAPI, HTTPException, Request

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
from app.schemas import (
    FigmaFileRequest,
    FigmaFileResponse,
    FigmaFilteredResponse,
    GuideRequest,
    GuideExportResponse,
    GuideResponse,
)

app = FastAPI(title="Figma UI User Guider", version="0.1.0")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    print(f"[request] {request.method} {request.url.path} -> {response.status_code}")
    return response


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
        file_id = extract_file_id(payload.figma_url)
        data = client.get_file(file_id, payload.figma_token)
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
        file_id = extract_file_id(payload.figma_url)
        data = client.get_file(file_id, payload.figma_token)
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
