from __future__ import annotations

import math


def metrics_for_rank(rank: int | None, k: int) -> dict[str, float]:
    """Return single-relevant-item ranking metrics for one evaluated user."""
    if k < 1:
        raise ValueError("k must be greater than zero")
    hit = rank is not None and 1 <= rank <= k
    return {
        "precision_at_k": 1.0 / k if hit else 0.0,
        "recall_at_k": 1.0 if hit else 0.0,
        "hit_rate_at_k": 1.0 if hit else 0.0,
        "ndcg_at_k": 1.0 / math.log2(rank + 1) if hit and rank is not None else 0.0,
        "mrr_at_k": 1.0 / rank if hit and rank is not None else 0.0,
    }

