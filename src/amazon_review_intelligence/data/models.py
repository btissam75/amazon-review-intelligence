from __future__ import annotations

import hashlib
import html
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


SPACE_RE = re.compile(r"\s+")
TAG_RE = re.compile(r"<[^>]+>")


def clean_text(value: Any) -> str:
    """Normalize text without destroying punctuation, emojis or negations."""
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = TAG_RE.sub(" ", text)
    text = unicodedata.normalize("NFKC", text)
    return SPACE_RE.sub(" ", text).strip()


def parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        # Reviews'23 timestamps are milliseconds; tolerate Unix seconds too.
        seconds = float(value) / 1000 if float(value) > 10_000_000_000 else float(value)
        parsed = datetime.fromtimestamp(seconds, tz=timezone.utc)
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("unsupported timestamp")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class ReviewEvent(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    event_id: str
    review_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    user_id: str | None = None
    rating: float = Field(ge=1, le=5)
    title: str = ""
    text: str = Field(min_length=2)
    verified_purchase: bool | None = None
    helpful_vote: int = Field(default=0, ge=0)
    category: str = Field(min_length=1)
    review_timestamp: datetime
    ingestion_timestamp: datetime
    source: str = "amazon_reviews_2023"
    schema_version: int = 1
    content_hash: str

    @field_validator("title", "text", mode="before")
    @classmethod
    def normalize_text(cls, value: Any) -> str:
        return clean_text(value)


def _first(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in record and record[key] is not None:
            return record[key]
    return default


def normalize_review(record: dict[str, Any], category: str) -> ReviewEvent:
    """Map Amazon Reviews'23 and common Amazon schemas to the canonical contract."""
    review_id = str(_first(record, "review_id", "reviewerID", default="")).strip()
    product_id = str(_first(record, "parent_asin", "asin", "product_id", default="")).strip()
    text = clean_text(_first(record, "text", "review_body", "reviewText", default=""))
    title = clean_text(_first(record, "title", "review_title", "summary", default=""))
    timestamp = parse_timestamp(
        _first(record, "timestamp", "sort_timestamp", "unixReviewTime", "review_date")
    )
    user_id_raw = _first(record, "user_id", "reviewerID", "customer_id")
    user_id = str(user_id_raw).strip() if user_id_raw is not None else None
    rating = float(_first(record, "rating", "overall", "star_rating"))
    helpful = int(_first(record, "helpful_vote", "helpful_votes", default=0) or 0)
    verified = _first(record, "verified_purchase", "verified", default=None)

    if not review_id:
        review_id = hashlib.sha256(
            f"{product_id}|{user_id}|{timestamp.isoformat()}|{text}".encode("utf-8")
        ).hexdigest()[:24]
    digest = hashlib.sha256(f"{product_id}|{text}".encode("utf-8")).hexdigest()

    return ReviewEvent(
        event_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"amazon-review:{review_id}")),
        review_id=review_id,
        product_id=product_id,
        user_id=user_id,
        rating=rating,
        title=title,
        text=text,
        verified_purchase=verified,
        helpful_vote=helpful,
        category=category,
        review_timestamp=timestamp,
        ingestion_timestamp=datetime.now(timezone.utc),
        content_hash=digest,
    )

