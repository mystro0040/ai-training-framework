"""Calibration = labelled REFERENCE examples, consulted at judgement time.

This is NOT training. The model's weights never change and nothing carries over
between runs. A calibration example is a clip whose TRUE score a human already
knows, stored together with the acoustic features extracted from it. At judgement
time the screen (core/screen.py) compares a new clip's features against these
references and says "this looks like a known-bad one" — it reads the reference
each run, the way autoweb reads a site profile. Delete the file and the screen
falls back to its hard-coded defect rules alone.

One JSON file per dimension (e.g. data/calibration/prosody.json), a list of
example dicts. Human-editable on purpose.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from .. import settings


@dataclass
class CalibrationExample:
    id: str
    dimension: str                 # which dimension this example calibrates, e.g. "prosody"
    label: int                     # the KNOWN human score on the rubric scale
    features: dict[str, Any] = field(default_factory=dict)  # extracted feature profile
    transcript: str = ""
    source: str = ""               # where it came from (page/URL/clip name)
    audio: str | None = None       # optional path to the clip, for re-listening
    notes: str = ""                # why it got this label (the human's reason)

    @classmethod
    def from_dict(cls, d: dict) -> "CalibrationExample":
        return cls(
            id=str(d["id"]),
            dimension=str(d.get("dimension", "")),
            label=int(d["label"]),
            features=dict(d.get("features", {}) or {}),
            transcript=d.get("transcript", "") or "",
            source=d.get("source", "") or "",
            audio=d.get("audio"),
            notes=d.get("notes", "") or "",
        )


@dataclass
class CalibrationSet:
    dimension: str
    examples: list[CalibrationExample] = field(default_factory=list)

    def add(self, ex: CalibrationExample) -> None:
        if ex.dimension and ex.dimension != self.dimension:
            raise ValueError(f"example dimension {ex.dimension!r} != set dimension {self.dimension!r}")
        # replace by id if it already exists (idempotent re-capture)
        self.examples = [e for e in self.examples if e.id != ex.id]
        self.examples.append(ex)

    def labels(self) -> list[int]:
        return sorted({e.label for e in self.examples})

    def __len__(self) -> int:
        return len(self.examples)

    # ---- persistence --------------------------------------------------------
    @classmethod
    def path_for(cls, dimension: str, base: Path | None = None) -> Path:
        base = Path(base) if base is not None else settings.CALIBRATION_DIR
        return base / f"{dimension}.json"

    @classmethod
    def load(cls, dimension: str, base: Path | None = None) -> "CalibrationSet":
        p = cls.path_for(dimension, base)
        if not p.exists():
            return cls(dimension=dimension, examples=[])
        data = json.loads(p.read_text())
        rows = data.get("examples", data) if isinstance(data, dict) else data
        return cls(dimension=dimension,
                   examples=[CalibrationExample.from_dict(r) for r in rows])

    def save(self, base: Path | None = None) -> Path:
        p = self.path_for(self.dimension, base)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {"dimension": self.dimension,
                   "examples": [asdict(e) for e in self.examples]}
        p.write_text(json.dumps(payload, indent=2) + "\n")
        return p
