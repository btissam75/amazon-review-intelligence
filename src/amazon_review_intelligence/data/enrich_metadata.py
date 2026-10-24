from __future__ import annotations

import argparse
import gzip
import json
import os
import time
import urllib.request
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient, UpdateOne


METADATA_URL = (
    "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/"
    "raw/meta_categories/meta_{category}.jsonl.gz"
)
DEFAULT_CATEGORIES = ("All_Beauty", "Appliances")


def _clean_text(value: Any, limit: int = 4_000) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned[:limit] or None


def _primary_image(images: Any) -> str | None:
    if not isinstance(images, list):
        return None
    ordered = sorted(images, key=lambda image: image.get("variant") != "MAIN")
    for image in ordered:
        if not isinstance(image, dict):
            continue
        for key in ("large", "hi_res", "thumb"):
            if image.get(key):
                return str(image[key])
    return None


def metadata_update(row: dict[str, Any], category: str) -> tuple[str, dict[str, Any]] | None:
    product_id = _clean_text(row.get("parent_asin"), 40)
    name = _clean_text(row.get("title"), 500)
    if not product_id or not name:
        return None

    details = row.get("details") if isinstance(row.get("details"), dict) else {}
    brand = _clean_text(row.get("store"), 200) or _clean_text(details.get("Brand"), 200)
    features = [
        text
        for value in (row.get("features") or [])[:8]
        if (text := _clean_text(value, 500))
    ]
    description = [
        text
        for value in (row.get("description") or [])[:4]
        if (text := _clean_text(value, 1_000))
    ]
    categories = [
        text
        for value in (row.get("categories") or [])[:8]
        if (text := _clean_text(value, 150))
    ]
    price = row.get("price")
    if not isinstance(price, (int, float)):
        price = None

    return product_id, {
        "name": name,
        "brand": brand,
        "price": price,
        "image_url": _primary_image(row.get("images")),
        "main_category": _clean_text(row.get("main_category"), 200),
        "categories": categories,
        "features": features,
        "description": description,
        "metadata_rating": row.get("average_rating"),
        "metadata_rating_count": row.get("rating_number"),
        "metadata_source": "amazon_reviews_2023",
        "metadata_category": category,
        "metadata_updated_at": datetime.now(timezone.utc),
    }


def _rows(url: str) -> Iterable[dict[str, Any]]:
    request = urllib.request.Request(url, headers={"User-Agent": "ARI-Metadata-Enricher/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        with gzip.GzipFile(fileobj=response) as stream:
            for raw_line in stream:
                try:
                    yield json.loads(raw_line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue


def enrich_category(collection, category: str, batch_size: int = 1_000) -> dict[str, int]:
    url = METADATA_URL.format(category=category)
    scanned = matched = modified = 0
    operations: list[UpdateOne] = []
    started = time.monotonic()

    def flush() -> None:
        nonlocal matched, modified, operations
        if not operations:
            return
        result = collection.bulk_write(operations, ordered=False)
        matched += result.matched_count
        modified += result.modified_count
        operations = []

    for row in _rows(url):
        scanned += 1
        update = metadata_update(row, category)
        if update:
            product_id, fields = update
            operations.append(UpdateOne({"product_id": product_id}, {"$set": fields}))
        if len(operations) >= batch_size:
            flush()
        if scanned % 25_000 == 0:
            print(
                f"metadata category={category} scanned={scanned} matched={matched} "
                f"elapsed_seconds={time.monotonic() - started:.1f}",
                flush=True,
            )
    flush()
    return {"scanned": scanned, "matched": matched, "modified": modified}


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich product profiles with Amazon metadata")
    parser.add_argument("--categories", nargs="+", default=list(DEFAULT_CATEGORIES))
    parser.add_argument("--batch-size", type=int, default=1_000)
    args = parser.parse_args()

    client = MongoClient(
        os.getenv("ARI_MONGODB_URI", "mongodb://mongodb:27017"),
        serverSelectionTimeoutMS=10_000,
    )
    database = client[os.getenv("ARI_MONGODB_DATABASE", "amazon_reviews")]
    products = database["product_profiles"]
    products.create_index(
        [("name", "text"), ("brand", "text"), ("main_category", "text")],
        name="product_search_text",
        default_language="none",
    )

    for category in args.categories:
        result = enrich_category(products, category, max(100, args.batch_size))
        print(f"metadata_complete category={category} {result}", flush=True)

    enriched = products.count_documents({"name": {"$type": "string", "$ne": ""}})
    print(f"metadata_products_ready={enriched}", flush=True)
    client.close()


if __name__ == "__main__":
    main()
