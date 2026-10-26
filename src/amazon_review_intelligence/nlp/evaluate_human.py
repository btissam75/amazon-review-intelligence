from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from .labels import LABELS


app = typer.Typer(
    add_completion=False,
    help="Evaluate the production sentiment model against human-reviewed labels.",
)


def load_reviewed_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Human-reviewed corpus not found: {path}. Run the annotation export first."
        )
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("label") not in LABELS:
                raise ValueError(
                    f"Invalid human label on line {line_number}: {record.get('label')!r}"
                )
            if not str(record.get("text", "")).strip():
                raise ValueError(f"Missing review text on line {line_number}")
            records.append(record)
    return records


def build_evaluation_report(
    records: list[dict[str, Any]],
    predictions: list[str],
    confidences: list[float],
    *,
    model_name: str,
    model_version: str,
) -> dict[str, Any]:
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

    if not records or len(records) != len(predictions) or len(records) != len(confidences):
        raise ValueError("records, predictions, and confidences must be non-empty and aligned")
    human_labels = [str(record["label"]) for record in records]
    classification = classification_report(
        human_labels,
        predictions,
        labels=list(LABELS),
        output_dict=True,
        zero_division=0,
    )
    matrix = confusion_matrix(human_labels, predictions, labels=list(LABELS)).tolist()
    errors = []
    for record, predicted, confidence in zip(records, predictions, confidences):
        if predicted == record["label"]:
            continue
        errors.append(
            {
                "review_id": record.get("review_id"),
                "human_label": record["label"],
                "predicted_label": predicted,
                "confidence": round(float(confidence), 6),
                "text_excerpt": " ".join(str(record.get("text", "")).split())[:240],
            }
        )
    errors.sort(key=lambda item: item["confidence"], reverse=True)
    weak_rows = [record for record in records if record.get("weak_label") in LABELS]
    weak_agreement = (
        sum(record["weak_label"] == record["label"] for record in weak_rows) / len(weak_rows)
        if weak_rows
        else None
    )
    low_confidence_threshold = 0.60
    per_class = {
        label: {
            "precision": float(classification[label]["precision"]),
            "recall": float(classification[label]["recall"]),
            "f1": float(classification[label]["f1-score"]),
            "support": int(classification[label]["support"]),
        }
        for label in LABELS
    }
    return {
        "model_name": model_name,
        "model_version": model_version,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_source": "human_consensus_or_adjudication",
        "dataset": {
            "size": len(records),
            "human_distribution": dict(Counter(human_labels)),
            "prediction_distribution": dict(Counter(predictions)),
        },
        "metrics": {
            "accuracy": float(accuracy_score(human_labels, predictions)),
            "macro_precision": float(classification["macro avg"]["precision"]),
            "macro_recall": float(classification["macro avg"]["recall"]),
            "macro_f1": float(classification["macro avg"]["f1-score"]),
            "weighted_f1": float(classification["weighted avg"]["f1-score"]),
        },
        "per_class": per_class,
        "confusion_matrix": {"labels": list(LABELS), "values": matrix},
        "confidence": {
            "mean": sum(float(value) for value in confidences) / len(confidences),
            "low_confidence_threshold": low_confidence_threshold,
            "low_confidence_count": sum(
                float(value) < low_confidence_threshold for value in confidences
            ),
            "low_confidence_ratio": sum(
                float(value) < low_confidence_threshold for value in confidences
            )
            / len(confidences),
        },
        "weak_label_human_agreement": float(weak_agreement) if weak_agreement is not None else None,
        "error_count": len(errors),
        "high_confidence_errors": errors[:25],
    }


def render_confusion_matrix(report: dict[str, Any], output: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = report["confusion_matrix"]["labels"]
    values = report["confusion_matrix"]["values"]
    figure, axis = plt.subplots(figsize=(7.2, 6.2))
    image = axis.imshow(values, cmap="Blues")
    figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    axis.set(
        xticks=range(len(labels)),
        yticks=range(len(labels)),
        xticklabels=labels,
        yticklabels=labels,
        xlabel="Prédiction du modèle",
        ylabel="Décision humaine",
        title=f"Matrice de confusion — {report['model_name']} v{report['model_version']}",
    )
    maximum = max(max(row) for row in values) if values else 0
    for row_index, row in enumerate(values):
        for column_index, value in enumerate(row):
            axis.text(
                column_index,
                row_index,
                str(value),
                ha="center",
                va="center",
                color="white" if maximum and value > maximum / 2 else "#10243d",
                fontweight="bold",
            )
    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=170, bbox_inches="tight")
    plt.close(figure)


def store_evaluation(report: dict[str, Any]) -> None:
    from pymongo import ASCENDING, MongoClient

    client = MongoClient(os.getenv("ARI_MONGODB_URI", "mongodb://mongodb:27017"))
    collection = client[os.getenv("ARI_MONGODB_DATABASE", "amazon_reviews")][
        "nlp_evaluations"
    ]
    collection.create_index(
        [("model_name", ASCENDING), ("model_version", ASCENDING)], unique=True
    )
    collection.replace_one(
        {"model_name": report["model_name"], "model_version": report["model_version"]},
        report,
        upsert=True,
    )
    client.close()


@app.command()
def evaluate(
    input_path: Path = typer.Option(Path("data/annotations/reviewed_reviews.jsonl")),
    model_path: Path = typer.Option(Path("models/sentiment_baseline.joblib")),
    report_path: Path = typer.Option(Path("data/reports/nlp_human_evaluation.json")),
    matrix_path: Path = typer.Option(Path("data/reports/nlp_confusion_matrix.png")),
    minimum_records: int = typer.Option(30, min=3),
) -> None:
    import joblib

    records = load_reviewed_records(input_path)
    if len(records) < minimum_records:
        raise typer.BadParameter(
            f"At least {minimum_records} completed human annotations are required; "
            f"found {len(records)}."
        )
    model = joblib.load(model_path)
    texts = [f"{record.get('title') or ''} {record['text']}".strip() for record in records]
    probabilities = model.predict_proba(texts)
    classes = list(model.classes_)
    best_indices = probabilities.argmax(axis=1)
    predictions = [str(classes[int(index)]) for index in best_indices]
    confidences = [float(probabilities[row, index]) for row, index in enumerate(best_indices)]
    report = build_evaluation_report(
        records,
        predictions,
        confidences,
        model_name="tfidf_logistic_regression",
        model_version="1",
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    render_confusion_matrix(report, matrix_path)
    store_evaluation(report)
    typer.echo(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
