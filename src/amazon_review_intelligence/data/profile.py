from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

import typer

app = typer.Typer(add_completion=False)


class ProfileAccumulator:
    """Incremental quality profile suitable for million-row streams."""

    def __init__(self) -> None:
        self.ratings: Counter[str] = Counter()
        self.categories: Counter[str] = Counter()
        self.products: set[str] = set()
        self.reviews: set[str] = set()
        self.duplicate_review_ids = 0
        self.empty_texts = 0
        self.text_lengths: list[int] = []
        self.count = 0

    def add(self, record: dict) -> None:
        self.count += 1
        review_id = str(record.get("review_id", ""))
        if review_id in self.reviews:
            self.duplicate_review_ids += 1
        self.reviews.add(review_id)
        self.products.add(str(record.get("product_id", "")))
        self.ratings[str(record.get("rating"))] += 1
        self.categories[str(record.get("category", "unknown"))] += 1
        length = len(str(record.get("text", "")))
        self.text_lengths.append(length)
        self.empty_texts += int(length == 0)

    def result(self) -> dict:
        sorted_lengths = sorted(self.text_lengths)

        def percentile(fraction: float) -> int:
            if not sorted_lengths:
                return 0
            position = min(int((len(sorted_lengths) - 1) * fraction), len(sorted_lengths) - 1)
            return sorted_lengths[position]

        return {
            "record_count": self.count,
            "unique_review_ids": len(self.reviews),
            "unique_products": len(self.products),
            "duplicate_review_ids": self.duplicate_review_ids,
            "empty_texts": self.empty_texts,
            "rating_distribution": dict(sorted(self.ratings.items())),
            "category_distribution": dict(self.categories.most_common()),
            "text_length": {
                "min": sorted_lengths[0] if sorted_lengths else 0,
                "p50": percentile(0.50),
                "p95": percentile(0.95),
                "max": sorted_lengths[-1] if sorted_lengths else 0,
            },
        }


def build_profile(records: Iterable[dict]) -> dict:
    accumulator = ProfileAccumulator()
    for record in records:
        accumulator.add(record)
    return accumulator.result()


def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


@app.command()
def main(
    input_path: Path,
    output: Path = Path("data/reports/quality_report.json"),
) -> None:
    report = build_profile(read_jsonl(input_path))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()

