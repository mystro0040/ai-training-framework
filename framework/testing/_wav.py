"""Test helper: synthesize a small PCM WAV (tone / silence / tone) with stdlib."""

import math
import struct
import wave


def tone(n, fr, freq=220.0, amp=10000):
    return [int(amp * math.sin(2 * math.pi * freq * i / fr)) for i in range(n)]


def write_tone_silence_tone(path, fr=16000, tone_sec=0.6, gap_sec=0.5):
    data = tone(int(tone_sec * fr), fr) + [0] * int(gap_sec * fr) + tone(int(tone_sec * fr), fr)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fr)
        w.writeframes(struct.pack("<%dh" % len(data), *data))
    return path
