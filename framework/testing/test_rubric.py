import pytest

from ratingkit.core.rubric import Rubric, RubricError, load_rubric, discover_rubrics


def test_multimodal_rubric_loads_and_validates():
    r = load_rubric("multimodal_quality_evaluator")
    assert r.key == "multimodal_quality_evaluator"
    assert {d.key for d in r.dimensions} == {"content", "prosody"}
    assert r.dimension("content").low == 1 and r.dimension("content").high == 5
    # Prosody must declare delivery-only discussion (separation of concerns).
    assert "delivery" in r.dimension("prosody").discuss_only.lower()


def test_example_rubric_discovered():
    names = discover_rubrics()
    assert "multimodal_quality_evaluator" in names
    assert "_example" not in names  # underscore modules are hidden


def test_bad_rubrics_rejected():
    with pytest.raises(RubricError):
        Rubric.from_dict({"key": "x", "name": "X", "dimensions": []})          # no dims
    with pytest.raises(RubricError):
        Rubric.from_dict({"key": "x", "name": "X",
                          "dimensions": [{"key": "a", "low": 5, "high": 5}]})   # empty scale
    with pytest.raises(RubricError):
        Rubric.from_dict({"key": "x", "name": "X", "dimensions": [
            {"key": "a", "low": 1, "high": 5}, {"key": "a", "low": 1, "high": 5}]})  # dup key
