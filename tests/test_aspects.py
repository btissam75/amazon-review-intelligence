from amazon_review_intelligence.nlp.aspects import analyze_aspects, detected_aspects


def fake_predictor(text: str) -> tuple[str, float]:
    lowered = text.lower()
    return ("negative", 0.9) if "damaged" in lowered or "late" in lowered else ("positive", 0.8)


def test_detects_multiple_business_aspects():
    assert detected_aspects("The packaging was damaged during delivery") == [
        "delivery",
        "packaging",
    ]


def test_analyzes_each_aspect_from_its_sentence():
    result = analyze_aspects(
        "Great quality and easy to use. The packaging was damaged and delivery was late.",
        predictor=fake_predictor,
    )
    indexed = {item["aspect"]: item for item in result}
    assert indexed["quality"]["label"] == "positive"
    assert indexed["usability"]["label"] == "positive"
    assert indexed["packaging"]["label"] == "negative"
    assert indexed["delivery"]["label"] == "negative"
    assert indexed["delivery"]["mentions"] == 1
