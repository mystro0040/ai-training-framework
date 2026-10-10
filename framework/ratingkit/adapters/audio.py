"""Audio adapter — the feasibility-gated one.

HONESTY, up front and in the output: a text LLM (Claude, as exposed through the
API and Claude Code) cannot ingest audio as sound. Its native inputs are text,
images, and PDFs — there is no audio modality. So this adapter does NOT make the
model "hear" the clip. It does the only honest thing a text pipeline can:

  1. extracts acoustic *features* from the waveform (pauses, energy dynamics,
     clipping) so a judge has objective prosody signal to reason over, and
  2. supplies / obtains a transcript for the Content dimension.

Feature extraction here is stdlib-only (the `wave` module) so it runs and tests
with zero installs, for 16/8/32-bit PCM WAV. Richer analysis (pitch via librosa)
and speech-to-text (whisper) are optional hooks: if the library is missing the
adapter degrades gracefully and the view's notes say exactly what to install.

A feature summary is NOT the same as hearing prosody. The Prosody dimension of a
"listen to the audio" rubric cannot be fully satisfied by a text model from
features alone — see ../../AGENTS.md and ../../assessment/. This adapter makes
the gap explicit rather than papering over it.
"""

from __future__ import annotations

import math
import statistics
import wave
from array import array
from pathlib import Path

from ..core.adapters import EvaluatorView
from ..core.item import Turn
from .. import settings

_HONESTY = ("Prosody values are EXTRACTED acoustic features, not the model "
            "hearing the audio. A text model cannot perceive sound directly.")

_ARRAY_CODE = {1: "b", 2: "h", 4: "i"}   # sampwidth bytes -> array typecode
_MAX_AMP = {1: 127, 2: 32767, 4: 2147483647}


class ProsodyError(ValueError):
    pass


def _read_wav_mono(path: str | Path):
    """Return (samples:list[int], framerate, sampwidth). Mono (channel 0)."""
    with wave.open(str(path), "rb") as w:
        nch, sw, fr, nframes = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(nframes)
    if sw not in _ARRAY_CODE:
        raise ProsodyError(f"unsupported sample width {sw*8}-bit; convert to 16-bit PCM WAV "
                           "(e.g. `ffmpeg -i in -ar 16000 -ac 1 -sample_fmt s16 out.wav`)")
    samples = array(_ARRAY_CODE[sw])
    samples.frombytes(raw)
    if sw == 1:  # 8-bit WAV is unsigned, centred at 128
        samples = array("i", (s - 128 for s in samples))
    if nch > 1:  # take channel 0
        samples = array("i", samples[0::nch])
    return samples, fr, sw


def extract_prosody_features(path: str | Path, transcript: str = "") -> dict:
    """Stdlib feature extraction from a PCM WAV. Returns a flat dict of numbers.

    These are objective signals a judge can use; they are not a verdict and not
    perception. See module docstring.
    """
    samples, fr, sw = _read_wav_mono(path)
    n = len(samples)
    if n == 0 or fr <= 0:
        raise ProsodyError("empty or malformed WAV")

    win = max(1, int(fr * settings.PROSODY_WINDOW_MS / 1000))
    win_sec = win / fr
    rms = []
    for i in range(0, n, win):
        chunk = samples[i:i + win]
        if not chunk:
            continue
        rms.append(math.sqrt(sum(s * s for s in chunk) / len(chunk)))
    if not rms:
        raise ProsodyError("no analysis windows")

    max_rms = max(rms) or 1.0
    thresh = settings.PROSODY_SILENCE_FRACTION * max_rms
    silent = [r < thresh for r in rms]

    # Pauses: runs of silent windows at least PROSODY_MIN_PAUSE_MS long.
    min_pause_win = max(1, int(settings.PROSODY_MIN_PAUSE_MS / settings.PROSODY_WINDOW_MS))
    pauses = []
    run_start = None
    for idx, is_sil in enumerate(silent + [False]):  # sentinel flush
        if is_sil and run_start is None:
            run_start = idx
        elif not is_sil and run_start is not None:
            length = idx - run_start
            if length >= min_pause_win:
                pauses.append({"start_sec": round(run_start * win_sec, 3),
                               "dur_sec": round(length * win_sec, 3)})
            run_start = None

    voiced = [r for r, s in zip(rms, silent) if not s]
    voiced_sec = len(voiced) * win_sec
    mean_v = statistics.fmean(voiced) if voiced else 0.0
    energy_cv = (statistics.pstdev(voiced) / mean_v) if len(voiced) > 1 and mean_v else 0.0

    max_amp = _MAX_AMP[sw]
    clip_level = 0.99 * max_amp
    clipping_fraction = sum(1 for s in samples if abs(s) >= clip_level) / n

    words = len(transcript.split())
    total_sec = n / fr
    # speaking_rate_wpm: words over the WHOLE clip (the standard "how fast did
    # they talk" — pauses count against the rate, as they should). Dividing by
    # voiced time only (the old bug) ignored pauses and overstated the rate
    # ~2x. articulation_rate_wpm keeps the voiced-only figure, named for what
    # it is: rate while actually phonating.
    wpm = round(words / (total_sec / 60), 1) if total_sec > 0 and words else 0.0
    artic_wpm = round(words / (voiced_sec / 60), 1) if voiced_sec > 0 and words else 0.0

    return {
        "duration_sec": round(total_sec, 3),
        "framerate_hz": fr,
        "voiced_sec": round(voiced_sec, 3),
        "voiced_fraction": round(voiced_sec / total_sec, 3),
        "num_pauses": len(pauses),
        "total_pause_sec": round(sum(p["dur_sec"] for p in pauses), 3),
        "pauses": pauses,
        "energy_cv": round(energy_cv, 3),      # low => monotone/flat dynamics
        "clipping_fraction": round(clipping_fraction, 5),  # artifact proxy
        "speaking_rate_wpm": wpm,              # words / total time; needs a transcript
        "articulation_rate_wpm": artic_wpm,    # words / voiced time only
    }


def _maybe_transcribe(path: str) -> tuple[str, list[str]]:
    """Optional STT hook. Returns (transcript, notes). Degrades if whisper absent."""
    try:
        import whisper  # type: ignore  # noqa: F401
    except Exception:
        return "", ["No transcript and speech-to-text unavailable. To auto-transcribe, "
                    "install one of: `pip install openai-whisper` (needs ffmpeg) or "
                    "`pip install faster-whisper`. Until then, provide `transcript` on the turn."]
    try:
        model = whisper.load_model("base")
        return model.transcribe(path).get("text", "").strip(), ["transcript via whisper(base)"]
    except Exception as e:  # pragma: no cover - depends on optional dep
        return "", [f"whisper present but transcription failed: {e}"]


class AudioAdapter:
    name = "audio"

    def can_handle(self, turn: Turn) -> bool:
        return bool(turn.audio)

    def view(self, item_id: str, turn: Turn) -> EvaluatorView:
        notes = [_HONESTY]
        transcript = turn.transcript
        prosody = None
        audio_ok = False

        src = turn.audio or ""
        is_wav = src.lower().endswith(".wav") and Path(src).exists()

        if not src:
            notes.append("turn.audio is empty")
        elif not Path(src).exists():
            notes.append(f"audio source not found on disk: {src!r} "
                         "(a URL/stream must be captured to a local WAV first — "
                         "e.g. via browser-attach + ffmpeg)")
        elif not is_wav:
            notes.append(f"audio {src!r} is not a .wav; convert with "
                         "`ffmpeg -i <in> -ar 16000 -ac 1 -sample_fmt s16 <out>.wav`")
        else:
            try:
                if not transcript:
                    transcript, tnotes = _maybe_transcribe(src)
                    notes += tnotes
                prosody = extract_prosody_features(src, transcript)
                audio_ok = True
            except ProsodyError as e:
                notes.append(f"prosody extraction failed: {e}")

        return EvaluatorView(
            item_id=item_id, turn_index=turn.index, label=turn.label,
            transcript=transcript, audio_available=audio_ok, prosody=prosody, notes=notes,
        )
