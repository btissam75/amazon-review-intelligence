from datetime import timezone

import pytest
from pydantic import ValidationError

from amazon_review_intelligence.data.models import clean_text, normalize_review


def test_clean_text_preserves_negation_and_emoji():
    assert clean_text("<b>Not</b>   good 😞") == "Not good 😞"


def test_normalize_reviews_2023_record():
    event = normalize_review(
        {
            "rating": 2.0,
            "title": "Battery",
            "text": "Good screen, but weak battery.",
            "parent_asin": "B001",
            "user_id": "USER1",
            "sort_timestamp": 1_690_000_000_000,
            "helpful_votes": 3,
            "verified_purchase": True,
        },
        "Electronics",
    )
    assert event.product_id == "B001"
    assert event.rating == 2
    assert event.helpful_vote == 3
    assert event.review_timestamp.tzinfo == timezone.utc
    assert len(event.content_hash) == 64
    assert event.review_id


def test_rejects_invalid_rating():
    with pytest.raises(ValidationError):
        normalize_review(
            {
                "rating": 8,
                "text": "Impossible rating",
                "parent_asin": "B001",
                "timestamp": 1_690_000_000_000,
            },
            "Electronics",
        )

