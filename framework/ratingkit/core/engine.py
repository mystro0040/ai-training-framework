"""The engine: for each item, for each turn the rubric targets, build an
EvaluatorView via the registry, hand it to the Scorer, validate against the
rubric, and persist. Resume-aware. Knows nothing about any rubric or modality.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .rubric import Rubric
from .item import Item
from .adapters import AdapterRegistry
from .scoring import Scorer, TurnEvaluation


@dataclass
class RunReport:
    evaluated: int = 0
    skipped_done: int = 0
    discarded: int = 0
    held: int = 0                 # dimensions reserved for a human judge
    evaluations: list[TurnEvaluation] = field(default_factory=list)


class Engine:
    def __init__(self, rubric: Rubric, registry: AdapterRegistry, scorer: Scorer, store=None):
        self.rubric = rubric
        self.registry = registry
        self.scorer = scorer
        self.store = store

    def evaluate_item(self, item: Item) -> list[TurnEvaluation]:
        out: list[TurnEvaluation] = []
        for turn in item.target_turns(self.rubric.target_roles):
            adapter = self.registry.pick(turn)
            view = adapter.view(item.id, turn)
            ev = self.scorer.score(turn, view, self.rubric)
            ev.validate(self.rubric)      # structural contract; raises on violation
            out.append(ev)
        return out

    def run(self, items: list[Item]) -> RunReport:
        report = RunReport()
        for item in items:
            for turn in item.target_turns(self.rubric.target_roles):
                if self.store and self.store.is_done(item.id, turn.index):
                    report.skipped_done += 1
                    continue
                adapter = self.registry.pick(turn)
                view = adapter.view(item.id, turn)
                ev = self.scorer.score(turn, view, self.rubric)
                ev.validate(self.rubric)
                if self.store:
                    self.store.save(ev)
                    for dim_key in ev.pending_dimensions():
                        self.store.enqueue_review(
                            item_id=item.id, turn_index=turn.index, dimension=dim_key,
                            audio=turn.audio, transcript=view.transcript,
                            screen=ev.scores[dim_key].screen)
                report.evaluations.append(ev)
                report.evaluated += 1
                if ev.discarded:
                    report.discarded += 1
                report.held += len(ev.pending_dimensions())
        return report
