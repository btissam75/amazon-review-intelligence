from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Iterable, Iterator
from urllib.request import Request, urlopen

import typer
from pydantic import ValidationError

from .models import normalize_review
from .profile import ProfileAccumulator

app = typer.Typer(add_completion=False, help="Prepare canonical Amazon review events.")
DATASET_URL = (
    "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/"
    "raw/review_categories/{category}.jsonl.gz"
)


def read_source(path: Path) -> Iterator[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                yield {"__parse_error__": str(exc), "__line_number__": line_number}


def read_remote(category: str) -> Iterator[dict]:
    """Stream and decompress a category without storing its complete archive."""
    url = DATASET_URL.format(category=category)
    request = Request(url, headers={"User-Agent": "amazon-review-intelligence/0.1"})
    with urlopen(request, timeout=60) as response, gzip.GzipFile(fileobj=response) as archive:
        for line_number, raw_line in enumerate(archive, start=1):
            if not raw_line.strip():
                continue
            try:
                yield json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                yield {"__parse_error__": str(exc), "__line_number__": line_number}


def prepare_records(
    records: Iterable[dict],
    category: str,
    output: Path,
    dlq: Path,
    limit: int | None = None,
) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    dlq.parent.mkdir(parents=True, exist_ok=True)
    valid_count = 0
    rejected = 0
    seen: set[str] = set()
    profiler = ProfileAccumulator()

    with output.open("w", encoding="utf-8") as clean_handle, dlq.open(
        "w", encoding="utf-8"
    ) as dlq_handle:
        for source_position, record in enumerate(records, start=1):
            if limit is not None and valid_count >= limit:
                break
            try:
                if "__parse_error__" in record:
                    raise ValueError(record["__parse_error__"])
                event = normalize_review(record, category)
                if event.review_id in seen:
                    raise ValueError("duplicate review_id")
                seen.add(event.review_id)
                payload = event.model_dump(mode="json")
                clean_handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
                profiler.add(payload)
                valid_count += 1
            except (ValidationError, ValueError, TypeError) as exc:
                rejected += 1
                dlq_handle.write(
                    json.dumps(
                        {
                            "source_position": source_position,
                            "error": str(exc),
                            "record": record,
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                    + "\n"
                )

    report = profiler.result()
    report.update({"rejected_count": rejected, "category": category})
    return report


def save_report(report: dict, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


@app.command("file")
def from_file(
    input_path: Path,
    category: str = "All_Beauty",
    limit: int | None = 50_000,
    output: Path = Path("data/clean/reviews.jsonl"),
    dlq: Path = Path("data/clean/reviews.dlq.jsonl"),
    report: Path = Path("data/reports/quality_report.json"),
) -> None:
    result = prepare_records(read_source(input_path), category, output, dlq, limit)
    save_report(result, report)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("download")
def download(
    category: str = "All_Beauty",
    limit: int = 50_000,
    output: Path = Path("data/clean/reviews.jsonl"),
    dlq: Path = Path("data/clean/reviews.dlq.jsonl"),
    report: Path = Path("data/reports/quality_report.json"),
) -> None:
    result = prepare_records(read_remote(category), category, output, dlq, limit)
    save_report(result, report)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()

