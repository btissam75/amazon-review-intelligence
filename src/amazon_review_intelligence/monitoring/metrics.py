from __future__ import annotations

import math
from typing import Iterable


def normalized_distribution(counts: dict[str, int], labels: Iterable[str]) -> dict[str, float]:
    """Return a stable probability distribution, including absent labels."""
    ordered = list(labels)
    total = sum(max(0, counts.get(label, 0)) for label in ordered)
    if not total:
        return {label: 0.0 for label in ordered}
    return {label: max(0, counts.get(label, 0)) / total for label in ordered}


def jensen_shannon_divergence(
    baseline: dict[str, float], current: dict[str, float], epsilon: float = 1e-12
) -> float:
    """Bounded, symmetric distribution drift metric in [0, 1]."""
    labels = sorted(set(baseline) | set(current))
    if not labels:
        return 0.0
    p = [max(float(baseline.get(label, 0.0)), 0.0) for label in labels]
    q = [max(float(current.get(label, 0.0)), 0.0) for label in labels]
    p_total, q_total = sum(p), sum(q)
    if p_total <= 0 or q_total <= 0:
        return 0.0
    p = [value / p_total for value in p]
    q = [value / q_total for value in q]
    midpoint = [(left + right) / 2 for left, right in zip(p, q)]

    def divergence(values: list[float]) -> float:
        return sum(
            value * math.log2(value / max(mean, epsilon))
            for value, mean in zip(values, midpoint)
            if value > epsilon
        )

    return max(0.0, min(1.0, (divergence(p) + divergence(q)) / 2))


def population_stability_index(
    baseline: list[float], current: list[float], epsilon: float = 1e-6
) -> float:
    """Calculate PSI for two aligned histograms."""
    if len(baseline) != len(current):
        raise ValueError("histograms must have the same number of bins")
    if not baseline:
        return 0.0
    baseline_total, current_total = sum(baseline), sum(current)
    if baseline_total <= 0 or current_total <= 0:
        return 0.0
    result = 0.0
    for baseline_value, current_value in zip(baseline, current):
        expected = max(baseline_value / baseline_total, epsilon)
        actual = max(current_value / current_total, epsilon)
        result += (actual - expected) * math.log(actual / expected)
    return max(0.0, result)


def monitoring_status(
    *,
    critical_error_rate: float,
    duplicate_rate: float,
    low_confidence_rate: float,
    sentiment_jsd: float,
    confidence_psi: float,
    confidence_delta: float,
) -> tuple[str, list[dict[str, str]]]:
    """Apply explicit operational thresholds and return actionable alerts."""
    alerts: list[dict[str, str]] = []

    def add(level: str, code: str, message: str) -> None:
        alerts.append({"level": level, "code": code, "message": message})

    if critical_error_rate >= 0.01:
        add("critical", "data_contract", "Plus de 1% des avis violent le contrat de données.")
    elif critical_error_rate >= 0.001:
        add("warning", "data_contract", "Des violations du contrat de données ont été détectées.")
    if duplicate_rate >= 0.10:
        add("critical", "duplicate_content", "Au moins 10% du contenu est dupliqué.")
    elif duplicate_rate >= 0.05:
        add("warning", "duplicate_content", "Le contenu dupliqué dépasse 5%.")
    if low_confidence_rate >= 0.40:
        add("critical", "low_confidence", "Au moins 40% des prédictions ont une faible confiance.")
    elif low_confidence_rate >= 0.25:
        add("warning", "low_confidence", "La faible confiance NLP dépasse 25%.")
    if sentiment_jsd >= 0.10 or confidence_psi >= 0.25:
        add("critical", "model_drift", "Une dérive NLP forte est détectée entre les fenêtres.")
    elif sentiment_jsd >= 0.03 or confidence_psi >= 0.10:
        add("warning", "model_drift", "Une dérive NLP modérée mérite une vérification.")
    if confidence_delta <= -0.10:
        add("critical", "confidence_drop", "La confiance moyenne a baissé d'au moins 10 points.")
    elif confidence_delta <= -0.05:
        add("warning", "confidence_drop", "La confiance moyenne a baissé d'au moins 5 points.")

    levels = {alert["level"] for alert in alerts}
    status = "critical" if "critical" in levels else "warning" if "warning" in levels else "healthy"
    if not alerts:
        add("info", "all_clear", "Aucun seuil de qualité ou de dérive n'est dépassé.")
    return status, alerts
