from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from pymongo import MongoClient
from pymongo.database import Database


@asynccontextmanager
async def database_lifespan(app: FastAPI):
    client = MongoClient(
        os.getenv("ARI_MONGODB_URI", "mongodb://mongodb:27017"),
        connectTimeoutMS=5_000,
        serverSelectionTimeoutMS=5_000,
    )
    app.state.mongodb_client = client
    app.state.database = client[os.getenv("ARI_MONGODB_DATABASE", "amazon_reviews")]
    try:
        yield
    finally:
        client.close()


def get_database(request: Request) -> Database:
    return request.app.state.database
