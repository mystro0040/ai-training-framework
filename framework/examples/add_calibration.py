#!/usr/bin/env python3
"""Record a labelled calibration example: a clip whose TRUE prosody score a human
already knows, stored with its extracted features so the screen can compare new
clips against it. This is reference data, not training — see core/calibration.py.

  # from an existing WAV, non-interactive:
  python3 examples/add_calibration.py --file clip.wav --label 2 \
      --id intro_robotic --source "examples page #3" --notes "flat, robotic throughout"

  # interactive (prompts for label/notes):
  python3 examples/add_calibration.py --file clip.wav
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ratingkit.adapters.audio import extract_prosody_features, _maybe_transcribe  # noqa: E402
from ratingkit.core.calibration import CalibrationExample, CalibrationSet  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", required=True, help="WAV clip to record")
    ap.add_argument("--label", type=int, help="known prosody score (1-5)")
    ap.add_argument("--id", default="", help="example id (default: file stem)")
    ap.add_argument("--dimension", default="prosody")
    ap.add_argument("--source", default="", help="where it came from")
    ap.add_argument("--notes", default="", help="why it got this label")
    ap.add_argument("--transcript", default="")
    ap.add_argument("--base", default="", help="calibration dir (default: settings.CALIBRATION_DIR)")
    args = ap.parse_args(argv)

    wav = Path(args.file)
    if not wav.exists():
        sys.exit(f"no such file: {wav}")
    transcript = args.transcript
    if not transcript:                       # auto-transcribe if whisper is available
        transcript, _ = _maybe_transcribe(str(wav))
    feats = extract_prosody_features(wav, transcript=transcript)

    label = args.label
    notes = args.notes
    if label is None:
        print("Extracted features:")
        for k, v in feats.items():
            if k != "pauses":
                print(f"  {k}: {v}")
        raw = input("Known prosody score 1-5: ").strip()
        label = int(raw)
        if not notes:
            notes = input("Why (one line): ").strip()
    if not (1 <= label <= 5):
        sys.exit(f"label {label} out of range 1-5")

    ex_id = args.id or wav.stem
    base = Path(args.base) if args.base else None
    cs = CalibrationSet.load(args.dimension, base=base)
    cs.add(CalibrationExample(id=ex_id, dimension=args.dimension, label=label,
                              features=feats, transcript=transcript,
                              source=args.source, audio=str(wav.resolve()), notes=notes))
    path = cs.save(base=base)
    print(f"recorded {ex_id!r} (label {label}) -> {path}  [{len(cs)} example(s) total]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
