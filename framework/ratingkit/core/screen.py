"""The feature-based DEFECT SCREEN for prosody — the honest core of "can a text
model judge how something sounds?"

It cannot hear. So this does the one thing features genuinely support, and only
that: flag clips that are *probably wrong*. The asymmetry is deliberate and is
the whole point —

  * defects (clipping, dead air, flat/monotone energy, absurd pacing) SHOW UP in
    the numbers, so a feature match to them is a HIGH-confidence "probably_wrong";
  * good, natural, warm prosody leaves no clear fingerprint in these numbers, so
    "nothing measurable is wrong" is only ever LOW confidence — it means
    "looks_clean", never "sounds good". Those clips are reserved for human ears.

Two signals combine:
  1. hard defect rules (thresholds in settings), and
  2. nearest-neighbour distance to the labelled calibration examples.

A match to a known-BAD example raises confidence of a problem; a match to a
known-GOOD example does NOT raise confidence of goodness (see above) — it only
withholds a defect flag. See core/calibration.py and ../../AGENTS.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .. import settings
from .calibration import CalibrationSet, CalibrationExample

# Numeric feature keys the distance metric uses. Lists/dicts (e.g. "pauses") and
# ids are ignored. Each is normalised by a rough natural scale so no single
# feature dominates the distance.
_FEATURE_SCALES = {
    "voiced_fraction": 1.0,
    "num_pauses": 10.0,
    "total_pause_sec": 10.0,
    "energy_cv": 1.0,
    "clipping_fraction": 0.05,
    "speaking_rate_wpm": 200.0,
}


@dataclass
class ScreenResult:
    dimension: str
    verdict: str                       # "probably_wrong" | "looks_clean" | "uncertain"
    confidence: str                    # "high" | "low"
    provisional_score: int | None      # suggested score when confident; else None
    reasons: list[str] = field(default_factory=list)
    nearest: list[dict] = field(default_factory=list)   # [{id,label,distance}]
    needs_human: bool = True

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "provisional_score": self.provisional_score,
            "reasons": self.reasons,
            "nearest": self.nearest,
            "needs_human": self.needs_human,
        }


def feature_distance(a: dict, b: dict) -> float:
    """Normalised Euclidean distance over the shared numeric feature keys."""
    terms = []
    for k, scale in _FEATURE_SCALES.items():
        if k in a and k in b and isinstance(a[k], (int, float)) and isinstance(b[k], (int, float)):
            terms.append(((a[k] - b[k]) / scale) ** 2)
    if not terms:
        return math.inf
    return math.sqrt(sum(terms) / len(terms))


def nearest_examples(features: dict, cal: CalibrationSet, k: int = 3) -> list[tuple[CalibrationExample, float]]:
    ranked = sorted(((e, feature_distance(features, e.features)) for e in cal.examples),
                    key=lambda t: t[1])
    return ranked[:k]


def prosody_defect_rules(features: dict) -> list[tuple[str, int]]:
    """Hard, interpretable defect checks. Returns (reason, suggested_score) pairs;
    an empty list means no measurable defect (NOT 'sounds good')."""
    hits: list[tuple[str, int]] = []
    clip = features.get("clipping_fraction", 0.0)
    if clip >= settings.SCREEN_CLIP_FRACTION:
        hits.append((f"clipping/distortion artifacts (clipping_fraction={clip})", 1))
    cv = features.get("energy_cv", 1.0)
    if cv < settings.SCREEN_MONOTONE_CV:
        hits.append((f"very flat energy (energy_cv={cv}) — monotone-delivery proxy", 2))
    longest = max((p.get("dur_sec", 0.0) for p in features.get("pauses", [])), default=0.0)
    if longest > settings.SCREEN_DEAD_AIR_SEC:
        hits.append((f"dead air — a {longest}s silence inside the clip", 2))
    rate = features.get("speaking_rate_wpm", 0.0)
    if rate and rate < settings.SCREEN_RATE_LOW_WPM:
        hits.append((f"draggy pacing (speaking_rate_wpm={rate})", 2))
    if rate and rate > settings.SCREEN_RATE_HIGH_WPM:
        hits.append((f"rushed pacing (speaking_rate_wpm={rate})", 2))
    return hits


def screen_prosody(features: dict, cal: CalibrationSet | None = None,
                   dimension: str = "prosody") -> ScreenResult:
    """Combine hard defect rules with calibration nearest-neighbour into a verdict.

    HIGH confidence is only ever reached for a problem. 'looks_clean' and
    'uncertain' are LOW confidence and default to needs_human=True.
    """
    cal = cal if cal is not None else CalibrationSet(dimension=dimension)
    reasons: list[str] = []
    nearest_dicts: list[dict] = []

    near = nearest_examples(features, cal) if len(cal) else []
    nearest_dicts = [{"id": e.id, "label": e.label, "distance": round(d, 3)} for e, d in near]
    close = [(e, d) for e, d in near if d <= settings.SCREEN_NEAR_DISTANCE]

    defects = prosody_defect_rules(features)

    # 1) Hard defects -> confident problem.
    if defects:
        reasons += [f"defect: {r}" for r, _ in defects]
        worst = min(s for _, s in defects)
        # a nearby known-bad example corroborates; a nearby known-good conflicts (note it).
        for e, d in close:
            if e.label <= 2:
                reasons.append(f"matches known-bad example {e.id!r} (label {e.label}, dist {round(d,3)})")
        return ScreenResult(dimension, "probably_wrong", "high", worst, reasons,
                            nearest_dicts, needs_human=False)

    # 2) No hard defect, but close to a known-BAD example -> confident problem.
    bad_close = [(e, d) for e, d in close if e.label <= 2]
    if bad_close:
        e, d = bad_close[0]
        reasons.append(f"no hard defect, but features match known-bad example "
                       f"{e.id!r} (label {e.label}, dist {round(d,3)})")
        return ScreenResult(dimension, "probably_wrong", "high", e.label, reasons,
                            nearest_dicts, needs_human=False)

    # 3) No defect, close to a known-GOOD example -> looks clean, but LOW confidence.
    good_close = [(e, d) for e, d in close if e.label >= 4]
    if good_close:
        e, d = good_close[0]
        reasons.append(f"no measurable defect; nearest example {e.id!r} is good "
                       f"(label {e.label}, dist {round(d,3)}). Features cannot confirm good "
                       "delivery — reserved for human ears.")
        return ScreenResult(dimension, "looks_clean", "low", None, reasons,
                            nearest_dicts, needs_human=True)

    # 4) Otherwise: nothing measurable to go on -> uncertain, human needed.
    reasons.append("no measurable defect and no close calibration match; "
                   "features are silent on quality — reserved for human ears.")
    return ScreenResult(dimension, "uncertain", "low", None, reasons,
                        nearest_dicts, needs_human=True)
