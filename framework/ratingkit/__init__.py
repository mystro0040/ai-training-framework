"""ratingkit — a general-purpose evaluation / rating engine.

Domain-neutral core: load a batch of items, iterate the turns a rubric targets,
turn each turn into an EvaluatorView via a modality adapter, hand that to a
pluggable Scorer, validate the result against the rubric, and persist it with
resume. It knows nothing about any one rubric or modality.

Layers (mirrors the autoweb engine/modules/profiles split):
  core/      the engine + data model + validation (no rubric, no modality logic)
  adapters/  per-modality input adapters (transcript, audio, ...)
  rubrics/   rubric *profiles* — pure data, one module per rubric

Nothing here is security-specific. See ../../AGENTS.md: this is AI
training/rating work, not bug bounty or pentest.
"""

__version__ = "0.1.0"
