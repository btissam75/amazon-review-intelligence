import pytest

from amazon_review_intelligence.annotation.service import cohen_kappa, consensus_label


def test_consensus_requires_all_expected_annotations():
    document = {
        "required_annotations": 2,
        "annotations": [{"annotator": "A", "label": "positive"}],
    }
    assert consensus_label(document) is None
    document["annotations"].append({"annotator": "B", "label": "positive"})
    assert consensus_label(document) == "positive"


def test_conflicting_annotations_require_adjudication():
    document = {
        "required_annotations": 2,
        "annotations": [
            {"annotator": "A", "label": "positive"},
            {"annotator": "B", "label": "negative"},
        ],
    }
    assert consensus_label(document) is None
    document["adjudicated_label"] = "neutral"
    assert consensus_label(document) == "neutral"


def test_cohen_kappa_reports_perfect_agreement():
    assert cohen_kappa([("positive", "positive"), ("negative", "negative")]) == pytest.approx(1.0)


def test_cohen_kappa_penalizes_systematic_disagreement():
    score = cohen_kappa([("positive", "negative"), ("negative", "positive")])
    assert score is not None and score < 0
