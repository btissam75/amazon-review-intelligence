from __future__ import annotations

import json
import glob
import random
from collections import Counter
from pathlib import Path

import typer

from .labels import LABELS, rating_to_sentiment

app = typer.Typer(add_completion=False)


def load_balanced_sample(pattern: str, max_per_class: int, seed: int = 42) -> list[dict]:
    """Reservoir-sample every class while scanning arbitrarily large JSONL files."""
    randomizer = random.Random(seed)
    samples: dict[str, list[dict]] = {label: [] for label in LABELS}
    observed: Counter[str] = Counter()
    paths = sorted(Path(path) for path in glob.glob(pattern) if ".dlq." not in path)
    if not paths:
        raise FileNotFoundError(f"no input file matches {pattern!r}")
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                label = rating_to_sentiment(float(record["rating"]))
                observed[label] += 1
                bucket = samples[label]
                if len(bucket) < max_per_class:
                    bucket.append(record)
                else:
                    position = randomizer.randrange(observed[label])
                    if position < max_per_class:
                        bucket[position] = record
    return [record for label in LABELS for record in samples[label]]


def chronological_split(records: list[dict], test_fraction: float) -> tuple[list[dict], list[dict]]:
    """Use the latest reviews as test data to approximate production conditions."""
    ordered = sorted(records, key=lambda item: item["review_timestamp"])
    split_at = max(1, int(len(ordered) * (1 - test_fraction)))
    return ordered[:split_at], ordered[split_at:]


@app.command()
def train(
    input_pattern: str = "data/clean/reviews_*.jsonl",
    model_path: Path = Path("models/sentiment_baseline.joblib"),
    report_path: Path = Path("data/reports/baseline_metrics.json"),
    test_fraction: float = 0.2,
    max_per_class: int = 50_000,
) -> None:
    try:
        import joblib
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import classification_report, confusion_matrix
        from sklearn.pipeline import Pipeline
    except ImportError as exc:
        raise typer.BadParameter('Install NLP dependencies with: pip install -e ".[nlp]"') from exc

    if not 0.05 <= test_fraction <= 0.5:
        raise typer.BadParameter("test-fraction must be between 0.05 and 0.5")
    records = load_balanced_sample(input_pattern, max_per_class=max_per_class)
    if len(records) < 30:
        raise typer.BadParameter("at least 30 clean reviews are required")

    train_records, test_records = chronological_split(records, test_fraction)
    x_train = [f'{row.get("title", "")} {row["text"]}'.strip() for row in train_records]
    y_train = [rating_to_sentiment(float(row["rating"])) for row in train_records]
    x_test = [f'{row.get("title", "")} {row["text"]}'.strip() for row in test_records]
    y_test = [rating_to_sentiment(float(row["rating"])) for row in test_records]

    missing = set(LABELS) - set(y_train)
    if missing:
        raise typer.BadParameter(f"training split is missing classes: {sorted(missing)}")

    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=100_000,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1_000,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )
    pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)
    metrics = classification_report(
        y_test,
        predictions,
        labels=list(LABELS),
        output_dict=True,
        zero_division=0,
    )
    report = {
        "model": "tfidf_logistic_regression",
        "model_version": "1",
        "split": "chronological",
        "sampling": "class-wise reservoir",
        "max_per_class": max_per_class,
        "train_size": len(train_records),
        "test_size": len(test_records),
        "train_distribution": dict(Counter(y_train)),
        "test_distribution": dict(Counter(y_test)),
        "classification_report": metrics,
        "confusion_matrix": {
            "labels": list(LABELS),
            "values": confusion_matrix(y_test, predictions, labels=list(LABELS)).tolist(),
        },
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, model_path)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    typer.echo(json.dumps(report, indent=2))


if __name__ == "__main__":
    app()

