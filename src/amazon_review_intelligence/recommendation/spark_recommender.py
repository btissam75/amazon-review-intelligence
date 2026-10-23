from __future__ import annotations

import math
import os
from datetime import datetime, timezone

from pyspark.ml.feature import StringIndexer
from pyspark.ml.recommendation import ALS
from pyspark.sql import DataFrame, SparkSession, Window, functions as F, types as T

from amazon_review_intelligence.recommendation.scoring import (
    ALS_WEIGHT,
    POPULARITY_WEIGHT,
    QUALITY_WEIGHT,
)


PROFILE_SCHEMA = T.StructType(
    [
        T.StructField("product_id", T.StringType(), False),
        T.StructField("review_count", T.LongType(), False),
        T.StructField("average_rating", T.DoubleType(), False),
        T.StructField("positive_ratio", T.DoubleType(), False),
        T.StructField("negative_ratio", T.DoubleType(), False),
        T.StructField("verified_ratio", T.DoubleType(), False),
        T.StructField("average_confidence", T.DoubleType(), False),
        T.StructField("quality_score", T.DoubleType(), False),
    ]
)


def rebuild_product_profiles() -> int:
    """Aggregate NLP outputs server-side and materialize one profile per product."""
    from pymongo import ASCENDING, DESCENDING, MongoClient

    client = MongoClient(os.getenv("ARI_MONGODB_URI", "mongodb://mongodb:27017"))
    database = client[os.getenv("ARI_MONGODB_DATABASE", "amazon_reviews")]
    profiles = database["product_profiles"]
    profiles.create_index("product_id", unique=True)
    profiles.create_index([("quality_score", DESCENDING), ("review_count", DESCENDING)])

    pipeline = [
        {
            "$group": {
                "_id": "$product_id",
                "review_count": {"$sum": 1},
                "average_rating": {"$avg": "$rating"},
                "average_confidence": {"$avg": "$sentiment_score"},
                "positive_count": {
                    "$sum": {"$cond": [{"$eq": ["$sentiment_label", "positive"]}, 1, 0]}
                },
                "negative_count": {
                    "$sum": {"$cond": [{"$eq": ["$sentiment_label", "negative"]}, 1, 0]}
                },
                "neutral_count": {
                    "$sum": {"$cond": [{"$eq": ["$sentiment_label", "neutral"]}, 1, 0]}
                },
                "verified_count": {
                    "$sum": {"$cond": [{"$eq": ["$verified_purchase", True]}, 1, 0]}
                },
            }
        },
        {
            "$set": {
                "product_id": "$_id",
                "positive_ratio": {"$divide": ["$positive_count", "$review_count"]},
                "negative_ratio": {"$divide": ["$negative_count", "$review_count"]},
                "neutral_ratio": {"$divide": ["$neutral_count", "$review_count"]},
                "verified_ratio": {"$divide": ["$verified_count", "$review_count"]},
                "rating_score": {
                    "$min": [
                        1.0,
                        {
                            "$max": [
                                0.0,
                                {
                                    "$divide": [
                                        {"$subtract": ["$average_rating", 1.0]},
                                        4.0,
                                    ]
                                },
                            ]
                        },
                    ]
                },
                "sentiment_balance": {
                    "$divide": [
                        {"$subtract": ["$positive_count", "$negative_count"]},
                        "$review_count",
                    ]
                },
                "updated_at": "$$NOW",
            }
        },
        {
            "$set": {
                "confidence_adjusted_sentiment": {
                    "$add": [
                        0.5,
                        {
                            "$multiply": [
                                {"$divide": ["$sentiment_balance", 2.0]},
                                "$average_confidence",
                            ]
                        },
                    ]
                }
            }
        },
        {
            "$set": {
                "quality_score": {
                    "$min": [
                        1.0,
                        {
                            "$max": [
                                0.0,
                                {
                                    "$add": [
                                        {"$multiply": [0.65, "$confidence_adjusted_sentiment"]},
                                        {"$multiply": [0.25, "$rating_score"]},
                                        {"$multiply": [0.10, "$verified_ratio"]},
                                    ]
                                },
                            ]
                        },
                    ]
                }
            }
        },
        {"$unset": ["_id", "rating_score", "sentiment_balance", "confidence_adjusted_sentiment"]},
        {
            "$merge": {
                "into": "product_profiles",
                "on": "product_id",
                "whenMatched": "replace",
                "whenNotMatched": "insert",
            }
        },
    ]
    list(database["reviews_enriched"].aggregate(pipeline, allowDiskUse=True))
    profiles.create_index([("product_id", ASCENDING), ("updated_at", DESCENDING)])
    count = profiles.count_documents({})
    client.close()
    print(f"product_profiles_ready={count}", flush=True)
    return count


def load_product_profiles(spark: SparkSession) -> DataFrame:
    from pymongo import MongoClient

    client = MongoClient(os.getenv("ARI_MONGODB_URI", "mongodb://mongodb:27017"))
    collection = client[os.getenv("ARI_MONGODB_DATABASE", "amazon_reviews")]["product_profiles"]
    fields = {field.name: 1 for field in PROFILE_SCHEMA.fields}
    fields["_id"] = 0
    rows = []
    for document in collection.find({}, fields, batch_size=5_000):
        rows.append(
            {
                field.name: (
                    str(document.get(field.name, ""))
                    if field.name == "product_id"
                    else int(document.get(field.name, 0))
                    if field.name == "review_count"
                    else float(document.get(field.name, 0.0) or 0.0)
                )
                for field in PROFILE_SCHEMA.fields
            }
        )
    client.close()
    if not rows:
        raise RuntimeError("product_profiles is empty")
    return spark.createDataFrame(rows, PROFILE_SCHEMA)


def write_recommendation_partition(rows) -> None:
    """Write recommendation documents from one Spark partition using idempotent upserts."""
    from pymongo import MongoClient, UpdateOne

    client = MongoClient(os.getenv("ARI_MONGODB_URI", "mongodb://mongodb:27017"))
    collection = client[os.getenv("ARI_MONGODB_DATABASE", "amazon_reviews")][
        "user_recommendations"
    ]
    version = os.getenv("ARI_RECOMMENDATION_MODEL_VERSION", "hybrid-als-nlp-v1")
    generated_at = datetime.now(timezone.utc)
    operations = []
    for row in rows:
        document = row.asDict(recursive=True)
        document["model_version"] = version
        document["generated_at"] = generated_at
        operations.append(
            UpdateOne({"user_id": document["user_id"]}, {"$set": document}, upsert=True)
        )
        if len(operations) >= 250:
            collection.bulk_write(operations, ordered=False)
            operations.clear()
    if operations:
        collection.bulk_write(operations, ordered=False)
    client.close()


def store_fallback_recommendations(limit: int = 100) -> None:
    from pymongo import MongoClient

    client = MongoClient(os.getenv("ARI_MONGODB_URI", "mongodb://mongodb:27017"))
    database = client[os.getenv("ARI_MONGODB_DATABASE", "amazon_reviews")]
    products = list(
        database["product_profiles"].find(
            {"review_count": {"$gte": 5}},
            {
                "_id": 0,
                "product_id": 1,
                "quality_score": 1,
                "positive_ratio": 1,
                "average_rating": 1,
                "review_count": 1,
            },
        ).sort([("quality_score", -1), ("review_count", -1)]).limit(limit)
    )
    database["recommendation_fallbacks"].update_one(
        {"name": "quality_popularity"},
        {
            "$set": {
                "name": "quality_popularity",
                "products": products,
                "generated_at": datetime.now(timezone.utc),
                "model_version": os.getenv(
                    "ARI_RECOMMENDATION_MODEL_VERSION", "hybrid-als-nlp-v1"
                ),
            }
        },
        upsert=True,
    )
    client.close()


def main() -> None:
    input_pattern = os.getenv(
        "ARI_RECOMMENDATION_INPUT", "/opt/app/data/clean/reviews_*.jsonl"
    )
    top_k = int(os.getenv("ARI_RECOMMENDATION_TOP_K", "10"))
    candidate_count = max(top_k, int(os.getenv("ARI_RECOMMENDATION_CANDIDATES", "20")))
    min_user_interactions = int(os.getenv("ARI_RECOMMENDATION_MIN_USER_INTERACTIONS", "2"))

    spark = (
        SparkSession.builder.appName("amazon-review-hybrid-recommender")
        .config("spark.sql.shuffle.partitions", os.getenv("ARI_SPARK_SHUFFLE_PARTITIONS", "32"))
        .config("spark.sql.adaptive.enabled", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    rebuild_product_profiles()
    profiles = load_product_profiles(spark).cache()
    max_reviews = profiles.agg(F.max("review_count")).first()[0] or 1
    popularity_denominator = max(math.log1p(max_reviews), 1.0)

    raw = spark.read.json(input_pattern).select("user_id", "product_id", "rating")
    interactions = (
        raw.filter(
            F.col("user_id").isNotNull()
            & F.col("product_id").isNotNull()
            & F.col("rating").between(1.0, 5.0)
        )
        .groupBy("user_id", "product_id")
        .agg(F.avg("rating").alias("rating"))
    )
    eligible_users = (
        interactions.groupBy("user_id")
        .count()
        .filter(F.col("count") >= min_user_interactions)
        .select("user_id")
    )
    interactions = interactions.join(eligible_users, "user_id", "inner").cache()

    user_indexer = StringIndexer(inputCol="user_id", outputCol="user_index", handleInvalid="skip")
    product_indexer = StringIndexer(
        inputCol="product_id", outputCol="product_index", handleInvalid="skip"
    )
    user_model = user_indexer.fit(interactions)
    indexed_users = user_model.transform(interactions)
    product_model = product_indexer.fit(indexed_users)
    indexed = (
        product_model.transform(indexed_users)
        .withColumn("user_index", F.col("user_index").cast("integer"))
        .withColumn("product_index", F.col("product_index").cast("integer"))
        .cache()
    )

    user_map = indexed.select("user_index", "user_id").distinct()
    product_map = indexed.select("product_index", "product_id").distinct()
    seen = indexed.select("user_id", "product_id").distinct()

    als = ALS(
        userCol="user_index",
        itemCol="product_index",
        ratingCol="rating",
        rank=int(os.getenv("ARI_ALS_RANK", "8")),
        maxIter=int(os.getenv("ARI_ALS_MAX_ITER", "5")),
        regParam=float(os.getenv("ARI_ALS_REG_PARAM", "0.1")),
        nonnegative=True,
        coldStartStrategy="drop",
        seed=42,
    )
    model = als.fit(indexed)
    candidates = (
        model.recommendForAllUsers(candidate_count)
        .select("user_index", F.explode("recommendations").alias("recommendation"))
        .select(
            "user_index",
            F.col("recommendation.product_index").alias("product_index"),
            F.col("recommendation.rating").cast("double").alias("als_prediction"),
        )
        .join(user_map, "user_index")
        .join(product_map, "product_index")
        .join(seen, ["user_id", "product_id"], "left_anti")
        .join(F.broadcast(profiles), "product_id", "inner")
    )

    als_normalized = F.greatest(
        F.lit(0.0), F.least(F.lit(1.0), (F.col("als_prediction") - 1.0) / 4.0)
    )
    popularity = F.log1p(F.col("review_count")) / F.lit(popularity_denominator)
    has_specific_reason = (
        (F.col("positive_ratio") >= 0.70)
        | (F.col("average_rating") >= 4.2)
        | (F.col("verified_ratio") >= 0.70)
    )
    scored = candidates.withColumn(
        "score",
        F.lit(ALS_WEIGHT) * als_normalized
        + F.lit(QUALITY_WEIGHT) * F.col("quality_score")
        + F.lit(POPULARITY_WEIGHT) * popularity,
    ).withColumn(
        "reason",
        F.when(
            has_specific_reason,
            F.concat_ws(
                " · ",
                F.when(F.col("positive_ratio") >= 0.70, "sentiment client très positif"),
                F.when(F.col("average_rating") >= 4.2, "excellente note moyenne"),
                F.when(F.col("verified_ratio") >= 0.70, "majorité d'achats vérifiés"),
            ),
        ).otherwise("compatible avec vos préférences"),
    )
    ranking = Window.partitionBy("user_id").orderBy(F.desc("score"), F.asc("product_id"))
    ranked = (
        scored.withColumn("rank", F.row_number().over(ranking))
        .filter(F.col("rank") <= top_k)
        .select(
            "user_id",
            F.struct(
                "rank",
                "product_id",
                F.round("score", 6).alias("score"),
                F.round("als_prediction", 6).alias("als_prediction"),
                F.round("quality_score", 6).alias("quality_score"),
                F.round("positive_ratio", 6).alias("positive_ratio"),
                F.round("average_rating", 4).alias("average_rating"),
                "review_count",
                "reason",
            ).alias("recommendation"),
        )
    )
    recommendation_documents = ranked.groupBy("user_id").agg(
        F.sort_array(F.collect_list("recommendation")).alias("recommendations")
    )
    recommendation_documents.rdd.foreachPartition(write_recommendation_partition)

    store_fallback_recommendations()
    from pymongo import ASCENDING, DESCENDING, MongoClient

    client = MongoClient(os.getenv("ARI_MONGODB_URI", "mongodb://mongodb:27017"))
    database = client[os.getenv("ARI_MONGODB_DATABASE", "amazon_reviews")]
    recommendations = database["user_recommendations"]
    recommendations.create_index("user_id", unique=True)
    recommendations.create_index([("model_version", ASCENDING), ("generated_at", DESCENDING)])
    recommendation_count = recommendations.count_documents({})
    database["model_registry"].update_one(
        {"model_version": os.getenv("ARI_RECOMMENDATION_MODEL_VERSION", "hybrid-als-nlp-v1")},
        {
            "$set": {
                "model_version": os.getenv(
                    "ARI_RECOMMENDATION_MODEL_VERSION", "hybrid-als-nlp-v1"
                ),
                "model_type": "hybrid_als_nlp",
                "top_k": top_k,
                "candidate_count": candidate_count,
                "minimum_user_interactions": min_user_interactions,
                "weights": {
                    "als": ALS_WEIGHT,
                    "nlp_quality": QUALITY_WEIGHT,
                    "popularity": POPULARITY_WEIGHT,
                },
                "recommendation_documents": recommendation_count,
                "trained_at": datetime.now(timezone.utc),
                "status": "ready",
            }
        },
        upsert=True,
    )
    client.close()
    print(f"recommendation_users_ready={recommendation_count} top_k={top_k}", flush=True)
    spark.stop()


if __name__ == "__main__":
    main()

