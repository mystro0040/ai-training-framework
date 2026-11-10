#!/usr/bin/env python3
"""Propagate the AI-training framework ENGINE from the PRIVATE working copy to the
PUBLIC master (private -> public by default). Copies everything under `framework/`
except caches and VCS metadata. The engine is general-purpose and carries NO
client/assignment data (that lives in the data repo), so nothing is stripped —
the split is structural: corporate data never enters `framework/`.

  python3 propagate_framework.py            # dry-run: show what would change
  python3 propagate_framework.py --apply    # copy private framework/ -> public framework/
  python3 propagate_framework.py --apply --src <dir> --dst <dir>   # override either side

Defaults point at the CONSOLIDATED locations (not a retired path):
  SRC = ~/Workspace/ai-training/ai_training_workspace/framework
  DST = ~/Workspace/Production_Ready/public/General_Development/ai-training-framework/framework
"""
from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

# Shared house CLI look — themeable, revert with CLI_STYLE=plain (see its ADOPTING.md).
# FAIL-OPEN: vendored clistyle lives in framework/ (this file is framework/utilities/…),
# so put framework/ on the path and import it there; if it is missing S stays None and
# callers fall back to plain output. Default theme = unchanged text, colour only on a TTY.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    import clistyle
    S = clistyle.styler()
except Exception:
    S = None


def _p(text, role):
    """Colour `text` for `role`; identical text when there is no styler or colour is off."""
    return S.paint(text, role) if S else text


HOME = Path.home()
DEFAULT_SRC = HOME / "Workspace/ai-training/ai_training_workspace/framework"
DEFAULT_DST = (HOME / "Workspace/Production_Ready/public/General_Development"
               / "ai-training-framework/framework")

EXCLUDE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".git"}
EXCLUDE_SUFFIXES = {".pyc"}


def _iter_files(root: Path):
    for p in root.rglob("*"):
        if any(part in EXCLUDE_DIR_NAMES for part in p.relative_to(root).parts):
            continue
        if p.is_file() and p.suffix not in EXCLUDE_SUFFIXES:
            yield p


def plan(src: Path, dst: Path):
    """Return (new, changed, unchanged) relative paths."""
    new, changed, unchanged = [], [], []
    for sp in _iter_files(src):
        rel = sp.relative_to(src)
        dp = dst / rel
        if not dp.exists():
            new.append(rel)
        elif not filecmp.cmp(sp, dp, shallow=False):
            changed.append(rel)
        else:
            unchanged.append(rel)
    return new, changed, unchanged


def apply(src: Path, dst: Path, rels):
    for rel in rels:
        dp = dst / rel
        dp.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / rel, dp)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--dst", default=str(DEFAULT_DST))
    ap.add_argument("--apply", action="store_true", help="actually copy (default: dry-run)")
    a = ap.parse_args(argv)
    src, dst = Path(a.src).expanduser(), Path(a.dst).expanduser()
    if not src.is_dir():
        print(_p("SRC not found:", "err") + f" {src}"); return 2
    new, changed, unchanged = plan(src, dst)
    print(_p("SRC", "bold") + f": {src}\n" + _p("DST", "bold") + f": {dst}")
    print("  " + _p(f"new={len(new)} changed={len(changed)} unchanged={len(unchanged)}", "accent"))
    for rel in new:
        print("  " + _p("+", "ok") + f" {rel}")
    for rel in changed:
        print("  " + _p("~", "warn") + f" {rel}")
    if not a.apply:
        print(_p("(dry-run — pass --apply to copy)", "dim"))
        return 0
    apply(src, dst, new + changed)
    print(_p("applied:", "ok") + f" {len(new) + len(changed)} file(s) copied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
