#!/usr/bin/env python3
"""ratingkit CLI.

Interactive by default (run with no args and it walks you through it); flags for
scripting. Run from the platform/ directory, or `pip install -e .` later.

  python3 -m ratingkit.main                      # interactive
  python3 -m ratingkit.main --list-rubrics
  python3 -m ratingkit.main --rubric multimodal_quality_evaluator \
          --items ../examples/sample_item.json --scorer smoke --run demo
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python3 ratingkit/main.py` from the platform/ dir, not just -m.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ratingkit import settings
from ratingkit.core.rubric import load_rubric, discover_rubrics
from ratingkit.core.item import load_items
from ratingkit.core.adapters import default_registry
from ratingkit.core.scoring import get_scorer
from ratingkit.core.store import Store
from ratingkit.core.engine import Engine


def _choose(prompt, options, default=None):
    for i, o in enumerate(options, 1):
        print(f"  {i}) {o}")
    raw = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    if not raw and default is not None:
        return default
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    return raw


def interactive() -> int:
    print("ratingkit — interactive run\n")
    rubrics = discover_rubrics()
    if not rubrics:
        print("No rubrics found under ratingkit/rubrics/.")
        return 1
    print("Rubrics:")
    rubric_name = _choose("Pick a rubric", rubrics, default=rubrics[0])
    items_path = input("Path to items JSON (file or dir): ").strip()
    if not items_path:
        print("No items path given.")
        return 1
    print("Scorers: smoke (offline reference) | prompt (render prompts) | "
          "screen (content + prosody defect-screen with human review queue)")
    scorer_name = _choose("Pick a scorer", ["smoke", "prompt", "screen"], default=settings.DEFAULT_SCORER)
    run_name = input("Run name [demo]: ").strip() or "demo"
    return _execute(rubric_name, items_path, scorer_name, run_name)


def _execute(rubric_name, items_path, scorer_name, run_name) -> int:
    rubric = load_rubric(rubric_name)
    items = load_items(items_path)
    scorer = get_scorer(scorer_name)
    store = Store(settings.RUNS_DIR / run_name)
    engine = Engine(rubric, default_registry(), scorer, store)
    report = engine.run(items)
    print(f"\nRubric      : {rubric.name}")
    print(f"Items       : {len(items)}")
    print(f"Evaluated   : {report.evaluated}  (skipped already-done: {report.skipped_done})")
    print(f"Discarded   : {report.discarded}")
    print(f"Held (human): {report.held}  -> `--review {run_name}` to see the queue")
    print(f"Results     : {store.results}")
    return 0


def _review(run_name: str) -> int:
    """List the dimensions reserved for a human in a run's review queue."""
    store = Store(settings.RUNS_DIR / run_name)
    reviews = store.list_reviews()
    if not reviews:
        print(f"No items reserved for human review in run {run_name!r}.")
        return 0
    print(f"{len(reviews)} dimension(s) reserved for human review in run {run_name!r}:\n")
    for r in reviews:
        print(f"- {r['item_id']}#{r['turn_index']} [{r['dimension']}]")
        print(f"    audio: {r.get('audio')}")
        scr = r.get("screen") or {}
        if scr.get("reasons"):
            print(f"    why reserved: {scr['reasons'][0]}")
        print(f"    transcript: {(r.get('transcript') or '')[:100]!r}")
    print("\nResolve one in Python:")
    print("  from ratingkit.core.store import Store; from ratingkit import settings")
    print(f"  Store(settings.RUNS_DIR / {run_name!r}).resolve_review("
          "'<item>', <turn>, 'prosody', score=<1-5>, justification='...')")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ratingkit — general-purpose rating engine")
    ap.add_argument("--list-rubrics", action="store_true")
    ap.add_argument("--rubric")
    ap.add_argument("--items")
    ap.add_argument("--scorer", default=settings.DEFAULT_SCORER)
    ap.add_argument("--run", default="demo")
    ap.add_argument("--review", metavar="RUN", help="list the human-review queue for a run")
    args = ap.parse_args(argv)

    if args.list_rubrics:
        for r in discover_rubrics():
            print(r)
        return 0
    if args.review:
        return _review(args.review)
    if args.rubric and args.items:
        return _execute(args.rubric, args.items, args.scorer, args.run)
    return interactive()


if __name__ == "__main__":
    raise SystemExit(main())
