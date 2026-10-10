#!/usr/bin/env python3
"""Capture a browser/tab's audio to a WAV, the way we proved works on this box.

The machine has no sound card — audio plays into a PipeWire *null* sink whose
MONITOR still carries the digital stream. So we capture from the monitor source;
it is browser-agnostic (Firefox, Chromium, anything) and needs no CDP. CDP only
matters when something has to *drive* a page; grabbing sound does not.

Flow (each step optional via flags):
  1. (default) wait until a playback stream goes un-corked — i.e. you pressed play;
  2. capture N seconds from the monitor with ffmpeg -> 16 kHz mono 16-bit WAV;
  3. (default) trim leading/trailing silence so replay-lag doesn't pad the clip;
  4. print the WAV path and the extracted prosody FEATURES as JSON.

Requires ffmpeg + pactl (PipeWire/PulseAudio). This is environment-specific glue,
deliberately kept OUT of the portable ratingkit package (it is in examples/).

  python3 examples/capture_clip.py                       # wait-for-play, 22s, trim
  python3 examples/capture_clip.py --seconds 30 --no-wait
  python3 examples/capture_clip.py --source auto_null.monitor --out /tmp/clip.wav
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ratingkit.adapters.audio import extract_prosody_features, ProsodyError  # noqa: E402


def _playback_uncorked() -> bool:
    try:
        out = subprocess.run(["pactl", "list", "sink-inputs"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return True   # no pactl -> can't gate; proceed
    return "Corked: no" in out


def wait_for_play(timeout_sec: float) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if _playback_uncorked():
            return True
        time.sleep(0.5)
    return False


def capture(source: str, seconds: int, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-f", "pulse", "-i", source,
           "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", "-t", str(seconds), str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def trim_silence(src: Path, out: Path, threshold_db: int = 50) -> Path:
    f = (f"silenceremove=start_periods=1:start_duration=0:start_threshold=-{threshold_db}dB:"
         "detection=peak,areverse,"
         f"silenceremove=start_periods=1:start_duration=0:start_threshold=-{threshold_db}dB:"
         "detection=peak,areverse")
    subprocess.run(["ffmpeg", "-y", "-i", str(src), "-af", f,
                    "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", str(out)],
                   check=True, capture_output=True)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="", help="output WAV path (default: a temp file)")
    ap.add_argument("--seconds", type=int, default=22, help="capture length")
    ap.add_argument("--source", default="auto_null.monitor", help="pulse monitor source")
    ap.add_argument("--no-wait", action="store_true", help="don't wait for playback to start")
    ap.add_argument("--wait-timeout", type=float, default=120.0)
    ap.add_argument("--no-trim", action="store_true", help="keep leading/trailing silence")
    ap.add_argument("--transcript", default="", help="known transcript (else STT if available)")
    args = ap.parse_args(argv)

    import tempfile
    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="clip-")) / "clip.wav"

    if not args.no_wait:
        print("waiting for playback (press play)...", file=sys.stderr)
        if not wait_for_play(args.wait_timeout):
            print("WARN: playback never started; capturing anyway (may be silent)", file=sys.stderr)

    raw = out.with_name(out.stem + "_raw.wav")
    capture(args.source, args.seconds, raw)
    final = raw if args.no_trim else trim_silence(raw, out)

    try:
        feats = extract_prosody_features(final, transcript=args.transcript)
    except ProsodyError as e:
        feats = {"error": str(e)}

    print(json.dumps({"wav": str(final), "features": feats}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
