import pytest

from amazon_review_intelligence.recommendation.scoring import (
    hybrid_score,
    product_quality_score,
    recommendation_reasons,
)


def test_product_quality_rewards_positive_verified_products():
    strong = product_quality_score(0.90, 0.05, 4.8, 0.90, 0.90)
    weak = product_quality_score(0.20, 0.65, 2.0, 0.20, 0.85)
    assert strong > weak
    assert 0.0 <= weak <= strong <= 1.0


def test_hybrid_score_is_bounded():
    assert hybrid_score(99.0, 99.0, 99.0) == pytest.approx(1.0)
    assert hybrid_score(-99.0, -99.0, -99.0) == pytest.approx(0.0)


def test_recommendation_reasons_are_explainable():
    reasons = recommendation_reasons(0.85, 4.6, 0.80)
    assert "sentiment client très positif" in reasons
    assert "excellente note moyenne" in reasons
    assert "majorité d'achats vérifiés" in reasons


def test_recommendation_reasons_have_fallback():
    assert recommendation_reasons(0.40, 3.5, 0.40) == [
        "compatible avec vos préférences"
    ]

