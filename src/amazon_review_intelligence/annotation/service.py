from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any


LABELS = ("negative", "neutral", "positive")


def consensus_label(document: dict[str, Any]) -> str | None:
    adjudicated = document.get("adjudicated_label")
    if adjudicated in LABELS:
        return str(adjudicated)
    annotations = document.get("annotations") or []
    required = int(document.get("required_annotations", 1))
    labels = [row.get("label") for row in annotations if row.get("label") in LABELS]
    if len(labels) < required or len(set(labels)) != 1:
        return None
    return str(labels[0])


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    observed = sum(left == right for left, right in pairs) / len(pairs)
    left_counts = Counter(left for left, _ in pairs)
    right_counts = Counter(right for _, right in pairs)
    expected = sum(
        (left_counts[label] / len(pairs)) * (right_counts[label] / len(pairs))
        for label in LABELS
    )
    if expected == 1:
        return 1.0 if observed == 1 else 0.0
    return (observed - expected) / (1 - expected)


def annotation_progress(collection, annotator: str | None = None) -> dict[str, Any]:
    documents = list(
        collection.find(
            {},
            {
                "_id": 0,
                "required_annotations": 1,
                "annotations": 1,
                "adjudicated_label": 1,
            },
        )
    )
    completed = sum(consensus_label(document) is not None for document in documents)
    conflicts = sum(
        len({row.get("label") for row in document.get("annotations", [])}) > 1
        and not document.get("adjudicated_label")
        for document in documents
    )
    double_pairs = []
    for document in documents:
        annotations = document.get("annotations") or []
        if len(annotations) >= 2:
            double_pairs.append((annotations[0]["label"], annotations[1]["label"]))
    reviewed = 0
    if annotator:
        reviewed = sum(
            any(row.get("annotator") == annotator for row in document.get("annotations", []))
            for document in documents
        )
    total = len(documents)
    kappa = cohen_kappa(double_pairs)
    return {
        "total": total,
        "completed": completed,
        "pending": total - completed,
        "completion_percentage": round(100 * completed / total, 2) if total else 0.0,
        "conflicts": conflicts,
        "double_annotated": len(double_pairs),
        "cohen_kappa": round(kappa, 4) if kappa is not None else None,
        "reviewed_by_annotator": reviewed,
    }


def next_annotation_task(collection, annotator: str) -> dict[str, Any] | None:
    document = collection.find_one(
        {
            "annotations": {"$not": {"$elemMatch": {"annotator": annotator}}},
            "$expr": {
                "$lt": [
                    {"$size": {"$ifNull": ["$annotations", []]}},
                    "$required_annotations",
                ]
            },
        },
        {
            "_id": 0,
            "review_id": 1,
            "title": 1,
            "text": 1,
            "category": 1,
            "required_annotations": 1,
        },
        sort=[("required_annotations", -1), ("priority", 1), ("review_id", 1)],
    )
    return document


def next_conflict_task(collection) -> dict[str, Any] | None:
    return collection.find_one(
        {
            "adjudicated_label": {"$exists": False},
            "annotations.1": {"$exists": True},
            "$expr": {"$gt": [{"$size": {"$setUnion": ["$annotations.label", []]}}, 1]},
        },
        {
            "_id": 0,
            "review_id": 1,
            "title": 1,
            "text": 1,
            "category": 1,
            "required_annotations": 1,
            "annotations.label": 1,
            "annotations.notes": 1,
        },
        sort=[("review_id", 1)],
    )


def save_annotation(
    collection,
    review_id: str,
    annotator: str,
    label: str,
    notes: str | None = None,
) -> dict[str, Any] | None:
    annotation = {
        "annotator": annotator,
        "label": label,
        "notes": notes or None,
        "annotated_at": datetime.now(timezone.utc),
    }
    result = collection.update_one(
        {"review_id": review_id},
        [
            {
                "$set": {
                    "annotations": {
                        "$concatArrays": [
                            {
                                "$filter": {
                                    "input": {"$ifNull": ["$annotations", []]},
                                    "as": "annotation",
                                    "cond": {"$ne": ["$$annotation.annotator", annotator]},
                                }
                            },
                            [annotation],
                        ]
                    },
                    "updated_at": "$$NOW",
                }
            }
        ],
    )
    if not result.matched_count:
        return None
    return collection.find_one({"review_id": review_id}, {"_id": 0})


def save_adjudication(
    collection,
    review_id: str,
    adjudicator: str,
    label: str,
    notes: str | None = None,
) -> dict[str, Any] | None:
    result = collection.update_one(
        {"review_id": review_id},
        {
            "$set": {
                "adjudicated_label": label,
                "adjudication": {
                    "adjudicator": adjudicator,
                    "notes": notes or None,
                    "adjudicated_at": datetime.now(timezone.utc),
                },
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    if not result.matched_count:
        return None
    return collection.find_one({"review_id": review_id}, {"_id": 0})
