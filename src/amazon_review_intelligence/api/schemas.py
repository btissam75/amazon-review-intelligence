from __future__ import annotations

from pydantic import BaseModel, Field


class SentimentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)


class SentimentResponse(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)


class Pagination(BaseModel):
    offset: int
    limit: int
    returned: int
