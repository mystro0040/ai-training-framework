"""Per-run state + results, with resume. A run writes to runs/<name>/:
  results.jsonl       one TurnEvaluation per line (append-only; latest line wins)
  state.json          {"done": ["item_id#turn_index", ...]} for resume
  review_queue.json   dimensions reserved for a human judge (not yet scored)

results.jsonl is append-only: an item re-scored (e.g. a human resolving a pending
prosody dimension) appends a NEW line, and load_results() keeps the latest per
key. That keeps a full audit trail while the current view stays correct.
"""

from __future__ import annotations

import json
from pathlib import Path

from .scoring import TurnEvaluation, DimensionScore


class Store:
    def __init__(self, run_dir: str | Path):
        self.dir = Path(run_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.results = self.dir / "results.jsonl"
        self.state = self.dir / "state.json"
        self.queue_path = self.dir / "review_queue.json"
        self._done: set[str] = set()
        if self.state.exists():
            try:
                self._done = set(json.loads(self.state.read_text()).get("done", []))
            except (json.JSONDecodeError, OSError):
                self._done = set()
        self._queue: dict[str, dict] = {}
        if self.queue_path.exists():
            try:
                self._queue = json.loads(self.queue_path.read_text())
            except (json.JSONDecodeError, OSError):
                self._queue = {}

    @staticmethod
    def _key(item_id: str, turn_index: int) -> str:
        return f"{item_id}#{turn_index}"

    @staticmethod
    def _qkey(item_id: str, turn_index: int, dimension: str) -> str:
        return f"{item_id}#{turn_index}:{dimension}"

    def is_done(self, item_id: str, turn_index: int) -> bool:
        return self._key(item_id, turn_index) in self._done

    def save(self, ev: TurnEvaluation) -> None:
        with self.results.open("a") as fh:
            fh.write(json.dumps(ev.to_dict()) + "\n")
        self._done.add(self._key(ev.item_id, ev.turn_index))
        self.state.write_text(json.dumps({"done": sorted(self._done)}, indent=1))

    def count(self) -> int:
        return len(self._done)

    # ---- review queue (human-reserved dimensions) ---------------------------
    def _flush_queue(self) -> None:
        self.queue_path.write_text(json.dumps(self._queue, indent=2) + "\n")

    def enqueue_review(self, *, item_id: str, turn_index: int, dimension: str,
                       audio: str | None, transcript: str, screen: dict | None) -> None:
        """Reserve one dimension of one turn for a human judge. Carries the clip
        path so it can be re-listened, and the ambiguous spans (pauses) to focus on."""
        spans = (screen or {}).get("nearest")  # provenance; pauses live under features
        self._queue[self._qkey(item_id, turn_index, dimension)] = {
            "item_id": item_id, "turn_index": turn_index, "dimension": dimension,
            "audio": audio, "transcript": transcript, "screen": screen,
        }
        self._flush_queue()

    def list_reviews(self) -> list[dict]:
        return list(self._queue.values())

    def pending_count(self) -> int:
        return len(self._queue)

    def load_results(self) -> dict[str, TurnEvaluation]:
        """Latest-wins map of item_id#turn_index -> TurnEvaluation."""
        out: dict[str, TurnEvaluation] = {}
        if not self.results.exists():
            return out
        for line in self.results.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            ev = TurnEvaluation.from_dict(json.loads(line))
            out[self._key(ev.item_id, ev.turn_index)] = ev
        return out

    def resolve_review(self, item_id: str, turn_index: int, dimension: str,
                       score: int, justification: str) -> TurnEvaluation:
        """A human gives the real score for a reserved dimension. Clears pending,
        appends the updated evaluation, and drops the queue entry."""
        qk = self._qkey(item_id, turn_index, dimension)
        if qk not in self._queue:
            raise KeyError(f"no pending review for {qk}")
        results = self.load_results()
        ev = results.get(self._key(item_id, turn_index))
        if ev is None:
            raise KeyError(f"no evaluation on record for {self._key(item_id, turn_index)}")
        prev = ev.scores.get(dimension)
        ev.scores[dimension] = DimensionScore(
            dimension=dimension, score=score, justification=justification,
            pending=False, screen=(prev.screen if prev else None))
        ev.notes = list(ev.notes) + [f"{dimension} resolved by human: score {score}"]
        with self.results.open("a") as fh:
            fh.write(json.dumps(ev.to_dict()) + "\n")
        del self._queue[qk]
        self._flush_queue()
        return ev
