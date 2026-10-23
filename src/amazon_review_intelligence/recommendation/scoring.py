from __future__ import annotations

ALS_WEIGHT = 0.65
QUALITY_WEIGHT = 0.25
POPULARITY_WEIGHT = 0.10


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def product_quality_score(
    positive_ratio: float,
    negative_ratio: float,
    average_rating: float,
    verified_ratio: float,
    average_confidence: float,
) -> float:
    """Combine sentiment polarity, confidence, rating and purchase verification."""
    sentiment_balance = clamp((1.0 + positive_ratio - negative_ratio) / 2.0)
    confidence = clamp(average_confidence)
    confidence_adjusted_sentiment = 0.5 + (sentiment_balance - 0.5) * confidence
    rating_score = clamp((average_rating - 1.0) / 4.0)
    return clamp(
        0.65 * confidence_adjusted_sentiment
        + 0.25 * rating_score
        + 0.10 * clamp(verified_ratio)
    )


def hybrid_score(als_prediction: float, quality_score: float, popularity_score: float) -> float:
    """Normalize a predicted rating and combine it with NLP-backed product quality."""
    als_score = clamp((als_prediction - 1.0) / 4.0)
    return clamp(
        ALS_WEIGHT * als_score
        + QUALITY_WEIGHT * clamp(quality_score)
        + POPULARITY_WEIGHT * clamp(popularity_score)
    )


def recommendation_reasons(
    positive_ratio: float,
    average_rating: float,
    verified_ratio: float,
) -> list[str]:
    reasons: list[str] = []
    if positive_ratio >= 0.70:
        reasons.append("sentiment client très positif")
    if average_rating >= 4.2:
        reasons.append("excellente note moyenne")
    if verified_ratio >= 0.70:
        reasons.append("majorité d'achats vérifiés")
    return reasons or ["compatible avec vos préférences"]

