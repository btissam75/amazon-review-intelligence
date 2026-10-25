from fastapi.testclient import TestClient

from amazon_review_intelligence.api import main as api_main
from amazon_review_intelligence.api.database import get_database


class FakeCollection:
    def __init__(self, document=None):
        self.document = document

    def find_one(self, *_args, **_kwargs):
        return self.document


class FakeDatabase:
    def __init__(self):
        self.collections = {
            "model_registry": FakeCollection({"status": "ready"}),
        }

    def command(self, name):
        assert name == "ping"
        return {"ok": 1}

    def __getitem__(self, name):
        return self.collections[name]


def test_health_reports_ready_model():
    api_main.app.dependency_overrides[get_database] = FakeDatabase
    try:
        client = TestClient(api_main.app)
        response = client.get("/health")
    finally:
        api_main.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mongodb": "connected",
        "recommendation_model": "ready",
    }


def test_sentiment_prediction(monkeypatch):
    monkeypatch.setattr(api_main, "predict_sentiment", lambda text: ("positive", 0.91))
    client = TestClient(api_main.app)
    response = client.post("/api/v1/sentiment/predict", json={"text": "Très bon produit"})
    assert response.status_code == 200
    assert response.json() == {"label": "positive", "confidence": 0.91}


def test_sentiment_prediction_rejects_empty_text():
    client = TestClient(api_main.app)
    response = client.post("/api/v1/sentiment/predict", json={"text": ""})
    assert response.status_code == 422


def test_recommendation_evaluation_is_exposed_before_dynamic_user_route():
    report = {
        "model_version": "hybrid-als-nlp-v1",
        "protocol": "temporal_leave_last_one_out",
        "winner": "hybrid",
        "strategies": [],
    }

    class EvaluationDatabase:
        def __getitem__(self, name):
            documents = {
                "recommendation_evaluations": report,
                "model_registry": None,
            }
            return FakeCollection(documents[name])

    api_main.cache._values.clear()
    api_main.app.dependency_overrides[get_database] = EvaluationDatabase
    try:
        response = TestClient(api_main.app).get("/api/v1/recommendations/evaluation")
    finally:
        api_main.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["winner"] == "hybrid"
