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
from amazon_review_intelligence.api.schemas import SentimentRequest, SentimentResponse
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
            {"_id": 0, "status": 1, "model_version": 1, "trained_at": 1},
        )
        return {
            "reviews": database["reviews_enriched"].estimated_document_count(),
            "products": database["product_profiles"].estimated_document_count(),
            "recommendation_users": database["user_recommendations"].estimated_document_count(),
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
        query["product_id"] = {"$regex": f"^{re.escape(search)}", "$options": "i"}
    projection = {"_id": 0}
    cursor = (
        database["product_profiles"]
        .find(query, projection)
        .sort([("quality_score", DESCENDING), ("review_count", DESCENDING)])
        .skip(offset)
        .limit(limit)
    )
    items = list(cursor)
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
                "review_timestamp": 1,
            },
        )
        .sort("review_timestamp", DESCENDING)
        .limit(review_limit)
    )
    return {"profile": profile, "reviews": reviews}


@app.get("/api/v1/recommendations/{user_id}", tags=["recommendations"])
def user_recommendations(user_id: str, database: DatabaseDependency) -> dict:
    result = database["user_recommendations"].find_one({"user_id": user_id}, {"_id": 0})
    if result:
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
        "recommendations": fallback.get("products", [])[:10],
    }


@app.get("/api/v1/recommendations", tags=["recommendations"])
def fallback_recommendations(database: DatabaseDependency) -> dict:
    fallback = database["recommendation_fallbacks"].find_one(
        {"name": "quality_popularity"}, {"_id": 0}
    )
    if not fallback:
        raise HTTPException(status_code=404, detail="Aucune recommandation disponible")
    return fallback


@app.post(
    "/api/v1/sentiment/predict",
    response_model=SentimentResponse,
    tags=["nlp"],
)
def predict(request: SentimentRequest) -> SentimentResponse:
    label, confidence = predict_sentiment(request.text)
    return SentimentResponse(label=label, confidence=confidence)
