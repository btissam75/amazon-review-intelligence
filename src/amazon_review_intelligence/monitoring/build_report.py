from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pymongo import DESCENDING, MongoClient

from amazon_review_intelligence.monitoring.metrics import (
    jensen_shannon_divergence,
    monitoring_status,
    normalized_distribution,
    population_stability_index,
)

LABELS = ("negative", "neutral", "positive")
CONFIDENCE_BOUNDARIES = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.000001]


def _quality(collection) -> dict:
    rows = list(
        collection.aggregate(
            [
                {
                    "$group": {
                        "_id": None,
                        "total": {"$sum": 1},
                        "missing_review_id": {"$sum": {"$cond": [{"$eq": [{"$ifNull": ["$review_id", ""]}, ""]}, 1, 0]}},
                        "missing_product_id": {"$sum": {"$cond": [{"$eq": [{"$ifNull": ["$product_id", ""]}, ""]}, 1, 0]}},
                        "empty_text": {"$sum": {"$cond": [{"$lt": [{"$strLenCP": {"$ifNull": ["$text", ""]}}, 2]}, 1, 0]}},
                        "invalid_rating": {"$sum": {"$cond": [{"$or": [{"$lt": [{"$ifNull": ["$rating", 0]}, 1]}, {"$gt": [{"$ifNull": ["$rating", 0]}, 5]}]}, 1, 0]}},
                        "invalid_sentiment": {"$sum": {"$cond": [{"$not": [{"$in": ["$sentiment_label", list(LABELS)]}]}, 1, 0]}},
                        "missing_confidence": {"$sum": {"$cond": [{"$eq": [{"$ifNull": ["$sentiment_score", None]}, None]}, 1, 0]}},
                        "low_confidence": {"$sum": {"$cond": [{"$lt": [{"$ifNull": ["$sentiment_score", 0]}, 0.6]}, 1, 0]}},
                        "average_confidence": {"$avg": "$sentiment_score"},
                        "aspect_enriched": {"$sum": {"$cond": [{"$gt": [{"$size": {"$ifNull": ["$aspect_sentiments", []]}}, 0]}, 1, 0]}},
                    }
                }
            ],
            allowDiskUse=True,
        )
    )
    result = rows[0] if rows else {"total": 0}
    result.pop("_id", None)
    total = result.get("total", 0) or 1
    critical_errors = sum(
        result.get(field, 0)
        for field in (
            "missing_review_id",
            "missing_product_id",
            "empty_text",
            "invalid_rating",
            "invalid_sentiment",
            "missing_confidence",
        )
    )
    result.update(
        {
            "critical_errors": critical_errors,
            "critical_error_rate": critical_errors / total,
            "low_confidence_rate": result.get("low_confidence", 0) / total,
            "aspect_coverage": result.get("aspect_enriched", 0) / total,
            "average_confidence": result.get("average_confidence") or 0.0,
        }
    )
    return result


def _duplicates(collection) -> int:
    rows = list(
        collection.aggregate(
            [
                {"$match": {"content_hash": {"$type": "string", "$ne": ""}}},
                {"$group": {"_id": "$content_hash", "count": {"$sum": 1}}},
                {"$match": {"count": {"$gt": 1}}},
                {"$group": {"_id": None, "duplicates": {"$sum": {"$subtract": ["$count", 1]}}}},
            ],
            allowDiskUse=True,
        )
    )
    return rows[0]["duplicates"] if rows else 0


def _window_metrics(collection, start: datetime, end: datetime) -> dict:
    match = {"review_timestamp": {"$gte": start, "$lt": end}}
    summary = list(
        collection.aggregate(
            [
                {"$match": match},
                {
                    "$group": {
                        "_id": "$sentiment_label",
                        "count": {"$sum": 1},
                        "average_confidence": {"$avg": "$sentiment_score"},
                        "low_confidence": {"$sum": {"$cond": [{"$lt": ["$sentiment_score", 0.6]}, 1, 0]}},
                    }
                },
            ],
            allowDiskUse=True,
        )
    )
    counts = {row["_id"]: row["count"] for row in summary if row.get("_id") in LABELS}
    total = sum(counts.values())
    weighted_confidence = sum(
        row.get("average_confidence", 0.0) * row["count"]
        for row in summary
        if row.get("_id") in LABELS
    )
    low_confidence = sum(row.get("low_confidence", 0) for row in summary)
    histogram_rows = list(
        collection.aggregate(
            [
                {"$match": match},
                {
                    "$bucket": {
                        "groupBy": "$sentiment_score",
                        "boundaries": CONFIDENCE_BOUNDARIES,
                        "default": "other",
                        "output": {"count": {"$sum": 1}},
                    }
                },
            ],
            allowDiskUse=True,
        )
    )
    histogram_by_key = {row["_id"]: row["count"] for row in histogram_rows}
    histogram = [histogram_by_key.get(boundary, 0) for boundary in CONFIDENCE_BOUNDARIES[:-1]]
    return {
        "start": start,
        "end": end,
        "total": total,
        "sentiment_counts": counts,
        "sentiment_distribution": normalized_distribution(counts, LABELS),
        "average_confidence": weighted_confidence / total if total else 0.0,
        "low_confidence_rate": low_confidence / total if total else 0.0,
        "confidence_histogram": histogram,
    }


def build_report(database, window_days: int = 90) -> dict:
    collection = database["reviews_enriched"]
    quality = _quality(collection)
    duplicates = _duplicates(collection)
    quality["duplicate_content"] = duplicates
    quality["duplicate_rate"] = duplicates / (quality.get("total", 0) or 1)

    latest = collection.find_one(
        {"review_timestamp": {"$type": "date"}},
        {"_id": 0, "review_timestamp": 1},
        sort=[("review_timestamp", DESCENDING)],
    )
    if not latest:
        raise RuntimeError("No valid review_timestamp found")
    latest_timestamp = latest["review_timestamp"]
    if latest_timestamp.tzinfo is None:
        latest_timestamp = latest_timestamp.replace(tzinfo=timezone.utc)
    current_end = latest_timestamp + timedelta(seconds=1)
    current_start = current_end - timedelta(days=window_days)
    baseline_start = current_start - timedelta(days=window_days)
    baseline = _window_metrics(collection, baseline_start, current_start)
    current = _window_metrics(collection, current_start, current_end)
    sentiment_jsd = jensen_shannon_divergence(
        baseline["sentiment_distribution"], current["sentiment_distribution"]
    )
    confidence_psi = population_stability_index(
        baseline["confidence_histogram"], current["confidence_histogram"]
    )
    confidence_delta = current["average_confidence"] - baseline["average_confidence"]
    status, alerts = monitoring_status(
        critical_error_rate=quality["critical_error_rate"],
        duplicate_rate=quality["duplicate_rate"],
        low_confidence_rate=quality["low_confidence_rate"],
        sentiment_jsd=sentiment_jsd,
        confidence_psi=confidence_psi,
        confidence_delta=confidence_delta,
    )
    now = datetime.now(timezone.utc)
    quality_score = max(
        0.0,
        100
        * (1 - min(1.0, quality["critical_error_rate"] + quality["duplicate_rate"])),
    )
    return {
        "version": "data-quality-drift-v1",
        "generated_at": now,
        "status": status,
        "quality_score": round(quality_score, 2),
        "data_quality": quality,
        "drift": {
            "window_days": window_days,
            "baseline": baseline,
            "current": current,
            "sentiment_jsd": sentiment_jsd,
            "confidence_psi": confidence_psi,
            "confidence_delta": confidence_delta,
        },
        "thresholds": {
            "sentiment_jsd_warning": 0.03,
            "sentiment_jsd_critical": 0.10,
            "confidence_psi_warning": 0.10,
            "confidence_psi_critical": 0.25,
            "low_confidence_warning": 0.25,
            "low_confidence_critical": 0.40,
        },
        "alerts": alerts,
    }


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Cannot serialize {type(value)!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a quality and NLP-drift snapshot")
    parser.add_argument("--window-days", type=int, default=90)
    parser.add_argument(
        "--output",
        default=os.getenv("ARI_MONITORING_REPORT", "data/reports/data_quality_drift.json"),
    )
    args = parser.parse_args()
    if args.window_days < 7:
        parser.error("--window-days must be at least 7")

    client = MongoClient(os.getenv("ARI_MONGODB_URI", "mongodb://mongodb:27017"))
    database = client[os.getenv("ARI_MONGODB_DATABASE", "amazon_reviews")]
    report = build_report(database, args.window_days)
    database["monitoring_snapshots"].insert_one(report.copy())
    database["monitoring_snapshots"].create_index([("generated_at", DESCENDING)])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, default=_json_default), encoding="utf-8")
    client.close()
    print(
        f"monitoring_ready status={report['status']} quality_score={report['quality_score']} "
        f"sentiment_jsd={report['drift']['sentiment_jsd']:.6f} "
        f"confidence_psi={report['drift']['confidence_psi']:.6f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
