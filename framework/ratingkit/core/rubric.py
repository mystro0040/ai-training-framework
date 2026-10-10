"""A Rubric is DATA (like an autoweb site profile): what to rate, on what scales,
with what anchors and justification rules. The engine consumes it; it is never
hard-coded into the engine.

Rubric *profiles* live in ratingkit/rubrics/<name>.py, each exposing a module
global ``RUBRIC`` (a dict). ``load_rubric("name")`` imports it; ``Rubric.from_dict``
builds one directly (used by tests, and by anything that holds the data already).
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Any


class RubricError(ValueError):
    """A rubric profile is structurally invalid."""


@dataclass
class Dimension:
    key: str                       # "content"
    name: str                      # "Content"
    low: int                       # scale minimum (e.g. 1)
    high: int                      # scale maximum (e.g. 5)
    anchors: dict[int, str] = field(default_factory=dict)   # score -> description
    justification_rules: str = ""
    discuss_only: str = ""         # e.g. "delivery only; do not mention meaning"

    def in_scale(self, score: int) -> bool:
        return self.low <= score <= self.high


@dataclass
class Rubric:
    key: str
    name: str
    system_role: str = ""
    directives: list[str] = field(default_factory=list)
    target_roles: list[str] = field(default_factory=lambda: ["agent"])
    dimensions: list[Dimension] = field(default_factory=list)
    edge_cases: list[str] = field(default_factory=list)
    output_fields: list[str] = field(default_factory=list)

    # ---- construction -------------------------------------------------------
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Rubric":
        dims = []
        for dd in d.get("dimensions", []):
            anchors = {int(k): v for k, v in (dd.get("anchors", {}) or {}).items()}
            dims.append(Dimension(
                key=dd["key"], name=dd.get("name", dd["key"]),
                low=int(dd.get("low", 1)), high=int(dd.get("high", 5)),
                anchors=anchors,
                justification_rules=dd.get("justification_rules", ""),
                discuss_only=dd.get("discuss_only", ""),
            ))
        r = cls(
            key=d["key"], name=d.get("name", d["key"]),
            system_role=d.get("system_role", ""),
            directives=list(d.get("directives", [])),
            target_roles=list(d.get("target_roles", ["agent"])),
            dimensions=dims,
            edge_cases=list(d.get("edge_cases", [])),
            output_fields=list(d.get("output_fields", [])),
        )
        r.validate()
        return r

    def validate(self) -> None:
        if not self.key or not self.name:
            raise RubricError("rubric needs a key and a name")
        if not self.dimensions:
            raise RubricError(f"rubric {self.key!r} has no dimensions")
        seen = set()
        for dim in self.dimensions:
            if dim.key in seen:
                raise RubricError(f"duplicate dimension key {dim.key!r}")
            seen.add(dim.key)
            if dim.low >= dim.high:
                raise RubricError(f"dimension {dim.key!r} has an empty scale {dim.low}..{dim.high}")
        if not self.target_roles:
            raise RubricError(f"rubric {self.key!r} targets no roles")

    def dimension(self, key: str) -> Dimension:
        for dim in self.dimensions:
            if dim.key == key:
                return dim
        raise KeyError(key)


def load_rubric(name: str) -> Rubric:
    """Import ratingkit.rubrics.<name> and build a Rubric from its RUBRIC dict."""
    mod = importlib.import_module(f"ratingkit.rubrics.{name}")
    if not hasattr(mod, "RUBRIC"):
        raise RubricError(f"rubric module {name!r} has no RUBRIC dict")
    return Rubric.from_dict(mod.RUBRIC)


def discover_rubrics() -> list[str]:
    """Names of the rubric profiles available under ratingkit.rubrics."""
    import ratingkit.rubrics as pkg
    return sorted(
        m.name for m in pkgutil.iter_modules(pkg.__path__)
        if not m.name.startswith("_")
    )
