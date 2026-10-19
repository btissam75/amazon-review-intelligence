import pytest

from amazon_review_intelligence.nlp.labels import rating_to_sentiment


@pytest.mark.parametrize(
    ("rating", "expected"),
    [(1, "negative"), (2, "negative"), (3, "neutral"), (4, "positive"), (5, "positive")],
)
def test_rating_to_sentiment(rating, expected):
    assert rating_to_sentiment(rating) == expected


def test_rating_to_sentiment_rejects_out_of_range():
    with pytest.raises(ValueError):
        rating_to_sentiment(0)

