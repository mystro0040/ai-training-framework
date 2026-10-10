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
from pathlib import Path

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
        print(f"SRC not found: {src}"); return 2
    new, changed, unchanged = plan(src, dst)
    print(f"SRC: {src}\nDST: {dst}")
    print(f"  new={len(new)} changed={len(changed)} unchanged={len(unchanged)}")
    for rel in new:
        print(f"  + {rel}")
    for rel in changed:
        print(f"  ~ {rel}")
    if not a.apply:
        print("(dry-run — pass --apply to copy)")
        return 0
    apply(src, dst, new + changed)
    print(f"applied: {len(new) + len(changed)} file(s) copied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
