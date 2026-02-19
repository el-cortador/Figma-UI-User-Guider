from __future__ import annotations

from pydantic import BaseModel, Field


class FigmaFileRequest(BaseModel):
    figma_url: str = Field(..., examples=["https://www.figma.com/file/AbCdEf1234/My-File"])
    figma_token: str = Field(..., min_length=1)


class FigmaFileResponse(BaseModel):
    file_id: str
    figma_json: dict


class FigmaFilteredResponse(BaseModel):
    file_id: str
    filtered_json: dict


class GuideRequest(BaseModel):
    figma_url: str
    figma_token: str
    language: str = "ru"
    detail_level: str = "brief"
    audience: str = "user"


class GuideResponse(BaseModel):
    file_id: str
    markdown: str
    guide_json: dict
