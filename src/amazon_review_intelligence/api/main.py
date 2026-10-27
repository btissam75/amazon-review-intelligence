from __future__ import annotations

import os
import re
import threading
import time
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pymongo import DESCENDING
from pymongo.database import Database
from pymongo.errors import PyMongoError

from amazon_review_intelligence.api.database import database_lifespan, get_database
from amazon_review_intelligence.annotation.service import (
    annotation_progress,
    next_annotation_task,
    next_conflict_task,
    save_adjudication,
    save_annotation,
)
from amazon_review_intelligence.api.schemas import (
    AdjudicationSubmission,
    AnnotationSubmission,
    AspectSentimentRequest,
    SentimentRequest,
    SentimentResponse,
)
from amazon_review_intelligence.nlp.aspects import ASPECT_MODEL_VERSION, analyze_aspects
from amazon_review_intelligence.nlp.inference import predict_sentiment


class ResultCache:
    def __init__(self) -> None:
        self._values: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get_or_create(self, key: str, ttl: int, factory):
        now = time.monotonic()
        with self._lock:
            cached = self._values.get(key)
            if cached and cached[0] > now:
                return cached[1]
        value = factory()
        with self._lock:
            self._values[key] = (now + ttl, value)
        return value


cache = ResultCache()
app = FastAPI(
    title="Amazon Review Intelligence API",
    version="1.0.0",
    description="Analytics NLP et recommandations hybrides sur un million d'avis Amazon.",
    lifespan=database_lifespan,
)
origins = [
    value.strip()
    for value in os.getenv("ARI_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    if value.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

DatabaseDependency = Annotated[Database, Depends(get_database)]

CATEGORY_NAMES = {
    "All_Beauty": "Produit beauté et soin",
    "Appliances": "Appareil pour la maison",
}


def _product_highlights(database: Database, product_ids: list[str]) -> dict[str, dict]:
    if not product_ids:
        return {}
    rows = database["reviews_enriched"].aggregate(
        [
            {"$match": {"product_id": {"$in": product_ids}}},
            {"$sort": {"product_id": 1, "helpful_vote": -1, "review_timestamp": -1}},
            {
                "$group": {
                    "_id": "$product_id",
                    "category": {"$first": "$category"},
                    "title": {"$first": "$title"},
                    "text": {"$first": "$text"},
                    "rating": {"$first": "$rating"},
                    "sentiment_label": {"$first": "$sentiment_label"},
                    "sentiment_score": {"$first": "$sentiment_score"},
                    "helpful_vote": {"$first": "$helpful_vote"},
                }
            },
        ]
    )
    return {row.pop("_id"): row for row in rows}


def _present_product(profile: dict, highlight: dict | None = None) -> dict:
    highlight = highlight or {}
    category_code = profile.get("metadata_category") or highlight.get("category")
    category = profile.get("main_category") or CATEGORY_NAMES.get(
        category_code, "Produit Amazon"
    )
    name = profile.get("name") or category
    return {
        **profile,
        "name": name,
        "category": category,
        "metadata_available": bool(profile.get("name")),
        "review_highlight": highlight or None,
    }


def _present_products(database: Database, profiles: list[dict]) -> list[dict]:
    product_ids = [row["product_id"] for row in profiles if row.get("product_id")]
    highlights = _product_highlights(database, product_ids)
    return [
        _present_product(profile, highlights.get(profile.get("product_id", "")))
        for profile in profiles
    ]


def _present_recommendations(database: Database, recommendations: list[dict]) -> list[dict]:
    product_ids = [row["product_id"] for row in recommendations if row.get("product_id")]
    profiles = {
        row["product_id"]: row
        for row in database["product_profiles"].find(
            {"product_id": {"$in": product_ids}}, {"_id": 0}
        )
    }
    highlights = _product_highlights(database, product_ids)
    presented = []
    for recommendation in recommendations:
        product_id = recommendation.get("product_id", "")
        profile = profiles.get(product_id, {"product_id": product_id})
        product = _present_product(profile, highlights.get(product_id))
        presented.append({**product, **recommendation})
    return presented


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"name": app.title, "version": app.version, "docs": "/docs"}


@app.get("/health", tags=["system"])
def health(database: DatabaseDependency) -> dict:
    try:
        database.command("ping")
        model = database["model_registry"].find_one(
            {"model_version": "hybrid-als-nlp-v1"}, {"_id": 0, "status": 1}
        )
    except PyMongoError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))
    return {
        "status": "ok",
        "mongodb": "connected",
        "recommendation_model": (model or {}).get("status", "unavailable"),
    }


@app.get("/api/v1/analytics/overview", tags=["analytics"])
def analytics_overview(database: DatabaseDependency) -> dict:
    def calculate() -> dict:
        registry = database["model_registry"].find_one(
            {"model_version": "hybrid-als-nlp-v1"},
            {
                "_id": 0,
                "status": 1,
                "model_version": 1,
                "trained_at": 1,
                "recommendation_documents": 1,
            },
        )
        return {
            "reviews": database["reviews_enriched"].count_documents({}),
            "products": database["product_profiles"].count_documents({}),
            "recommendation_users": (registry or {}).get("recommendation_documents")
            or database["user_recommendations"].count_documents({}),
            "model": registry,
        }

    return cache.get_or_create("overview", 30, calculate)


@app.get("/api/v1/analytics/sentiments", tags=["analytics"])
def sentiment_distribution(database: DatabaseDependency) -> dict:
    def calculate() -> dict:
        rows = list(
            database["reviews_enriched"].aggregate(
                [
                    {
                        "$group": {
                            "_id": "$sentiment_label",
                            "total": {"$sum": 1},
                            "average_confidence": {"$avg": "$sentiment_score"},
                        }
                    },
                    {"$sort": {"total": -1}},
                ],
                allowDiskUse=True,
            )
        )
        total = sum(row["total"] for row in rows) or 1
        return {
            "total": total,
            "items": [
                {
                    "label": row["_id"],
                    "total": row["total"],
                    "percentage": round(100 * row["total"] / total, 2),
                    "average_confidence": round(row.get("average_confidence", 0.0), 6),
                }
                for row in rows
            ],
        }

    return cache.get_or_create("sentiments", 300, calculate)


@app.get("/api/v1/analytics/details", tags=["analytics"])
def analytics_details(database: DatabaseDependency) -> dict:
    def calculate() -> dict:
        result = list(
            database["reviews_enriched"].aggregate(
                [
                    {
                        "$facet": {
                            "ratings": [
                                {"$group": {"_id": "$rating", "total": {"$sum": 1}}},
                                {"$sort": {"_id": 1}},
                            ],
                            "verification": [
                                {
                                    "$group": {
                                        "_id": None,
                                        "total": {"$sum": 1},
                                        "verified": {
                                            "$sum": {"$cond": ["$verified_purchase", 1, 0]}
                                        },
                                    }
                                }
                            ],
                            "categories": [
                                {"$group": {"_id": "$category", "total": {"$sum": 1}}},
                                {"$sort": {"total": -1}},
                                {"$limit": 8},
                            ],
                        }
                    }
                ],
                allowDiskUse=True,
            )
        )[0]
        verification = (result.get("verification") or [{}])[0]
        total = verification.get("total", 0)
        verified = verification.get("verified", 0)
        return {
            "ratings": [
                {"rating": row["_id"], "total": row["total"]}
                for row in result.get("ratings", [])
            ],
            "verified": {
                "total": total,
                "verified": verified,
                "percentage": round(100 * verified / total, 2) if total else 0.0,
            },
            "categories": [
                {"category": row["_id"] or "Sans catégorie", "total": row["total"]}
                for row in result.get("categories", [])
            ],
        }

    return cache.get_or_create("analytics-details", 300, calculate)


@app.get("/api/v1/analytics/aspects", tags=["analytics"])
def aspect_distribution(
    database: DatabaseDependency,
    product_id: Annotated[str | None, Query(max_length=100)] = None,
) -> dict:
    cache_key = f"aspect-analytics:{product_id or 'global'}"

    def calculate() -> dict:
        match: dict = {"aspect_model_version": ASPECT_MODEL_VERSION}
        if product_id:
            match["product_id"] = product_id
        rows = list(
            database["reviews_enriched"].aggregate(
                [
                    {"$match": match},
                    {"$unwind": "$aspect_sentiments"},
                    {
                        "$group": {
                            "_id": {
                                "aspect": "$aspect_sentiments.aspect",
                                "label": "$aspect_sentiments.label",
                            },
                            "reviews": {"$sum": 1},
                            "mentions": {"$sum": "$aspect_sentiments.mentions"},
                            "average_confidence": {"$avg": "$aspect_sentiments.score"},
                        }
                    },
                    {"$sort": {"mentions": -1}},
                ],
                allowDiskUse=True,
            )
        )
        grouped: dict[str, dict] = {}
        for row in rows:
            aspect = row["_id"]["aspect"]
            label = row["_id"]["label"]
            item = grouped.setdefault(
                aspect,
                {
                    "aspect": aspect,
                    "reviews": 0,
                    "mentions": 0,
                    "distribution": {"negative": 0, "neutral": 0, "positive": 0},
                    "confidence_sum": 0.0,
                },
            )
            item["reviews"] += row["reviews"]
            item["mentions"] += row["mentions"]
            item["distribution"][label] = row["reviews"]
            item["confidence_sum"] += row.get("average_confidence", 0.0) * row["reviews"]
        items = []
        for item in grouped.values():
            reviews = item["reviews"] or 1
            distribution = item["distribution"]
            items.append(
                {
                    "aspect": item["aspect"],
                    "reviews": item["reviews"],
                    "mentions": item["mentions"],
                    "distribution": distribution,
                    "positive_percentage": round(100 * distribution["positive"] / reviews, 2),
                    "negative_percentage": round(100 * distribution["negative"] / reviews, 2),
                    "average_confidence": round(item["confidence_sum"] / reviews, 6),
                }
            )
        items.sort(key=lambda item: item["mentions"], reverse=True)
        job = database["pipeline_jobs"].find_one(
            {"name": "aspect-sentiment-backfill"}, {"_id": 0}
        )
        return {
            "model_version": ASPECT_MODEL_VERSION,
            "scope": {"product_id": product_id} if product_id else {"type": "global"},
            "job": job,
            "items": items,
        }

    return cache.get_or_create(cache_key, 120, calculate)


@app.get("/api/v1/users/sample", tags=["recommendations"])
def sample_users(
    database: DatabaseDependency,
    limit: Annotated[int, Query(ge=1, le=20)] = 6,
) -> dict:
    users = list(
        database["user_recommendations"].find(
            {"model_version": "hybrid-als-nlp-v1"},
            {"_id": 0, "user_id": 1},
        ).limit(limit)
    )
    return {"items": [row["user_id"] for row in users]}


@app.get("/api/v1/annotations/progress", tags=["human-annotation"])
def human_annotation_progress(
    database: DatabaseDependency,
    annotator: Annotated[str | None, Query(min_length=2, max_length=80)] = None,
) -> dict:
    return annotation_progress(database["annotation_tasks"], annotator)


@app.get("/api/v1/annotations/next", tags=["human-annotation"])
def next_human_annotation(
    database: DatabaseDependency,
    annotator: Annotated[str, Query(min_length=2, max_length=80)],
) -> dict:
    return {"task": next_annotation_task(database["annotation_tasks"], annotator)}


@app.get("/api/v1/annotations/conflicts/next", tags=["human-annotation"])
def next_annotation_conflict(database: DatabaseDependency) -> dict:
    return {"task": next_conflict_task(database["annotation_tasks"])}


@app.post("/api/v1/annotations/{review_id}", tags=["human-annotation"])
def submit_human_annotation(
    review_id: str,
    submission: AnnotationSubmission,
    database: DatabaseDependency,
) -> dict:
    document = save_annotation(
        database["annotation_tasks"],
        review_id,
        submission.annotator.strip(),
        submission.label,
        submission.notes,
    )
    if not document:
        raise HTTPException(status_code=404, detail="Tâche d'annotation introuvable")
    labels = [row["label"] for row in document.get("annotations", [])]
    return {
        "saved": True,
        "review_id": review_id,
        "source_rating": document.get("source_rating"),
        "weak_label": document.get("weak_label"),
        "model_confidence": document.get("model_confidence"),
        "annotation_count": len(labels),
        "required_annotations": document.get("required_annotations", 1),
        "agreement": "uncertain" not in labels and len(set(labels)) <= 1,
    }


@app.post("/api/v1/annotations/{review_id}/adjudicate", tags=["human-annotation"])
def adjudicate_human_annotation(
    review_id: str,
    submission: AdjudicationSubmission,
    database: DatabaseDependency,
) -> dict:
    document = save_adjudication(
        database["annotation_tasks"],
        review_id,
        submission.adjudicator.strip(),
        submission.label,
        submission.notes,
    )
    if not document:
        raise HTTPException(status_code=404, detail="Conflit d'annotation introuvable")
    return {
        "saved": True,
        "review_id": review_id,
        "source_rating": document.get("source_rating"),
        "weak_label": document.get("weak_label"),
        "model_confidence": document.get("model_confidence"),
        "annotation_count": len(document.get("annotations", [])),
        "required_annotations": document.get("required_annotations", 2),
        "agreement": True,
    }


@app.get("/api/v1/products", tags=["products"])
def list_products(
    database: DatabaseDependency,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=100)] = None,
    min_quality: Annotated[float, Query(ge=0.0, le=1.0)] = 0.0,
) -> dict:
    query: dict = {"quality_score": {"$gte": min_quality}}
    if search:
        expression = {"$regex": re.escape(search.strip()), "$options": "i"}
        query["$or"] = [
            {"name": expression},
            {"brand": expression},
            {"main_category": expression},
            {"product_id": expression},
        ]
    projection = {"_id": 0}
    cursor = (
        database["product_profiles"]
        .find(query, projection)
        .sort([("quality_score", DESCENDING), ("review_count", DESCENDING)])
        .skip(offset)
        .limit(limit)
    )
    items = _present_products(database, list(cursor))
    return {
        "items": items,
        "pagination": {"offset": offset, "limit": limit, "returned": len(items)},
    }


@app.get("/api/v1/products/{product_id}", tags=["products"])
def product_detail(
    product_id: str,
    database: DatabaseDependency,
    review_limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    profile = database["product_profiles"].find_one({"product_id": product_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    reviews = list(
        database["reviews_enriched"]
        .find(
            {"product_id": product_id},
            {
                "_id": 0,
                "review_id": 1,
                "rating": 1,
                "title": 1,
                "text": 1,
                "sentiment_label": 1,
                "sentiment_score": 1,
                "verified_purchase": 1,
                "helpful_vote": 1,
                "category": 1,
                "review_timestamp": 1,
                "aspect_sentiments": 1,
                "aspect_model_version": 1,
            },
        )
        .sort([("helpful_vote", DESCENDING), ("review_timestamp", DESCENDING)])
        .limit(review_limit)
    )
    highlight = reviews[0] if reviews else None
    return {"profile": _present_product(profile, highlight), "reviews": reviews}


@app.get("/api/v1/recommendations/evaluation", tags=["recommendations"])
def recommendation_evaluation(database: DatabaseDependency) -> dict:
    """Expose the latest leakage-controlled offline evaluation."""

    def calculate() -> dict:
        evaluation = database["recommendation_evaluations"].find_one(
            {"model_version": "hybrid-als-nlp-v1"}, {"_id": 0}
        )
        if not evaluation:
            registry = database["model_registry"].find_one(
                {"model_version": "hybrid-als-nlp-v1"},
                {"_id": 0, "offline_evaluation": 1},
            )
            evaluation = (registry or {}).get("offline_evaluation")
        if not evaluation:
            raise HTTPException(
                status_code=404,
                detail="Evaluation hors ligne non encore exécutée",
            )
        return evaluation

    return cache.get_or_create("recommendation-evaluation", 60, calculate)


@app.get("/api/v1/nlp/evaluation", tags=["nlp"])
def nlp_human_evaluation(database: DatabaseDependency) -> dict:
    """Expose the latest sentiment evaluation against human labels."""

    def calculate() -> dict:
        evaluation = database["nlp_evaluations"].find_one(
            {"model_name": "tfidf_logistic_regression", "model_version": "1"},
            {"_id": 0},
        )
        if not evaluation:
            raise HTTPException(
                status_code=404,
                detail="Evaluation NLP humaine non encore exécutée",
            )
        return evaluation

    return cache.get_or_create("nlp-human-evaluation", 60, calculate)


@app.get("/api/v1/recommendations/{user_id}", tags=["recommendations"])
def user_recommendations(user_id: str, database: DatabaseDependency) -> dict:
    result = database["user_recommendations"].find_one({"user_id": user_id}, {"_id": 0})
    if result:
        result["recommendations"] = _present_recommendations(
            database, result.get("recommendations", [])
        )
        return {"personalized": True, **result}
    fallback = database["recommendation_fallbacks"].find_one(
        {"name": "quality_popularity"}, {"_id": 0}
    )
    if not fallback:
        raise HTTPException(status_code=404, detail="Aucune recommandation disponible")
    return {
        "personalized": False,
        "user_id": user_id,
        "model_version": "quality-popularity-fallback-v1",
        "recommendations": _present_recommendations(
            database, fallback.get("products", [])[:10]
        ),
    }


@app.get("/api/v1/recommendations", tags=["recommendations"])
def fallback_recommendations(database: DatabaseDependency) -> dict:
    fallback = database["recommendation_fallbacks"].find_one(
        {"name": "quality_popularity"}, {"_id": 0}
    )
    if not fallback:
        raise HTTPException(status_code=404, detail="Aucune recommandation disponible")
    fallback["products"] = _present_recommendations(database, fallback.get("products", []))
    return fallback


@app.post(
    "/api/v1/sentiment/predict",
    response_model=SentimentResponse,
    tags=["nlp"],
)
def predict(request: SentimentRequest) -> SentimentResponse:
    label, confidence = predict_sentiment(request.text)
    return SentimentResponse(label=label, confidence=confidence)


@app.post("/api/v1/sentiment/aspects", tags=["nlp"])
def predict_aspect_sentiments(request: AspectSentimentRequest) -> dict:
    return {
        "model_version": ASPECT_MODEL_VERSION,
        "aspects": analyze_aspects(request.text, request.title),
    }
