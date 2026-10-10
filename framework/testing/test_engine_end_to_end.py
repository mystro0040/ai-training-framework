import json

from ratingkit.core.item import load_items, Item
from ratingkit.core.rubric import load_rubric
from ratingkit.core.adapters import default_registry
from ratingkit.core.scoring import get_scorer, PromptScorer
from ratingkit.core.store import Store
from ratingkit.core.engine import Engine

from _wav import write_tone_silence_tone


def test_smoke_run_only_scores_agent_turns_and_discards_prosody_without_audio(tmp_path):
    items = load_items(
        __import__("pathlib").Path(__file__).resolve().parent.parent / "examples" / "sample_item.json"
    )
    rubric = load_rubric("multimodal_quality_evaluator")
    store = Store(tmp_path / "run1")
    report = Engine(rubric, default_registry(), get_scorer("smoke"), store).run(items)

    # sample_item has 2 agent turns, 2 user turns -> 2 evaluations
    assert report.evaluated == 2
    for ev in report.evaluations:
        assert ev.label == "Agent response"
        assert ev.scores["content"].score is not None          # content rated
        assert ev.scores["prosody"].discarded is True          # no audio -> honest discard
    # persisted
    assert store.results.exists()
    lines = store.results.read_text().strip().splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["label"] == "Agent response"


def test_resume_skips_already_done(tmp_path):
    items = load_items(
        __import__("pathlib").Path(__file__).resolve().parent.parent / "examples" / "sample_item.json"
    )
    rubric = load_rubric("multimodal_quality_evaluator")
    run = tmp_path / "run2"
    Engine(rubric, default_registry(), get_scorer("smoke"), Store(run)).run(items)
    # fresh store on same dir -> everything already done
    report2 = Engine(rubric, default_registry(), get_scorer("smoke"), Store(run)).run(items)
    assert report2.evaluated == 0 and report2.skipped_done == 2


def test_audio_turn_gets_prosody_scored(tmp_path):
    wav = write_tone_silence_tone(tmp_path / "a.wav")
    item = Item.from_dict({"id": "aud", "turns": [
        {"role": "agent", "label": "Agent response", "transcript": "hello", "audio": str(wav)},
    ]})
    rubric = load_rubric("multimodal_quality_evaluator")
    report = Engine(rubric, default_registry(), get_scorer("smoke"), Store(tmp_path / "r")).run([item])
    ev = report.evaluations[0]
    assert ev.scores["prosody"].discarded is False             # audio present -> prosody rated
    assert ev.scores["prosody"].score is not None


def test_prompt_scorer_renders_rubric_and_honesty(tmp_path):
    wav = write_tone_silence_tone(tmp_path / "b.wav")
    item = Item.from_dict({"id": "p", "turns": [
        {"role": "agent", "label": "Agent response", "transcript": "hi", "audio": str(wav)},
    ]})
    rubric = load_rubric("multimodal_quality_evaluator")
    scorer = PromptScorer()
    Engine(rubric, default_registry(), scorer, None).run([item])
    assert scorer.sink, "a prompt should have been rendered"
    prompt = scorer.sink[0]
    assert "Content" in prompt and "Prosody" in prompt
    assert "NOT the model hearing" in prompt            # honesty surfaced to the judge
