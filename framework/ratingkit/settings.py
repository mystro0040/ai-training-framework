"""Defaults for ratingkit. One place to change behaviour; override per-run via CLI."""

import os
from pathlib import Path

# Where runs (campaign state + results) are written.
RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"

# Default scorer when none is chosen. "smoke" is a deterministic, offline
# reference scorer for testing the pipeline; "prompt" renders the per-turn
# evaluation prompt for a model/human to answer. The real task swaps in a
# model-backed scorer (see core/scoring.py).
DEFAULT_SCORER = "smoke"

# --- Audio prosody feature extraction (adapters/audio.py) ---------------------
# These govern the stdlib WAV analysis. They are feature-extraction knobs, not
# a claim that the model hears audio — see adapters/audio.py.
PROSODY_WINDOW_MS = 25          # analysis window
PROSODY_SILENCE_FRACTION = 0.15 # window RMS below this fraction of peak => silence
PROSODY_MIN_PAUSE_MS = 250      # a run of silence this long counts as a pause

# --- Prosody defect screen (core/screen.py) -----------------------------------
# A feature-based DEFECT SCREEN: it can confidently flag "probably wrong"; it
# CANNOT confidently bless "sounds good" (quality lives in the sound, which a
# text model never receives). See core/screen.py and ../../AGENTS.md.
#
# Hard-defect thresholds — crossing one is a high-confidence "probably_wrong":
SCREEN_CLIP_FRACTION = 0.005    # clipping_fraction above this => artifacts/distortion
SCREEN_MONOTONE_CV = 0.12       # energy_cv below this => flat/monotone delivery proxy
SCREEN_DEAD_AIR_SEC = 2.0       # any single pause longer than this => dead air
SCREEN_RATE_LOW_WPM = 90        # speaking_rate below => draggy/unnatural pacing
SCREEN_RATE_HIGH_WPM = 240      # speaking_rate above => rushed/unnatural pacing
# Nearest-neighbour calibration match: features within this normalised distance
# of a labelled example are "close" to it.
SCREEN_NEAR_DISTANCE = 1.0

# Prosody-screen policy for the ScreenScorer: what to do with the SCALE:
#   "reserve_low_confidence" — auto-score only high-confidence defects; reserve
#                              everything else for a human (default, honest).
#   "reserve_all"            — never auto-score prosody; always reserve for ears.
#   "auto_all"               — auto-score every item from features (low fidelity;
#                              clean/uncertain get a conservative provisional).
SCREEN_POLICY = "reserve_low_confidence"

# --- Calibration + human-review queue -----------------------------------------
# Labelled reference examples (feature profile -> known score) the screen compares
# against. One JSON file per dimension under this dir.
# The public framework ships with NO calibration data (clean engine). Point this
# at a data repo's calibration dir via RATINGKIT_CALIBRATION_DIR; the default is a
# framework-local (usually empty) dir, which CalibrationSet.load handles gracefully.
CALIBRATION_DIR = Path(os.environ.get("RATINGKIT_CALIBRATION_DIR")
                       or Path(__file__).resolve().parent.parent / "data" / "calibration")
