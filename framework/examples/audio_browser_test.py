#!/usr/bin/env python3
"""Audio feasibility test — the decisive "can the model actually hear?" check.

What it does:
  1. Sources a short real-world audio clip — from a YouTube URL (yt-dlp + ffmpeg)
     or a local file you pass — and normalises it to 16 kHz mono 16-bit WAV.
  2. Runs it through ratingkit's AudioAdapter: extracts prosody FEATURES and builds
     the EvaluatorView a judge would see.
  3. Prints the features AND the verdict in plain terms.

The point it proves: even with a real clip in hand, a text LLM receives extracted
FEATURES + (optionally) a transcript — never the sound itself. That gap is the whole
audio-feasibility question. See ../AGENTS.md and ../assessment/.

Requirements (install if missing — operator-approved):
  - ffmpeg            (sudo apt-get install -y ffmpeg)   # REQUIRED to make a WAV
  - yt-dlp            (already present at /usr/bin/yt-dlp) # only for --url mode

Usage:
  python3 examples/audio_browser_test.py --url "https://www.youtube.com/watch?v=..." --seconds 20
  python3 examples/audio_browser_test.py --file /path/to/clip.wav

Browser-attach alternative (matches "open the browser and play a video"): launch
Chromium via the `browser-attach` skill, play the video in a visible tab, and capture
the system-audio monitor with ffmpeg (`ffmpeg -f pulse -i default out.wav`). The result
is the same WAV this script analyses — CDP drives the page but does not hand over audio,
so an external capture is always the step that produces sound-as-data.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ratingkit.core.item import Turn
from ratingkit.adapters.audio import AudioAdapter


def _need(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        sys.exit(f"MISSING: {tool!r} is not installed. Install it and re-run "
                 f"(ffmpeg: `sudo apt-get install -y ffmpeg`).")
    return path


def fetch_youtube_wav(url: str, seconds: int, out: Path) -> Path:
    _need("yt-dlp"); _need("ffmpeg")
    cmd = [
        "yt-dlp", "-x", "--audio-format", "wav",
        "--postprocessor-args", "ffmpeg:-ar 16000 -ac 1",
        "--download-sections", f"*0-{seconds}",
        "--force-keyframes-at-cuts",
        "-o", str(out.with_suffix(".%(ext)s")), url,
    ]
    print("running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    wav = out.with_suffix(".wav")
    if not wav.exists():
        sys.exit("yt-dlp did not produce a .wav (check ffmpeg).")
    return wav


def normalise_to_wav(src: Path, out: Path) -> Path:
    _need("ffmpeg")
    subprocess.run(["ffmpeg", "-y", "-i", str(src), "-ar", "16000", "-ac", "1",
                    "-sample_fmt", "s16", str(out)], check=True)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--url", help="YouTube (or yt-dlp-supported) URL")
    g.add_argument("--file", help="local audio file (any format ffmpeg reads)")
    ap.add_argument("--seconds", type=int, default=20, help="clip length for --url")
    ap.add_argument("--transcript", default="", help="optional known transcript")
    args = ap.parse_args(argv)

    tmp = Path(tempfile.mkdtemp(prefix="audiotest-"))
    if args.url:
        wav = fetch_youtube_wav(args.url, args.seconds, tmp / "clip")
    else:
        src = Path(args.file)
        wav = src if src.suffix.lower() == ".wav" else normalise_to_wav(src, tmp / "clip.wav")

    turn = Turn(index=0, role="agent", label="Agent response",
                transcript=args.transcript, audio=str(wav))
    view = AudioAdapter().view("audio-test", turn)

    print("\n================ EvaluatorView (what a judge receives) ================")
    print(f"audio_available : {view.audio_available}")
    print(f"transcript      : {view.transcript!r}")
    print("prosody features:")
    for k, v in (view.prosody or {}).items():
        print(f"    {k}: {v}")
    print("notes:")
    for n in view.notes:
        print(f"    - {n}")
    print("\n================ VERDICT ================")
    print("The lines above are EVERYTHING the model gets from this audio: numbers and text.")
    print("It did not hear the clip. 'Content' is judgeable from the transcript; 'Prosody' can")
    print("only be reasoned about from these features, not perceived — that is the gap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
