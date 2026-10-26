from __future__ import annotations

import json
import os
from pathlib import Path

import typer
from pymongo import MongoClient

from .service import annotation_progress, consensus_label


app = typer.Typer(add_completion=False, help="Export the manually validated sentiment corpus.")


@app.command()
def export(
    output: Path = typer.Option(Path("data/annotations/reviewed_reviews.jsonl")),
    report: Path = typer.Option(Path("data/reports/annotation_report.json")),
) -> None:
    client = MongoClient(os.getenv("ARI_MONGODB_URI", "mongodb://mongodb:27017"))
    tasks = client[os.getenv("ARI_MONGODB_DATABASE", "amazon_reviews")]["annotation_tasks"]
    output.parent.mkdir(parents=True, exist_ok=True)
    exported = 0
    distribution: dict[str, int] = {}
    with output.open("w", encoding="utf-8") as handle:
        for document in tasks.find({}, {"_id": 0}).sort("review_id", 1):
            label = consensus_label(document)
            if not label:
                continue
            row = {
                "review_id": document["review_id"],
                "title": document.get("title"),
                "text": document["text"],
                "label": label,
                "weak_label": document.get("weak_label"),
                "model_confidence": document.get("model_confidence"),
                "category": document.get("category"),
                "review_timestamp": document.get("review_timestamp"),
                "annotation_count": len(document.get("annotations", [])),
            }
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            exported += 1
            distribution[label] = distribution.get(label, 0) + 1
    summary = {
        **annotation_progress(tasks),
        "exported": exported,
        "label_distribution": distribution,
        "output": str(output),
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(json.dumps(summary, ensure_ascii=False, indent=2))
    client.close()


if __name__ == "__main__":
    app()
