import pytest

from ratingkit.core.item import Item
from ratingkit.core.rubric import load_rubric
from ratingkit.core.scoring import TurnEvaluation, DimensionScore, ScoreError


def _item():
    return Item.from_dict({"id": "i1", "turns": [
        {"role": "user", "label": "User turn", "transcript": "hi"},
        {"role": "agent", "label": "Agent response", "transcript": "hello there"},
    ]})


def test_target_turns_match_role_or_label():
    it = _item()
    # by role
    assert [t.index for t in it.target_turns(["agent"])] == [1]
    # by label (case-insensitive)
    assert [t.index for t in it.target_turns(["agent response"])] == [1]
    # user turns excluded
    assert all(t.role == "agent" for t in it.target_turns(["agent"]))


def test_evaluation_validation_contract():
    rubric = load_rubric("multimodal_quality_evaluator")
    good = TurnEvaluation(item_id="i1", turn_index=1, label="Agent response", scores={
        "content": DimensionScore("content", 4, "quoted the user and adapted"),
        "prosody": DimensionScore("prosody", None, "no audio", discarded=True),
    })
    good.validate(rubric)  # should not raise

    # missing a required dimension
    with pytest.raises(ScoreError):
        TurnEvaluation("i1", 1, "Agent response",
                       scores={"content": DimensionScore("content", 4, "ok")}).validate(rubric)

    # score out of range
    with pytest.raises(ScoreError):
        TurnEvaluation("i1", 1, "Agent response", scores={
            "content": DimensionScore("content", 9, "ok"),
            "prosody": DimensionScore("prosody", None, "n/a", discarded=True),
        }).validate(rubric)

    # empty justification
    with pytest.raises(ScoreError):
        TurnEvaluation("i1", 1, "Agent response", scores={
            "content": DimensionScore("content", 4, "   "),
            "prosody": DimensionScore("prosody", None, "n/a", discarded=True),
        }).validate(rubric)
