import pytest

from amazon_review_intelligence.monitoring.metrics import (
    jensen_shannon_divergence,
    monitoring_status,
    normalized_distribution,
    population_stability_index,
)


def test_drift_metrics_are_zero_for_identical_distributions():
    distribution = normalized_distribution(
        {"negative": 20, "neutral": 30, "positive": 50},
        ["negative", "neutral", "positive"],
    )
    assert jensen_shannon_divergence(distribution, distribution) == pytest.approx(0.0)
    assert population_stability_index([20, 30, 50], [20, 30, 50]) == pytest.approx(0.0)


def test_drift_metrics_detect_changed_distributions():
    baseline = {"negative": 0.1, "neutral": 0.2, "positive": 0.7}
    current = {"negative": 0.7, "neutral": 0.2, "positive": 0.1}
    assert jensen_shannon_divergence(baseline, current) > 0.2
    assert population_stability_index([10, 20, 70], [70, 20, 10]) > 1.0


def test_monitoring_status_prioritizes_critical_alerts():
    status, alerts = monitoring_status(
        critical_error_rate=0.02,
        duplicate_rate=0.01,
        low_confidence_rate=0.10,
        sentiment_jsd=0.01,
        confidence_psi=0.02,
        confidence_delta=0.0,
    )
    assert status == "critical"
    assert any(alert["code"] == "data_contract" for alert in alerts)


def test_monitoring_status_is_healthy_below_thresholds():
    status, alerts = monitoring_status(
        critical_error_rate=0.0,
        duplicate_rate=0.01,
        low_confidence_rate=0.10,
        sentiment_jsd=0.01,
        confidence_psi=0.02,
        confidence_delta=0.0,
    )
    assert status == "healthy"
    assert alerts[0]["code"] == "all_clear"
