from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def load_sentiment_model():
    """Load one model instance per long-lived Python worker."""
    import joblib

    path = os.getenv("ARI_MODEL_PATH", "/opt/app/models/sentiment_baseline.joblib")
    return joblib.load(path)


def predict_sentiment(text: str) -> tuple[str, float]:
    model = load_sentiment_model()
    probabilities = model.predict_proba([text or ""])[0]
    best = int(probabilities.argmax())
    return str(model.classes_[best]), float(probabilities[best])
