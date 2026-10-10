from ratingkit.core.item import Turn
from ratingkit.adapters.transcript import TranscriptAdapter
from ratingkit.adapters.audio import AudioAdapter, extract_prosody_features

from _wav import write_tone_silence_tone


def test_transcript_adapter_never_claims_audio():
    v = TranscriptAdapter().view("i1", Turn(index=0, role="agent", transcript="hi"))
    assert v.audio_available is False and v.prosody is None and v.transcript == "hi"


def test_transcript_adapter_notes_dropped_audio():
    v = TranscriptAdapter().view("i1", Turn(index=0, role="agent", transcript="hi", audio="x.wav"))
    assert any("transcript only" in n for n in v.notes)


def test_prosody_features_find_the_pause(tmp_path):
    wav = write_tone_silence_tone(tmp_path / "clip.wav", tone_sec=0.6, gap_sec=0.5)
    f = extract_prosody_features(wav, transcript="two words here")
    assert f["num_pauses"] == 1                       # exactly the middle gap
    assert 0.4 <= f["total_pause_sec"] <= 0.6         # ~0.5s
    assert f["voiced_fraction"] > 0.5                 # two tones dominate
    assert f["clipping_fraction"] < 0.001             # amp well under full scale
    assert f["speaking_rate_wpm"] > 0                 # transcript supplied
    assert f["pauses"][0]["start_sec"] > 0.3          # pause begins after the first tone


def test_audio_adapter_sets_available_and_honesty_note(tmp_path):
    wav = write_tone_silence_tone(tmp_path / "c.wav")
    v = AudioAdapter().view("i1", Turn(index=0, role="agent", transcript="hi", audio=str(wav)))
    assert v.audio_available is True and v.prosody is not None
    assert any("cannot perceive sound" in n for n in v.notes)  # honesty baked in


def test_audio_adapter_missing_file_degrades(tmp_path):
    v = AudioAdapter().view("i1", Turn(index=0, role="agent", transcript="hi",
                                       audio=str(tmp_path / "nope.wav")))
    assert v.audio_available is False
    assert any("not found" in n for n in v.notes)


def test_speaking_rate_is_over_total_time_not_voiced(tmp_path):
    # tone(0.6s) + silence(0.5s) + tone(0.6s) = 1.7s total, ~1.2s voiced.
    # The honest speaking rate counts the pause against it, so it is LOWER than
    # the articulation rate (words / voiced time only). The old bug made them equal.
    wav = write_tone_silence_tone(tmp_path / "clip.wav", tone_sec=0.6, gap_sec=0.5)
    f = extract_prosody_features(wav, transcript="one two three four")
    assert f["speaking_rate_wpm"] > 0 and f["articulation_rate_wpm"] > 0
    assert f["speaking_rate_wpm"] < f["articulation_rate_wpm"]   # pause lowers the real rate
