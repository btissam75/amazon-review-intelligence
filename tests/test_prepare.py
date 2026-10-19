import json

from amazon_review_intelligence.data.prepare import prepare_records


def test_prepare_routes_invalid_and_duplicates_to_dlq(tmp_path):
    records = [
        {
            "review_id": "r1",
            "rating": 5,
            "text": "Excellent product",
            "parent_asin": "p1",
            "timestamp": 1_690_000_000_000,
        },
        {
            "review_id": "r1",
            "rating": 5,
            "text": "Duplicate",
            "parent_asin": "p1",
            "timestamp": 1_690_000_000_000,
        },
        {
            "review_id": "r2",
            "rating": 0,
            "text": "Invalid",
            "parent_asin": "p2",
            "timestamp": 1_690_000_000_000,
        },
    ]
    output = tmp_path / "clean.jsonl"
    dlq = tmp_path / "dlq.jsonl"
    report = prepare_records(records, "Test", output, dlq)

    assert report["record_count"] == 1
    assert report["rejected_count"] == 2
    assert len(output.read_text(encoding="utf-8").splitlines()) == 1
    errors = [json.loads(line) for line in dlq.read_text(encoding="utf-8").splitlines()]
    assert len(errors) == 2

