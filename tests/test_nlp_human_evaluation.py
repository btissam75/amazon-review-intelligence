import pytest

from amazon_review_intelligence.nlp.evaluate_human import build_evaluation_report


def test_human_evaluation_computes_macro_metrics_and_errors():
    records = [
        {"review_id": "1", "text": "bad", "label": "negative", "weak_label": "negative"},
        {"review_id": "2", "text": "okay", "label": "neutral", "weak_label": "positive"},
        {"review_id": "3", "text": "great", "label": "positive", "weak_label": "positive"},
    ]
    report = build_evaluation_report(
        records,
        ["negative", "positive", "positive"],
        [0.9, 0.8, 0.95],
        model_name="test-model",
        model_version="test",
    )
    assert report["dataset"]["size"] == 3
    assert report["metrics"]["accuracy"] == pytest.approx(2 / 3)
    assert report["metrics"]["macro_f1"] < 1
    assert report["error_count"] == 1
    assert report["weak_label_human_agreement"] == pytest.approx(2 / 3)
    assert report["confusion_matrix"]["values"][1] == [0, 0, 1]


def test_human_evaluation_rejects_unaligned_inputs():
    with pytest.raises(ValueError):
        build_evaluation_report(
            [{"label": "positive", "text": "great"}],
            [],
            [],
            model_name="test-model",
            model_version="test",
        )
