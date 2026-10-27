from __future__ import annotations

import os
import time

from pyspark.sql import DataFrame, SparkSession, functions as F, types as T

from amazon_review_intelligence.nlp.inference import predict_sentiment
from amazon_review_intelligence.nlp.aspects import ASPECT_MODEL_VERSION, analyze_aspects


REVIEW_SCHEMA = T.StructType(
    [
        T.StructField("event_id", T.StringType(), False),
        T.StructField("review_id", T.StringType(), False),
        T.StructField("product_id", T.StringType(), False),
        T.StructField("user_id", T.StringType(), True),
        T.StructField("rating", T.DoubleType(), False),
        T.StructField("title", T.StringType(), True),
        T.StructField("text", T.StringType(), False),
        T.StructField("verified_purchase", T.BooleanType(), True),
        T.StructField("helpful_vote", T.LongType(), True),
        T.StructField("category", T.StringType(), False),
        T.StructField("review_timestamp", T.StringType(), False),
        T.StructField("ingestion_timestamp", T.StringType(), False),
        T.StructField("source", T.StringType(), False),
        T.StructField("schema_version", T.IntegerType(), False),
        T.StructField("content_hash", T.StringType(), False),
    ]
)

SENTIMENT_SCHEMA = T.StructType(
    [
        T.StructField("label", T.StringType(), False),
        T.StructField("score", T.DoubleType(), False),
    ]
)

ASPECT_SCHEMA = T.ArrayType(
    T.StructType(
        [
            T.StructField("aspect", T.StringType(), False),
            T.StructField("label", T.StringType(), False),
            T.StructField("score", T.DoubleType(), False),
            T.StructField("mentions", T.IntegerType(), False),
            T.StructField("evidence", T.ArrayType(T.StringType()), False),
        ]
    )
)


sentiment_udf = F.udf(predict_sentiment, SENTIMENT_SCHEMA)
aspect_udf = F.udf(lambda title, text: analyze_aspects(text, title), ASPECT_SCHEMA)


def run_mongo_operation_with_retry(operation, operation_name: str):
    """Retry a MongoDB operation when Docker DNS or the server is temporarily unavailable."""
    from pymongo.errors import AutoReconnect, ConnectionFailure, NetworkTimeout

    max_attempts = int(os.getenv("ARI_MONGODB_MAX_RETRIES", "30"))
    delay = float(os.getenv("ARI_MONGODB_RETRY_DELAY_SECONDS", "2"))
    retryable_errors = (AutoReconnect, ConnectionFailure, NetworkTimeout)
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except retryable_errors as error:
            if attempt == max_attempts:
                raise
            wait_seconds = min(delay * (2 ** min(attempt - 1, 4)), 30.0)
            print(
                f"mongo_retry operation={operation_name} attempt={attempt}/{max_attempts} "
                f"wait_seconds={wait_seconds:.1f} error={error}",
                flush=True,
            )
            time.sleep(wait_seconds)


def write_outputs(batch: DataFrame, batch_id: int) -> None:
    """Write one enriched micro-batch to Kafka and idempotently to MongoDB."""
    # The source is a historical replay and is not ordered by event time. Deduplicate only
    # inside the current batch; MongoDB's unique review_id index handles cross-batch retries.
    batch = batch.dropDuplicates(["review_id"])
    batch.persist()
    (
        batch.select(
            F.col("product_id").cast("string").alias("key"),
            F.to_json(F.struct(*batch.columns)).alias("value"),
        )
        .write.format("kafka")
        .option("kafka.bootstrap.servers", os.getenv("ARI_KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"))
        .option("topic", os.getenv("ARI_ENRICHED_TOPIC", "amazon.reviews.enriched"))
        .save()
    )
    documents = (row.asDict(recursive=True) for row in batch.toLocalIterator())
    from pymongo import MongoClient, UpdateOne

    client = MongoClient(
        os.getenv("ARI_MONGODB_URI", "mongodb://mongodb:27017"),
        connectTimeoutMS=5_000,
        serverSelectionTimeoutMS=5_000,
    )
    collection = client[os.getenv("ARI_MONGODB_DATABASE", "amazon_reviews")][
        "reviews_enriched"
    ]
    operations = []
    total = 0
    for document in documents:
        operations.append(UpdateOne({"review_id": document["review_id"]}, {"$set": document}, upsert=True))
        if len(operations) >= 1_000:
            run_mongo_operation_with_retry(
                lambda: collection.bulk_write(operations, ordered=False),
                "bulk_write",
            )
            total += len(operations)
            operations.clear()
    if operations:
        run_mongo_operation_with_retry(
            lambda: collection.bulk_write(operations, ordered=False),
            "bulk_write",
        )
        total += len(operations)
    run_mongo_operation_with_retry(
        lambda: collection.create_index("review_id", unique=True),
        "create_review_id_index",
    )
    run_mongo_operation_with_retry(
        lambda: collection.create_index([("product_id", 1), ("review_timestamp", -1)]),
        "create_product_timestamp_index",
    )
    client.close()
    batch.unpersist()
    print(f"completed_batch={batch_id} kafka_and_mongo_rows={total}", flush=True)


def main() -> None:
    kafka_servers = os.getenv("ARI_KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    raw_topic = os.getenv("ARI_RAW_TOPIC", "amazon.reviews.raw")
    dlq_topic = os.getenv("ARI_DLQ_TOPIC", "amazon.reviews.dlq")
    checkpoint_root = os.getenv("ARI_CHECKPOINT_ROOT", "/opt/app/checkpoints")

    spark = (
        SparkSession.builder.appName("amazon-review-sentiment-stream")
        .config("spark.sql.shuffle.partitions", os.getenv("ARI_SPARK_SHUFFLE_PARTITIONS", "8"))
        .config("spark.sql.adaptive.enabled", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", kafka_servers)
        .option("subscribe", raw_topic)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "true")
        .option("maxOffsetsPerTrigger", os.getenv("ARI_MAX_OFFSETS_PER_TRIGGER", "20000"))
        .load()
    )
    parsed = raw.select(
        F.from_json(F.col("value").cast("string"), REVIEW_SCHEMA).alias("review"),
        F.col("timestamp").alias("kafka_timestamp"),
    ).select("review.*", "kafka_timestamp")

    validity = (
        F.col("review_id").isNotNull()
        & F.col("product_id").isNotNull()
        & (F.length(F.trim(F.col("text"))) >= 2)
        & F.col("rating").between(1.0, 5.0)
    )
    invalid = parsed.filter(~validity | F.col("event_id").isNull()).withColumn(
        "error", F.lit("schema_or_business_rule_validation_failed")
    )
    valid = (
        parsed.filter(validity)
        .withColumn("review_timestamp", F.to_timestamp("review_timestamp"))
    )
    enriched = (
        valid.withColumn("nlp", sentiment_udf(F.concat_ws(" ", "title", "text")))
        .withColumn("sentiment_label", F.col("nlp.label"))
        .withColumn("sentiment_score", F.col("nlp.score"))
        .withColumn("model_name", F.lit("tfidf_logistic_regression"))
        .withColumn("model_version", F.lit("1"))
        .withColumn("aspect_sentiments", aspect_udf("title", "text"))
        .withColumn("aspect_model_version", F.lit(ASPECT_MODEL_VERSION))
        .withColumn("processed_at", F.current_timestamp())
        .drop("nlp")
    )

    dlq_query = (
        invalid.select(
            F.coalesce(F.col("product_id"), F.lit("invalid")).alias("key"),
            F.to_json(F.struct(*invalid.columns)).alias("value"),
        )
        .writeStream.format("kafka")
        .option("kafka.bootstrap.servers", kafka_servers)
        .option("topic", dlq_topic)
        .option("checkpointLocation", f"{checkpoint_root}/kafka-dlq")
        .outputMode("append")
        .start()
    )
    mongo_query = (
        enriched.writeStream.foreachBatch(write_outputs)
        .option("checkpointLocation", f"{checkpoint_root}/enriched-outputs")
        .outputMode("append")
        .start()
    )
    spark.streams.awaitAnyTermination()
    dlq_query.stop()
    mongo_query.stop()


if __name__ == "__main__":
    main()
