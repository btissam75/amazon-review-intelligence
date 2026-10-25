import pytest

from amazon_review_intelligence.recommendation.metrics import metrics_for_rank


def test_ranking_metrics_reward_first_position():
    metrics = metrics_for_rank(1, 10)
    assert metrics["precision_at_k"] == pytest.approx(0.1)
    assert metrics["recall_at_k"] == pytest.approx(1.0)
    assert metrics["hit_rate_at_k"] == pytest.approx(1.0)
    assert metrics["ndcg_at_k"] == pytest.approx(1.0)
    assert metrics["mrr_at_k"] == pytest.approx(1.0)


def test_ranking_metrics_penalize_late_and_missing_hits():
    late = metrics_for_rank(10, 10)
    missing = metrics_for_rank(None, 10)
    assert 0 < late["ndcg_at_k"] < 1
    assert late["mrr_at_k"] == pytest.approx(0.1)
    assert all(value == 0.0 for value in missing.values())


def test_ranking_metrics_reject_invalid_k():
    with pytest.raises(ValueError):
        metrics_for_rank(1, 0)
