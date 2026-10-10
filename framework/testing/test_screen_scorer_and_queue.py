from ratingkit.core.item import Item
from ratingkit.core.rubric import load_rubric
from ratingkit.core.adapters import default_registry
from ratingkit.core.scoring import ScreenScorer, TurnEvaluation, DimensionScore, ScoreError
from ratingkit.core.calibration import CalibrationSet
from ratingkit.core.store import Store
from ratingkit.core.engine import Engine

from _wav import write_tone_silence_tone

import pytest


def _audio_item(tmp_path):
    wav = write_tone_silence_tone(tmp_path / "a.wav")
    return Item.from_dict({"id": "aud", "turns": [
        {"role": "agent", "label": "Agent response", "transcript": "hello there friend",
         "audio": str(wav)},
    ]})


def test_pending_dimension_validates_but_score_plus_pending_does_not():
    rubric = load_rubric("multimodal_quality_evaluator")
    ev = TurnEvaluation("i", 0, "Agent response", scores={
        "content": DimensionScore("content", 4, "ok"),
        "prosody": DimensionScore("prosody", None, "reserved", pending=True),
    })
    ev.validate(rubric)   # pending prosody is allowed

    bad = TurnEvaluation("i", 0, "Agent response", scores={
        "content": DimensionScore("content", 4, "ok"),
        "prosody": DimensionScore("prosody", 3, "contradiction", pending=True),
    })
    with pytest.raises(ScoreError):
        bad.validate(rubric)


def test_screen_scorer_auto_scores_a_defect(tmp_path):
    # The synth tone/silence/tone has flat energy -> monotone defect -> auto-scored,
    # NOT reserved. (High-confidence defect path.)
    rubric = load_rubric("multimodal_quality_evaluator")
    scorer = ScreenScorer(calibration=CalibrationSet(dimension="prosody"),
                          policy="reserve_low_confidence")
    report = Engine(rubric, default_registry(), scorer, Store(tmp_path / "r")).run([_audio_item(tmp_path)])
    ev = report.evaluations[0]
    assert ev.scores["prosody"].pending is False
    assert ev.scores["prosody"].score is not None
    assert report.held == 0


def test_reserve_all_holds_prosody_and_human_resolves_it(tmp_path):
    rubric = load_rubric("multimodal_quality_evaluator")
    scorer = ScreenScorer(calibration=CalibrationSet(dimension="prosody"), policy="reserve_all")
    store = Store(tmp_path / "r2")
    report = Engine(rubric, default_registry(), scorer, store).run([_audio_item(tmp_path)])

    # prosody reserved; content still scored; run did not block
    ev = report.evaluations[0]
    assert ev.scores["prosody"].pending is True
    assert ev.scores["content"].score is not None
    assert report.held == 1 and store.pending_count() == 1

    reviews = store.list_reviews()
    assert reviews[0]["dimension"] == "prosody" and reviews[0]["audio"].endswith(".wav")

    # human listens and resolves
    store.resolve_review("aud", 0, "prosody", score=4, justification="natural, warm on a re-listen")
    assert store.pending_count() == 0
    latest = store.load_results()["aud#0"]
    assert latest.scores["prosody"].score == 4 and latest.scores["prosody"].pending is False


def test_no_audio_prosody_discarded_not_pending(tmp_path):
    rubric = load_rubric("multimodal_quality_evaluator")
    item = Item.from_dict({"id": "t", "turns": [
        {"role": "agent", "label": "Agent response", "transcript": "hi"},   # no audio
    ]})
    scorer = ScreenScorer(calibration=CalibrationSet(dimension="prosody"), policy="reserve_all")
    report = Engine(rubric, default_registry(), scorer, Store(tmp_path / "r3")).run([item])
    ev = report.evaluations[0]
    assert ev.scores["prosody"].discarded is True and ev.scores["prosody"].pending is False
    assert report.held == 0
