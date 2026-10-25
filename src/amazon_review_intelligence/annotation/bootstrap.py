from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import typer
from pymongo import ASCENDING, MongoClient, UpdateOne

from .service import LABELS


app = typer.Typer(add_completion=False, help="Create a balanced human-annotation sample.")


@app.command()
def bootstrap(
    per_class: int = typer.Option(500, min=10, max=10_000),
    double_annotation_ratio: float = typer.Option(0.20, min=0.0, max=1.0),
) -> None:
    client = MongoClient(os.getenv("ARI_MONGODB_URI", "mongodb://mongodb:27017"))
    database = client[os.getenv("ARI_MONGODB_DATABASE", "amazon_reviews")]
    reviews = database["reviews_enriched"]
    tasks = database["annotation_tasks"]
    tasks.create_index("review_id", unique=True)
    tasks.create_index([("weak_label", ASCENDING), ("priority", ASCENDING)])
    tasks.create_index("annotations.annotator")
    created_by_label: dict[str, int] = {}

    for label in LABELS:
        existing = tasks.count_documents({"weak_label": label})
        needed = max(0, per_class - existing)
        existing_ids = tasks.distinct("review_id", {"weak_label": label})
        rows = list(
            reviews.aggregate(
                [
                    {
                        "$match": {
                            "sentiment_label": label,
                            "review_id": {"$nin": existing_ids},
                            "text": {"$type": "string", "$ne": ""},
                        }
                    },
                    {"$sample": {"size": needed}},
                    {
                        "$project": {
                            "_id": 0,
                            "review_id": 1,
                            "title": 1,
                            "text": 1,
                            "category": 1,
                            "rating": 1,
                            "review_timestamp": 1,
                            "sentiment_label": 1,
                            "sentiment_score": 1,
                        }
                    },
                ],
                allowDiskUse=True,
            )
        )
        double_target = round(per_class * double_annotation_ratio)
        existing_double = tasks.count_documents(
            {"weak_label": label, "required_annotations": 2}
        )
        doubles_to_assign = max(0, double_target - existing_double)
        operations = []
        for index, row in enumerate(rows):
            operations.append(
                UpdateOne(
                    {"review_id": row["review_id"]},
                    {
                        "$setOnInsert": {
                            "review_id": row["review_id"],
                            "title": row.get("title"),
                            "text": row["text"],
                            "category": row.get("category"),
                            "source_rating": row.get("rating"),
                            "review_timestamp": row.get("review_timestamp"),
                            "weak_label": row.get("sentiment_label"),
                            "model_confidence": row.get("sentiment_score"),
                            "required_annotations": 2 if index < doubles_to_assign else 1,
                            "priority": index,
                            "annotations": [],
                            "created_at": datetime.now(timezone.utc),
                        }
                    },
                    upsert=True,
                )
            )
        if operations:
            result = tasks.bulk_write(operations, ordered=False)
            created_by_label[label] = result.upserted_count
        else:
            created_by_label[label] = 0

    report = {
        "target_per_class": per_class,
        "double_annotation_ratio": double_annotation_ratio,
        "created_by_label": created_by_label,
        "total_tasks": tasks.count_documents({}),
        "double_annotation_tasks": tasks.count_documents({"required_annotations": 2}),
    }
    typer.echo(json.dumps(report, indent=2))
    client.close()


if __name__ == "__main__":
    app()
