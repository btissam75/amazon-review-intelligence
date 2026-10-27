from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SentimentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)


class SentimentResponse(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)


class AspectSentimentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    title: str | None = Field(default=None, max_length=500)


class AnnotationSubmission(BaseModel):
    annotator: str = Field(min_length=2, max_length=80)
    label: Literal["negative", "neutral", "positive", "uncertain"]
    notes: str | None = Field(default=None, max_length=500)


class AdjudicationSubmission(BaseModel):
    adjudicator: str = Field(min_length=2, max_length=80)
    label: Literal["negative", "neutral", "positive"]
    notes: str | None = Field(default=None, max_length=500)


class Pagination(BaseModel):
    offset: int
    limit: int
    returned: int
