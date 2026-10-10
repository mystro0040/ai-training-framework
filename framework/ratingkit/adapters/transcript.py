"""Transcript adapter — the always-available fallback. It presents the turn's
text and nothing about sound. It never claims audio is present."""

from __future__ import annotations

from ..core.adapters import EvaluatorView
from ..core.item import Turn


class TranscriptAdapter:
    name = "transcript"

    def can_handle(self, turn: Turn) -> bool:
        return True  # fallback: always handles

    def view(self, item_id: str, turn: Turn) -> EvaluatorView:
        notes = []
        if turn.audio:
            notes.append("Turn has audio, but it is being read as transcript only "
                         "(no audio adapter handled it / audio unreadable).")
        return EvaluatorView(
            item_id=item_id, turn_index=turn.index, label=turn.label,
            transcript=turn.transcript, audio_available=False, prosody=None, notes=notes,
        )
