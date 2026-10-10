"""Scores, their validation against a rubric, and the pluggable Scorer interface.

The engine does NOT judge. A Scorer does. That separation is deliberate: the
same engine/validation/persistence runs whether the judge is a model, a human,
or a deterministic stub. The real training/rating task swaps in a model-backed
scorer; the offline smoke scorer lets the whole pipeline run and be tested with
no model and no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .rubric import Rubric
from .item import Turn
from .adapters import EvaluatorView


class ScoreError(ValueError):
    """An evaluation does not satisfy the rubric's structural contract."""


@dataclass
class DimensionScore:
    dimension: str
    score: int | None            # None when discarded=True or pending=True
    justification: str = ""
    discarded: bool = False      # discard for THIS dimension (genuinely unrateable)
    pending: bool = False        # reserved for a human judge (not yet scored)
    screen: dict | None = None   # optional screen result that produced this (provenance)


@dataclass
class TurnEvaluation:
    item_id: str
    turn_index: int
    label: str
    scores: dict[str, DimensionScore] = field(default_factory=dict)
    discarded: bool = False      # whole turn unusable
    notes: list[str] = field(default_factory=list)

    def validate(self, rubric: Rubric) -> None:
        """Enforce the structural contract. Semantic quality is the judge's job;
        this catches missing dimensions, out-of-range scores, and empty
        justifications — the mechanical failures a rubric can actually enforce."""
        if self.discarded:
            return
        for dim in rubric.dimensions:
            if dim.key not in self.scores:
                raise ScoreError(f"{self.item_id}#{self.turn_index}: missing dimension {dim.key!r}")
            ds = self.scores[dim.key]
            if ds.discarded:
                continue
            if ds.pending:
                # Reserved for a human — legitimately not yet scored. A pending
                # dimension must NOT carry a score (that would be a contradiction).
                if ds.score is not None:
                    raise ScoreError(f"{self.item_id}#{self.turn_index}: {dim.key!r} is pending "
                                     "but already has a score")
                continue
            if ds.score is None:
                raise ScoreError(f"{self.item_id}#{self.turn_index}: {dim.key!r} has no score and is not discarded")
            if not dim.in_scale(ds.score):
                raise ScoreError(
                    f"{self.item_id}#{self.turn_index}: {dim.key!r} score {ds.score} "
                    f"outside {dim.low}..{dim.high}"
                )
            if not ds.justification.strip():
                raise ScoreError(f"{self.item_id}#{self.turn_index}: {dim.key!r} needs a justification")

    def pending_dimensions(self) -> list[str]:
        """Dimension keys reserved for a human (awaiting a score)."""
        return [k for k, v in self.scores.items() if v.pending]

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "turn_index": self.turn_index,
            "label": self.label,
            "discarded": self.discarded,
            "notes": self.notes,
            "scores": {
                k: {"dimension": v.dimension, "score": v.score,
                    "justification": v.justification, "discarded": v.discarded,
                    "pending": v.pending, "screen": v.screen}
                for k, v in self.scores.items()
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TurnEvaluation":
        scores = {
            k: DimensionScore(
                dimension=v.get("dimension", k), score=v.get("score"),
                justification=v.get("justification", ""),
                discarded=bool(v.get("discarded", False)),
                pending=bool(v.get("pending", False)),
                screen=v.get("screen"),
            )
            for k, v in (d.get("scores", {}) or {}).items()
        }
        return cls(item_id=d["item_id"], turn_index=d["turn_index"],
                   label=d.get("label", ""), scores=scores,
                   discarded=bool(d.get("discarded", False)),
                   notes=list(d.get("notes", []) or []))


class Scorer(Protocol):
    name: str
    def score(self, turn: Turn, view: EvaluatorView, rubric: Rubric) -> TurnEvaluation:
        ...


# --- Reference scorers --------------------------------------------------------

class SmokeScorer:
    """Deterministic, offline reference scorer. NOT a real judge — it exists so
    the pipeline runs end-to-end and the tests can assert real invariants. It
    produces defensible, mechanical scores from the EvaluatorView so output
    always satisfies the rubric contract."""

    name = "smoke"

    def score(self, turn: Turn, view: EvaluatorView, rubric: Rubric) -> TurnEvaluation:
        ev = TurnEvaluation(item_id=view.item_id, turn_index=turn.index, label=turn.label)
        for dim in rubric.dimensions:
            if dim.key == "prosody" and not view.audio_available:
                # Honest: with no audio, prosody is unrateable, not guessed.
                ev.scores[dim.key] = DimensionScore(
                    dimension=dim.key, score=None, discarded=True,
                    justification="No audio available; prosody cannot be rated without the acoustic signal.",
                )
                continue
            score, why = self._mechanical(dim, turn, view)
            ev.scores[dim.key] = DimensionScore(dimension=dim.key, score=score, justification=why)
        ev.validate(rubric)
        return ev

    @staticmethod
    def _mechanical(dim, turn, view) -> tuple[int, str]:
        mid = (dim.low + dim.high + 1) // 2
        if dim.key == "content":
            text = (view.transcript or "").strip()
            if not text:
                return dim.low, "No transcript content to evaluate (smoke scorer)."
            if len(text) < 15:
                return mid, f"Very short response ({len(text)} chars); little to assess (smoke scorer)."
            return dim.high - 1, "Non-empty, substantive transcript (smoke scorer — not a real content judgement)."
        if dim.key == "prosody" and view.prosody:
            p = view.prosody
            issues = []
            if p.get("num_pauses", 0) > 4:
                issues.append(f"{p['num_pauses']} pauses")
            if p.get("energy_cv", 1.0) < 0.15:
                issues.append("low energy variation (monotone proxy)")
            if p.get("clipping_fraction", 0.0) > 0.01:
                issues.append("possible clipping artifacts")
            if not issues:
                return dim.high - 1, "Acoustic features look clean (smoke scorer — feature-based, not heard)."
            return mid, "Feature flags: " + ", ".join(issues) + " (smoke scorer — feature-based, not heard)."
        return mid, "Neutral default (smoke scorer)."


class PromptScorer:
    """Renders the per-turn evaluation PROMPT instead of scoring. The prompt is
    what a model or human judge answers. Deployments subclass this (or wrap it)
    to actually call a model and parse the reply back into a TurnEvaluation."""

    name = "prompt"

    def __init__(self, sink: list | None = None):
        self.sink = sink if sink is not None else []

    def render(self, turn: Turn, view: EvaluatorView, rubric: Rubric) -> str:
        lines = [f"# {rubric.name}", ""]
        if rubric.system_role:
            lines += ["## Role", rubric.system_role, ""]
        if rubric.directives:
            lines += ["## Core directives"] + [f"- {d}" for d in rubric.directives] + [""]
        lines += [f"## Evaluate this turn: {turn.label or turn.role} (index {turn.index})", ""]
        lines += ["Transcript (visual aid; may contain errors):", f"> {view.transcript or '(none)'}", ""]
        if view.audio_available:
            lines += [f"Audio available at: {turn.audio}"]
            if view.prosody:
                lines += ["Extracted acoustic features (NOT the model hearing — see notes):"]
                lines += [f"  - {k}: {v}" for k, v in view.prosody.items()]
        else:
            lines += ["Audio: NOT available / not ingestible as sound."]
        for n in view.notes:
            lines += [f"  note: {n}"]
        lines += ["", "## Rate each dimension"]
        for dim in rubric.dimensions:
            lines += [f"### {dim.name} ({dim.low}-{dim.high})"]
            for s in sorted(dim.anchors):
                lines += [f"  {s}: {dim.anchors[s]}"]
            if dim.justification_rules:
                lines += [f"  justification: {dim.justification_rules}"]
            if dim.discuss_only:
                lines += [f"  discuss ONLY: {dim.discuss_only}"]
        lines += ["", "## Output", "For each dimension give: " + ", ".join(rubric.output_fields or
                   ["Score", "Justification"])]
        return "\n".join(lines)

    def score(self, turn: Turn, view: EvaluatorView, rubric: Rubric) -> TurnEvaluation:
        prompt = self.render(turn, view, rubric)
        self.sink.append(prompt)
        # No judgement is made here; a model/human answers the rendered prompt.
        ev = TurnEvaluation(item_id=view.item_id, turn_index=turn.index, label=turn.label,
                            discarded=True, notes=["prompt rendered; awaiting a judge's answer"])
        return ev


class ScreenScorer:
    """Scores Content via a delegated scorer, and PROSODY via the feature defect
    screen + calibration (core/screen.py). Honest by construction:

      * a high-confidence defect ('probably_wrong') is auto-scored low, with the
        triggering features named in the justification;
      * everything else is marked PENDING — reserved for a human's ears — because
        features cannot confirm good delivery. The run does not block on it.

    The policy knob (settings.SCREEN_POLICY, overridable) chooses how much to
    reserve: 'reserve_low_confidence' (default), 'reserve_all', or 'auto_all'.
    This is the scorer the real audio task uses; Content is still the model's job
    (delegated here to the reference content scorer for the automated pipeline).
    """

    name = "screen"

    def __init__(self, calibration=None, policy: str | None = None, content_scorer: Scorer | None = None):
        from .. import settings
        self.calibration = calibration
        self.policy = policy or settings.SCREEN_POLICY
        self.content_scorer = content_scorer or SmokeScorer()

    def score(self, turn: Turn, view: EvaluatorView, rubric: Rubric) -> TurnEvaluation:
        base = self.content_scorer.score(turn, view, rubric)   # Content (and others)
        ev = TurnEvaluation(item_id=view.item_id, turn_index=turn.index, label=turn.label)
        for dim in rubric.dimensions:
            if dim.key == "prosody":
                ev.scores[dim.key] = self._prosody(dim, view)
            else:
                ev.scores[dim.key] = base.scores.get(dim.key) or DimensionScore(
                    dim.key, None, discarded=True, justification="not scored by content scorer")
        ev.notes = list(base.notes)
        ev.validate(rubric)
        return ev

    def _prosody(self, dim, view: EvaluatorView) -> DimensionScore:
        from .screen import screen_prosody
        from .calibration import CalibrationSet
        if not view.audio_available or not view.prosody:
            return DimensionScore(dim.key, None, discarded=True,
                justification="No audio available; prosody cannot be rated without the acoustic signal.")
        cal = self.calibration if self.calibration is not None else CalibrationSet.load("prosody")
        res = screen_prosody(view.prosody, cal, dimension=dim.key)
        sd = res.to_dict()
        why = "; ".join(res.reasons)

        if self.policy == "reserve_all":
            return DimensionScore(dim.key, None, pending=True, screen=sd,
                justification=f"Reserved for human ears (policy=reserve_all). {why}")

        if res.confidence == "high":   # a confident, measurable defect
            score = res.provisional_score if res.provisional_score and dim.in_scale(res.provisional_score) else dim.low
            return DimensionScore(dim.key, score, screen=sd,
                justification=f"Feature-based defect screen (NOT heard): {why}")

        if self.policy == "auto_all":  # low-confidence provisional, explicitly flagged
            mid = (dim.low + dim.high + 1) // 2
            return DimensionScore(dim.key, mid, screen=sd,
                justification=f"Low-confidence provisional from features (policy=auto_all; NOT heard): {why}")

        # default: reserve low-confidence cases for a human
        return DimensionScore(dim.key, None, pending=True, screen=sd,
            justification=f"Reserved for human ears (features cannot confirm good delivery): {why}")


def get_scorer(name: str) -> Scorer:
    name = (name or "").lower()
    if name == "smoke":
        return SmokeScorer()
    if name == "prompt":
        return PromptScorer()
    if name == "screen":
        return ScreenScorer()
    raise ValueError(f"unknown scorer {name!r} (known: smoke, prompt, screen)")
