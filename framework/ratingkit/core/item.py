"""The thing being rated: an Item (one conversation) made of ordered Turns.

A Turn carries the transcript (a visual aid that may contain errors) and an
optional reference to its audio segment. The rubric decides which turns to
evaluate (e.g. only turns labelled "Agent response").
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable


@dataclass
class Turn:
    index: int
    role: str                     # "agent" | "user" (free-form; rubric targets by this)
    label: str = ""               # human label, e.g. "Agent response"
    transcript: str = ""          # may be wrong — audio is ground truth when present
    audio: str | None = None      # path or URL to this turn's audio segment
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict, index: int) -> "Turn":
        return cls(
            index=d.get("index", index),
            role=str(d.get("role", "")).lower(),
            label=d.get("label", ""),
            transcript=d.get("transcript", d.get("text", "")) or "",
            audio=d.get("audio"),
            meta=d.get("meta", {}) or {},
        )


@dataclass
class Item:
    id: str
    turns: list[Turn]
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        raw_turns = d.get("turns", [])
        turns = [Turn.from_dict(t, i) for i, t in enumerate(raw_turns)]
        return cls(id=str(d.get("id", "item")), turns=turns, meta=d.get("meta", {}) or {})

    def target_turns(self, roles: Iterable[str]) -> list[Turn]:
        """Turns the rubric wants evaluated, matched on role OR label (case-insensitive)."""
        wanted = {r.lower() for r in roles}
        out = []
        for t in self.turns:
            if t.role in wanted or t.label.lower() in wanted:
                out.append(t)
        return out

    def to_dict(self) -> dict:
        return {"id": self.id, "turns": [asdict(t) for t in self.turns], "meta": self.meta}


def load_items(path: str | Path) -> list[Item]:
    """Load items from a JSON file (one item, or a list of items) or a directory of such files."""
    p = Path(path)
    items: list[Item] = []
    if p.is_dir():
        for f in sorted(p.glob("*.json")):
            items.extend(load_items(f))
        return items
    data = json.loads(p.read_text())
    if isinstance(data, dict) and "items" in data:
        data = data["items"]
    if isinstance(data, dict):
        data = [data]
    for d in data:
        items.append(Item.from_dict(d))
    return items
