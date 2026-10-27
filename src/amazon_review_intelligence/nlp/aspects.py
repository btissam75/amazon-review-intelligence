from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from .inference import predict_sentiment


ASPECT_MODEL_VERSION = "lexicon-sentence-tfidf-v1"
ASPECT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "quality": (
        "quality",
        "material",
        "construction",
        "performance",
        "works",
        "worked",
        "fonctionne",
        "qualité",
        "matière",
    ),
    "price": (
        "price",
        "cost",
        "expensive",
        "cheap",
        "value for money",
        "worth",
        "prix",
        "cher",
        "chère",
        "abordable",
    ),
    "delivery": (
        "delivery",
        "shipping",
        "arrived",
        "arrival",
        "courier",
        "livraison",
        "livré",
        "livrée",
        "retard",
    ),
    "packaging": (
        "packaging",
        "package",
        "box",
        "wrapped",
        "seal",
        "emballage",
        "boîte",
        "colis",
    ),
    "durability": (
        "durable",
        "durability",
        "lasted",
        "broken",
        "broke",
        "sturdy",
        "fragile",
        "long lasting",
        "durabilité",
        "cassé",
        "cassée",
        "solide",
    ),
    "usability": (
        "easy to use",
        "difficult to use",
        "instructions",
        "setup",
        "install",
        "comfortable",
        "ergonomic",
        "facile à utiliser",
        "difficile à utiliser",
        "mode d'emploi",
        "installation",
        "confortable",
    ),
}


def split_sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+", text or "")
        if sentence.strip()
    ]


def detected_aspects(sentence: str) -> list[str]:
    lowered = sentence.casefold()
    matches = []
    for aspect, keywords in ASPECT_KEYWORDS.items():
        if any(re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", lowered) for keyword in keywords):
            matches.append(aspect)
    return matches


def analyze_aspects(
    text: str,
    title: str | None = None,
    predictor: Callable[[str], tuple[str, float]] = predict_sentiment,
) -> list[dict[str, Any]]:
    """Detect product aspects and aggregate sentence-level sentiment evidence."""
    evidence: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
    for sentence in split_sentences(f"{title or ''}. {text or ''}".strip(". ")):
        aspects = detected_aspects(sentence)
        if not aspects:
            continue
        label, confidence = predictor(sentence)
        for aspect in aspects:
            evidence[aspect].append((sentence, label, float(confidence)))

    results = []
    for aspect in ASPECT_KEYWORDS:
        mentions = evidence.get(aspect, [])
        if not mentions:
            continue
        weights = {label: 0.0 for label in ("negative", "neutral", "positive")}
        for _, label, confidence in mentions:
            if label in weights:
                weights[label] += confidence
        total_weight = sum(weights.values()) or 1.0
        positive_negative_gap = abs(weights["positive"] - weights["negative"]) / total_weight
        if weights["positive"] and weights["negative"] and positive_negative_gap < 0.20:
            label = "neutral"
            score = 1.0 - positive_negative_gap
        else:
            label = max(weights, key=weights.get)
            score = weights[label] / total_weight
        excerpts = []
        for sentence, _, _ in mentions:
            excerpt = " ".join(sentence.split())[:220]
            if excerpt not in excerpts:
                excerpts.append(excerpt)
        results.append(
            {
                "aspect": aspect,
                "label": label,
                "score": round(max(0.0, min(1.0, score)), 6),
                "mentions": len(mentions),
                "evidence": excerpts[:3],
            }
        )
    return results
