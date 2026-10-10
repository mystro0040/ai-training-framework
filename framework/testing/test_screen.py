from ratingkit.core.calibration import CalibrationExample, CalibrationSet
from ratingkit.core.screen import screen_prosody, feature_distance

# A feature profile with NO hard defect: varied energy, no clipping, normal rate,
# no long pause. The screen must not invent a defect from this.
CLEAN = {"voiced_fraction": 0.55, "num_pauses": 3, "total_pause_sec": 1.5,
         "energy_cv": 0.40, "clipping_fraction": 0.0, "speaking_rate_wpm": 150.0,
         "pauses": [{"start_sec": 1.0, "dur_sec": 0.4}]}


def test_clipping_is_confident_wrong():
    f = dict(CLEAN, clipping_fraction=0.2)
    r = screen_prosody(f)
    assert r.verdict == "probably_wrong" and r.confidence == "high"
    assert r.needs_human is False and r.provisional_score == 1


def test_monotone_is_confident_wrong():
    f = dict(CLEAN, energy_cv=0.05)
    r = screen_prosody(f)
    assert r.verdict == "probably_wrong" and r.confidence == "high"
    assert any("monotone" in x for x in r.reasons)


def test_dead_air_is_confident_wrong():
    f = dict(CLEAN, pauses=[{"start_sec": 2.0, "dur_sec": 3.5}])
    r = screen_prosody(f)
    assert r.verdict == "probably_wrong" and r.confidence == "high"
    assert any("dead air" in x for x in r.reasons)


def test_clean_with_no_calibration_is_uncertain_and_needs_human():
    r = screen_prosody(CLEAN)   # empty calibration
    assert r.verdict == "uncertain" and r.confidence == "low"
    assert r.needs_human is True and r.provisional_score is None


def test_close_to_known_bad_flags_without_a_hard_defect():
    cal = CalibrationSet(dimension="prosody")
    cal.add(CalibrationExample(id="bad", dimension="prosody", label=2, features=dict(CLEAN)))
    r = screen_prosody(CLEAN, cal)   # identical features, label 2
    assert r.verdict == "probably_wrong" and r.confidence == "high"
    assert r.provisional_score == 2


def test_close_to_known_good_is_only_low_confidence():
    # THE asymmetry: a match to a good example never yields high confidence.
    cal = CalibrationSet(dimension="prosody")
    cal.add(CalibrationExample(id="good", dimension="prosody", label=5, features=dict(CLEAN)))
    r = screen_prosody(CLEAN, cal)
    assert r.verdict == "looks_clean" and r.confidence == "low"
    assert r.needs_human is True and r.provisional_score is None


def test_distance_zero_for_identical_and_grows_with_difference():
    assert feature_distance(CLEAN, CLEAN) == 0.0
    far = dict(CLEAN, energy_cv=0.0, clipping_fraction=0.05)
    assert feature_distance(CLEAN, far) > 0.0
