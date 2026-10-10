from ratingkit.core.calibration import CalibrationExample, CalibrationSet


def test_add_save_load_roundtrip(tmp_path):
    cs = CalibrationSet(dimension="prosody")
    cs.add(CalibrationExample(id="good1", dimension="prosody", label=5,
                              features={"energy_cv": 0.4, "clipping_fraction": 0.0},
                              notes="natural, warm"))
    cs.add(CalibrationExample(id="bad1", dimension="prosody", label=1,
                              features={"energy_cv": 0.4, "clipping_fraction": 0.2},
                              notes="heavy distortion"))
    cs.save(base=tmp_path)

    loaded = CalibrationSet.load("prosody", base=tmp_path)
    assert len(loaded) == 2
    assert loaded.labels() == [1, 5]
    assert {e.id for e in loaded.examples} == {"good1", "bad1"}


def test_add_is_idempotent_by_id():
    cs = CalibrationSet(dimension="prosody")
    cs.add(CalibrationExample(id="x", dimension="prosody", label=3, features={"energy_cv": 0.2}))
    cs.add(CalibrationExample(id="x", dimension="prosody", label=4, features={"energy_cv": 0.3}))
    assert len(cs) == 1 and cs.examples[0].label == 4   # replaced, not duplicated


def test_mismatched_dimension_rejected():
    cs = CalibrationSet(dimension="prosody")
    try:
        cs.add(CalibrationExample(id="y", dimension="content", label=3))
        assert False, "should have raised"
    except ValueError:
        pass


def test_load_missing_returns_empty(tmp_path):
    cs = CalibrationSet.load("prosody", base=tmp_path / "nope")
    assert len(cs) == 0 and cs.dimension == "prosody"
