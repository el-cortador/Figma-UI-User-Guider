from __future__ import annotations

from typing import Generator

from fastapi import Depends, FastAPI, HTTPException

from app.figma import (
    FigmaAuthError,
    FigmaBadUrlError,
    FigmaClient,
    FigmaNotFoundError,
    FigmaRequestError,
    extract_file_id,
)
from app.filtering import filter_figma_json
from app.schemas import FigmaFileRequest, FigmaFileResponse, FigmaFilteredResponse

app = FastAPI(title="Figma UI User Guider", version="0.1.0")


def get_figma_client() -> Generator[FigmaClient, None, None]:
    client = FigmaClient()
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
