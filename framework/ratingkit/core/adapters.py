"""Input / modality adapters: turn a Turn into an EvaluatorView — the structured
material a judge reasons over. One adapter per modality (transcript, audio, ...),
like autoweb modules. The engine picks the most specific adapter that can handle
a turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .item import Turn


@dataclass
class EvaluatorView:
    """What the judge actually sees for one turn."""
    item_id: str
    turn_index: int
    label: str
    transcript: str = ""
    audio_available: bool = False
    prosody: dict | None = None          # extracted acoustic FEATURES, not perception
    notes: list[str] = field(default_factory=list)


class Adapter(Protocol):
    name: str
    def can_handle(self, turn: Turn) -> bool: ...
    def view(self, item_id: str, turn: Turn) -> EvaluatorView: ...


class AdapterRegistry:
    """Holds adapters in priority order; the first that can_handle wins. Register
    specific adapters (audio) before the fallback (transcript)."""

    def __init__(self):
        self._adapters: list[Adapter] = []

    def register(self, adapter: Adapter) -> None:
        self._adapters.append(adapter)

    def pick(self, turn: Turn) -> Adapter:
        for a in self._adapters:
            if a.can_handle(turn):
                return a
        raise LookupError(f"no adapter can handle turn {turn.index}")

    def __len__(self):
        return len(self._adapters)


def default_registry() -> AdapterRegistry:
    """Audio first (specific), transcript last (always handles)."""
    from ..adapters.audio import AudioAdapter
    from ..adapters.transcript import TranscriptAdapter
    reg = AdapterRegistry()
    reg.register(AudioAdapter())
    reg.register(TranscriptAdapter())
    return reg
