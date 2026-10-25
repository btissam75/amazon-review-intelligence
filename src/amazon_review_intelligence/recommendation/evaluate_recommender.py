from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

from pyspark.ml.recommendation import ALS
from pyspark.sql import DataFrame, SparkSession, Window, functions as F, types as T

from amazon_review_intelligence.nlp.inference import predict_sentiment
from amazon_review_intelligence.recommendation.scoring import (
    ALS_WEIGHT,
    POPULARITY_WEIGHT,
    QUALITY_WEIGHT,
)
from amazon_review_intelligence.recommendation.spark_recommender import build_distributed_index


SENTIMENT_SCHEMA = T.StructType(
    [
        T.StructField("label", T.StringType(), False),
        T.StructField("score", T.DoubleType(), False),
    ]
)
sentiment_udf = F.udf(predict_sentiment, SENTIMENT_SCHEMA)


def _global_candidates(
    users: DataFrame,
    seen: DataFrame,
    products: DataFrame,
    score_column: str,
    k: int,
    pool_size: int,
) -> DataFrame:
    pool = products.orderBy(F.desc(score_column), F.asc("product_id")).limit(pool_size)
    candidates = (
        users.crossJoin(F.broadcast(pool))
        .join(seen, ["user_id", "product_id"], "left_anti")
    )
    ranking = Window.partitionBy("user_id").orderBy(
        F.desc(score_column), F.asc("product_id")
    )
    return candidates.withColumn("rank", F.row_number().over(ranking)).filter(
        F.col("rank") <= k
    )


def _evaluate_strategy(
    recommendations: DataFrame,
    holdout: DataFrame,
    product_count: int,
    train_interaction_count: int,
    k: int,
    strategy: str,
) -> dict:
    ranked = recommendations.select("user_id", "product_id", "rank", "category", "review_count")
    hits = (
        holdout.alias("h")
        .join(
            ranked.alias("r"),
            (F.col("h.user_id") == F.col("r.user_id"))
            & (F.col("h.product_id") == F.col("r.product_id")),
            "left",
        )
        .select(F.col("h.user_id").alias("user_id"), F.col("r.rank").alias("hit_rank"))
    )
    summary = hits.agg(
        F.count("user_id").alias("users"),
        F.avg(F.when(F.col("hit_rank").isNotNull(), F.lit(1.0 / k)).otherwise(0.0)).alias(
            "precision_at_k"
        ),
        F.avg(F.when(F.col("hit_rank").isNotNull(), 1.0).otherwise(0.0)).alias(
            "recall_at_k"
        ),
        F.avg(F.when(F.col("hit_rank").isNotNull(), 1.0).otherwise(0.0)).alias(
            "hit_rate_at_k"
        ),
        F.avg(
            F.when(
                F.col("hit_rank").isNotNull(),
                1.0 / F.log2(F.col("hit_rank") + 1.0),
            ).otherwise(0.0)
        ).alias("ndcg_at_k"),
        F.avg(
            F.when(F.col("hit_rank").isNotNull(), 1.0 / F.col("hit_rank")).otherwise(0.0)
        ).alias("mrr_at_k"),
    ).first()
    list_stats = (
        ranked.groupBy("user_id")
        .agg(
            F.countDistinct("category").alias("distinct_categories"),
            F.count("product_id").alias("list_size"),
        )
        .agg(F.avg(F.col("distinct_categories") / F.col("list_size")).alias("diversity"))
        .first()
    )
    recommendation_stats = ranked.agg(
        F.countDistinct("product_id").alias("distinct_products"),
        F.avg(
            -F.log2(
                F.greatest(
                    F.col("review_count") / F.lit(max(train_interaction_count, 1)),
                    F.lit(1.0 / max(train_interaction_count, 1)),
                )
            )
        ).alias("novelty"),
    ).first()
    return {
        "strategy": strategy,
        "users": int(summary["users"] or 0),
        "precision_at_k": float(summary["precision_at_k"] or 0.0),
        "recall_at_k": float(summary["recall_at_k"] or 0.0),
        "hit_rate_at_k": float(summary["hit_rate_at_k"] or 0.0),
        "ndcg_at_k": float(summary["ndcg_at_k"] or 0.0),
        "mrr_at_k": float(summary["mrr_at_k"] or 0.0),
        "catalog_coverage": float(recommendation_stats["distinct_products"] or 0)
        / max(product_count, 1),
        "category_diversity": float(list_stats["diversity"] or 0.0),
        "novelty_bits": float(recommendation_stats["novelty"] or 0.0),
    }


def _store_report(report: dict) -> None:
    from pymongo import MongoClient

    output = Path(
        os.getenv("ARI_EVALUATION_REPORT", "/opt/app/data/reports/recommender_evaluation.json")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    client = MongoClient(os.getenv("ARI_MONGODB_URI", "mongodb://mongodb:27017"))
    database = client[os.getenv("ARI_MONGODB_DATABASE", "amazon_reviews")]
    database["recommendation_evaluations"].replace_one(
        {"model_version": report["model_version"]}, report, upsert=True
    )
    database["model_registry"].update_one(
        {"model_version": report["model_version"]},
        {
            "$set": {
                "offline_evaluation": report,
                "evaluated_at": report["evaluated_at"],
                "evaluation_status": "ready",
            }
        },
    )
    client.close()
    print(f"evaluation_report={output}", flush=True)


def main() -> None:
    input_pattern = os.getenv("ARI_RECOMMENDATION_INPUT", "/opt/app/data/clean/reviews_*.jsonl")
    model_version = os.getenv("ARI_RECOMMENDATION_MODEL_VERSION", "hybrid-als-nlp-v1")
    k = int(os.getenv("ARI_EVALUATION_TOP_K", "10"))
    candidate_count = max(k, int(os.getenv("ARI_EVALUATION_CANDIDATES", "50")))
    global_pool_size = max(k * 10, int(os.getenv("ARI_EVALUATION_GLOBAL_POOL", "100")))

    spark = (
        SparkSession.builder.appName("amazon-review-recommender-evaluation")
        .config("spark.sql.shuffle.partitions", os.getenv("ARI_SPARK_SHUFFLE_PARTITIONS", "32"))
        .config("spark.sql.adaptive.enabled", "true")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    raw = spark.read.json(input_pattern).select(
        "user_id",
        "product_id",
        F.col("rating").cast("double").alias("rating"),
        "title",
        "text",
        "verified_purchase",
        "category",
        F.to_timestamp("review_timestamp").alias("review_timestamp"),
        "review_id",
    )
    valid = raw.filter(
        F.col("user_id").isNotNull()
        & F.col("product_id").isNotNull()
        & F.col("review_timestamp").isNotNull()
        & F.col("rating").between(1.0, 5.0)
    )
    latest_product_interaction = Window.partitionBy("user_id", "product_id").orderBy(
        F.desc("review_timestamp"), F.desc("review_id")
    )
    deduplicated = valid.withColumn(
        "product_event_rank", F.row_number().over(latest_product_interaction)
    ).filter(F.col("product_event_rank") == 1).drop("product_event_rank")

    eligible_users = (
        deduplicated.groupBy("user_id").count().filter(F.col("count") >= 3).select("user_id")
    )
    temporal_rank = Window.partitionBy("user_id").orderBy(
        F.desc("review_timestamp"), F.desc("review_id"), F.asc("product_id")
    )
    split = deduplicated.join(eligible_users, "user_id").withColumn(
        "temporal_rank", F.row_number().over(temporal_rank)
    )
    train = split.filter(F.col("temporal_rank") > 1).drop("temporal_rank").cache()
    train_catalog = train.select("product_id").distinct()
    holdout = (
        split.filter(F.col("temporal_rank") == 1)
        .select("user_id", "product_id")
        .join(train_catalog, "product_id")
        .cache()
    )
    evaluation_users = holdout.select("user_id").distinct().cache()
    seen = train.select("user_id", "product_id").distinct().cache()

    nlp_train = (
        train.withColumn("nlp", sentiment_udf(F.concat_ws(" ", "title", "text")))
        .withColumn("sentiment_label", F.col("nlp.label"))
        .withColumn("sentiment_score", F.col("nlp.score"))
        .drop("nlp")
    )
    products = (
        nlp_train.groupBy("product_id")
        .agg(
            F.count("*").alias("review_count"),
            F.avg("rating").alias("average_rating"),
            F.avg(F.coalesce(F.col("verified_purchase").cast("double"), F.lit(0.0))).alias(
                "verified_ratio"
            ),
            F.avg("sentiment_score").alias("average_confidence"),
            F.avg(F.when(F.col("sentiment_label") == "positive", 1.0).otherwise(0.0)).alias(
                "positive_ratio"
            ),
            F.avg(F.when(F.col("sentiment_label") == "negative", 1.0).otherwise(0.0)).alias(
                "negative_ratio"
            ),
            F.first(F.coalesce("category", F.lit("unknown")), ignorenulls=True).alias("category"),
        )
        .cache()
    )
    max_reviews = products.agg(F.max("review_count")).first()[0] or 1
    popularity_denominator = max(math.log1p(max_reviews), 1.0)
    products = (
        products.withColumn(
            "confidence_adjusted_sentiment",
            F.lit(0.5)
            + ((F.col("positive_ratio") - F.col("negative_ratio")) / 2.0)
            * F.col("average_confidence"),
        )
        .withColumn(
            "quality_score",
            F.greatest(
                F.lit(0.0),
                F.least(
                    F.lit(1.0),
                    F.lit(0.65) * F.col("confidence_adjusted_sentiment")
                    + F.lit(0.25) * ((F.col("average_rating") - 1.0) / 4.0)
                    + F.lit(0.10) * F.col("verified_ratio"),
                ),
            ),
        )
        .withColumn(
            "popularity_score",
            F.log1p(F.col("review_count")) / F.lit(popularity_denominator),
        )
        .drop("confidence_adjusted_sentiment")
        .cache()
    )

    user_map = build_distributed_index(train, "user_id", "user_index").cache()
    product_map = build_distributed_index(train, "product_id", "product_index").cache()
    indexed = (
        train.groupBy("user_id", "product_id").agg(F.avg("rating").alias("rating"))
        .join(user_map, "user_id")
        .join(product_map, "product_id")
        .cache()
    )
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
    evaluation_user_indices = evaluation_users.join(user_map, "user_id")
    als_candidates = (
        model.recommendForUserSubset(
            evaluation_user_indices.select("user_index"), candidate_count
        )
        .select("user_index", F.explode("recommendations").alias("recommendation"))
        .select(
            "user_index",
            F.col("recommendation.product_index").alias("product_index"),
            F.col("recommendation.rating").cast("double").alias("als_prediction"),
        )
        .join(user_map, "user_index")
        .join(product_map, "product_index")
        .join(seen, ["user_id", "product_id"], "left_anti")
        .join(products, "product_id")
        .cache()
    )
    als_candidates = als_candidates.withColumn(
        "als_score",
        F.greatest(F.lit(0.0), F.least(F.lit(1.0), (F.col("als_prediction") - 1.0) / 4.0)),
    ).withColumn(
        "hybrid_score",
        F.lit(ALS_WEIGHT) * F.col("als_score")
        + F.lit(QUALITY_WEIGHT) * F.col("quality_score")
        + F.lit(POPULARITY_WEIGHT) * F.col("popularity_score"),
    )

    def rank_candidates(frame: DataFrame, score: str) -> DataFrame:
        ranking = Window.partitionBy("user_id").orderBy(F.desc(score), F.asc("product_id"))
        return frame.withColumn("rank", F.row_number().over(ranking)).filter(F.col("rank") <= k)

    recommendations = {
        "popularity": _global_candidates(
            evaluation_users, seen, products, "popularity_score", k, global_pool_size
        ),
        "nlp_quality": _global_candidates(
            evaluation_users, seen, products, "quality_score", k, global_pool_size
        ),
        "als": rank_candidates(als_candidates, "als_score"),
        "hybrid": rank_candidates(als_candidates, "hybrid_score"),
    }
    evaluated_users = holdout.count()
    product_count = products.count()
    train_interaction_count = train.count()
    metrics = [
        _evaluate_strategy(
            frame, holdout, product_count, train_interaction_count, k, strategy
        )
        for strategy, frame in recommendations.items()
    ]
    winner = max(metrics, key=lambda item: (item["ndcg_at_k"], item["hit_rate_at_k"]))[
        "strategy"
    ]
    report = {
        "model_version": model_version,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "protocol": "temporal_leave_last_one_out",
        "leakage_control": "ALS and NLP product quality trained only on past interactions",
        "k": k,
        "eligible_users": evaluated_users,
        "training_interactions": train_interaction_count,
        "training_products": product_count,
        "winner": winner,
        "strategies": metrics,
    }
    _store_report(report)
    print(json.dumps(report, indent=2), flush=True)
    spark.stop()


if __name__ == "__main__":
    main()

