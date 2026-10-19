from __future__ import annotations

import argparse
import glob
import json
import os
import time
from pathlib import Path

from kafka import KafkaProducer


def iter_events(pattern: str):
    paths = sorted(Path(path) for path in glob.glob(pattern) if ".dlq." not in path)
    if not paths:
        raise FileNotFoundError(f"no input file matches {pattern!r}")
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay canonical reviews into Kafka")
    parser.add_argument("--input", default="/opt/app/data/clean/reviews_*.jsonl")
    parser.add_argument("--limit", type=int, default=1_000_000)
    parser.add_argument("--rate", type=float, default=5_000, help="events/second; 0 means unlimited")
    args = parser.parse_args()

    servers = os.getenv("ARI_KAFKA_BOOTSTRAP_SERVERS", "kafka:9092").split(",")
    topic = os.getenv("ARI_RAW_TOPIC", "amazon.reviews.raw")
    producer = KafkaProducer(
        bootstrap_servers=servers,
        key_serializer=lambda value: value.encode("utf-8"),
        value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
        acks="all",
        retries=10,
        compression_type="gzip",
        linger_ms=20,
        batch_size=131_072,
    )
    started = time.monotonic()
    sent = 0
    for event in iter_events(args.input):
        if sent >= args.limit:
            break
        producer.send(topic, key=event["product_id"], value=event)
        sent += 1
        if args.rate > 0 and sent % 1_000 == 0:
            expected = sent / args.rate
            elapsed = time.monotonic() - started
            if expected > elapsed:
                time.sleep(expected - elapsed)
        if sent % 25_000 == 0:
            print(f"published={sent} elapsed_seconds={time.monotonic() - started:.1f}", flush=True)
    producer.flush()
    producer.close()
    print(f"completed published={sent} elapsed_seconds={time.monotonic() - started:.1f}", flush=True)


if __name__ == "__main__":
    main()

