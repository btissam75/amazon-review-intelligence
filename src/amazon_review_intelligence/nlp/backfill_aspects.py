from __future__ import annotations

import os
from datetime import datetime, timezone

import typer

from .aspects import ASPECT_MODEL_VERSION, analyze_aspects


app = typer.Typer(add_completion=False, help="Backfill aspect sentiment for MongoDB reviews.")


@app.command()
def backfill(
    batch_size: int = typer.Option(500, min=10, max=5_000),
    limit: int = typer.Option(0, min=0),
) -> None:
    from pymongo import MongoClient, UpdateOne

    client = MongoClient(
        os.getenv("ARI_MONGODB_URI", "mongodb://mongodb:27017"),
        socketTimeoutMS=120_000,
    )
    database = client[os.getenv("ARI_MONGODB_DATABASE", "amazon_reviews")]
    reviews = database["reviews_enriched"]
    jobs = database["pipeline_jobs"]
    query = {"aspect_model_version": {"$ne": ASPECT_MODEL_VERSION}}
    total = reviews.count_documents(query)
    target = min(total, limit) if limit else total
    jobs.update_one(
        {"name": "aspect-sentiment-backfill"},
        {
            "$set": {
                "name": "aspect-sentiment-backfill",
                "status": "running",
                "model_version": ASPECT_MODEL_VERSION,
                "target": target,
                "processed": 0,
                "started_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )
    cursor = reviews.find(
        query,
        {"_id": 0, "review_id": 1, "title": 1, "text": 1},
        batch_size=batch_size,
    )
    if limit:
        cursor = cursor.limit(limit)
    operations = []
    processed = 0
    reviews_with_aspects = 0
    for document in cursor:
        aspects = analyze_aspects(document.get("text", ""), document.get("title"))
        reviews_with_aspects += bool(aspects)
        operations.append(
            UpdateOne(
                {"review_id": document["review_id"]},
                {
                    "$set": {
                        "aspect_sentiments": aspects,
                        "aspect_model_version": ASPECT_MODEL_VERSION,
                        "aspects_processed_at": datetime.now(timezone.utc),
                    }
                },
            )
        )
        if len(operations) >= batch_size:
            reviews.bulk_write(operations, ordered=False)
            processed += len(operations)
            operations.clear()
            jobs.update_one(
                {"name": "aspect-sentiment-backfill"},
                {
                    "$set": {
                        "processed": processed,
                        "reviews_with_aspects": reviews_with_aspects,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            typer.echo(f"aspects_processed={processed}/{target} matched={reviews_with_aspects}")
    if operations:
        reviews.bulk_write(operations, ordered=False)
        processed += len(operations)
    reviews.create_index("aspect_model_version")
    reviews.create_index("aspect_sentiments.aspect")
    reviews.create_index("aspect_sentiments.label")
    jobs.update_one(
        {"name": "aspect-sentiment-backfill"},
        {
            "$set": {
                "status": "ready" if processed == target else "incomplete",
                "processed": processed,
                "reviews_with_aspects": reviews_with_aspects,
                "completed_at": datetime.now(timezone.utc),
            }
        },
    )
    client.close()
    typer.echo(
        f"aspect_backfill_ready processed={processed} matched={reviews_with_aspects} "
        f"version={ASPECT_MODEL_VERSION}"
    )


if __name__ == "__main__":
    app()
