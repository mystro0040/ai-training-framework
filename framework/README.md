# ratingkit — a general-purpose rating / evaluation engine

Built general-first (your Gen Dev pattern): a reusable engine + a rubric *data*
format usable by any future training/rating project, with the specific
"Multimodal Quality Evaluator" app sitting on top as data + adapters. Same
layering as `autoweb` (engine / modules / profiles).

```
platform/
  ratingkit/
    core/        engine, data model, validation — domain-neutral, no rubric/modality logic
      engine.py      iterate target turns -> adapter -> scorer -> validate -> persist (resume)
      item.py        Item / Turn model + JSON loader
      rubric.py      Rubric loaded from a data profile; structural validation
      scoring.py     Score model + validation + pluggable Scorer (smoke | prompt | your model)
      adapters.py    EvaluatorView + adapter registry
      store.py       per-run results.jsonl + resume state
    adapters/    one per modality
      transcript.py  always-available text fallback
      audio.py       stdlib WAV prosody-FEATURE extraction (see the honesty note below)
    rubrics/     pure-data rubric profiles (one module each, exposing RUBRIC)
      multimodal_quality_evaluator.py
      _example.py
    main.py      interactive CLI (bare) + flags (scripting)
    settings.py
  examples/sample_item.json
  testing/       pytest suite (stdlib-only; synthesises its own WAV)
```

## The honest part — audio & prosody

A text LLM cannot ingest audio as sound; its native inputs are text, images and
PDFs. So the audio adapter does **not** make the model "hear" a clip. It extracts
acoustic **features** (pauses, energy dynamics, clipping, speaking rate) so a
judge has objective prosody signal, and it supplies/obtains a transcript for
Content. Every audio view carries a note saying so, and the Prosody score is an
honest `discard` when there is no audio. Fully closing the Prosody dimension
needs an **audio-native** judge or a feature pipeline we agree stands in for
"listening" — see `../AGENTS.md` and `../assessment/`.

## Run it

```bash
cd platform
python3 -m ratingkit.main --list-rubrics
python3 -m ratingkit.main --rubric multimodal_quality_evaluator \
        --items examples/sample_item.json --scorer smoke --run demo
python3 -m ratingkit.main            # interactive
```

Scorers: `smoke` (deterministic offline reference — proves the pipeline, not a
real judgement), `prompt` (renders the per-turn prompt a model/human answers).
The real task swaps in a model-backed scorer (subclass `PromptScorer`).

## Test

```bash
cd platform
python3 -m pytest testing -q        # stdlib only; no network, no installs
```

## Optional installs (only for richer audio; not needed for the engine or tests)

- Speech-to-text (auto-transcribe audio): `pip install openai-whisper` (needs
  `ffmpeg`) **or** `pip install faster-whisper`.
- Pitch/intonation features: `pip install librosa` (future hook).
- Non-WAV audio: `ffmpeg` to convert to 16 kHz mono 16-bit WAV.

The engine, both adapters' core paths, and the whole test suite run with **zero**
installs.
