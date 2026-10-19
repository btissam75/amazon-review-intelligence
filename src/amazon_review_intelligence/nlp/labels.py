from __future__ import annotations


LABELS = ("negative", "neutral", "positive")


def rating_to_sentiment(rating: float) -> str:
    """Create a weak sentiment label from a 1–5 star rating."""
    if not 1 <= rating <= 5:
        raise ValueError("rating must be between 1 and 5")
    if rating <= 2:
        return "negative"
    if rating == 3:
        return "neutral"
    return "positive"

