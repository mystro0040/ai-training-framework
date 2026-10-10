#!/usr/bin/env python3
"""Build a self-contained HTML review console from a calibration set: every clip
as a tap-to-play player with its label, transcript and extracted features. Audio
is embedded as base64 so the page is one portable file (open on any device, no
server). Reusable for the human-review QUEUE too — same shape, different source.

  python3 examples/build_review_console.py --audio-dir <dir-of-mp3s> --out console.html
"""

from __future__ import annotations

import argparse
import base64
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ratingkit.core.calibration import CalibrationSet  # noqa: E402
from ratingkit.core.rubric import load_rubric  # noqa: E402

_MIME = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4", "ogg": "audio/ogg"}


def _data_uri(path: Path) -> str:
    ext = path.suffix.lstrip(".").lower()
    b = base64.b64encode(path.read_bytes()).decode()
    return f"data:{_MIME.get(ext, 'audio/mpeg')};base64,{b}"


def _find_audio(audio_dir: Path, ex_id: str) -> Path | None:
    for ext in ("mp3", "wav", "m4a", "ogg"):
        p = audio_dir / f"{ex_id}.{ext}"
        if p.exists():
            return p
    return None


def build(audio_dir: Path, dimension: str = "prosody") -> str:
    cs = CalibrationSet.load(dimension)
    rubric = load_rubric("multimodal_quality_evaluator")
    anchors = rubric.dimension(dimension).anchors
    examples = sorted(cs.examples, key=lambda e: (-e.label, e.id))

    cards = []
    for e in examples:
        ap = _find_audio(audio_dir, e.id)
        audio_html = (f'<audio controls preload="none" src="{_data_uri(ap)}"></audio>'
                      if ap else '<p class="missing">audio file not found</p>')
        f = e.features
        mp = max((p.get("dur_sec", 0.0) for p in f.get("pauses", [])), default=0.0)
        feats = [
            ("voiced", f"{f.get('voiced_fraction', 0) * 100:.0f}%"),
            ("pauses", f"{f.get('num_pauses', 0)} (max {mp:.1f}s)"),
            ("energy var", f"{f.get('energy_cv', 0):.2f}"),
            ("rate", f"{f.get('speaking_rate_wpm', 0):.0f} wpm"),
            ("clip", f"{f.get('clipping_fraction', 0) * 100:.2f}%"),
        ]
        feat_html = "".join(
            f'<div class="feat"><span class="fk">{k}</span>'
            f'<span class="fv">{html.escape(v)}</span></div>' for k, v in feats)
        label_word = {5: "excellent", 4: "good", 3: "mixed", 2: "poor", 1: "bad"}.get(e.label, "")
        cards.append(f"""
      <article class="card" data-rating="{e.label}">
        <header class="card-h">
          <span class="badge r{e.label}">{e.label}<small>/5</small></span>
          <div class="card-t">
            <h3>{html.escape(e.id.replace('_', ' '))}</h3>
            <p class="word">labeled {label_word}</p>
          </div>
        </header>
        {audio_html}
        <details class="tr"><summary>transcript</summary>
          <p>{html.escape(e.transcript or '(none)')}</p></details>
        <div class="feats">{feat_html}</div>
      </article>""")

    legend = "".join(
        f'<li><span class="badge r{s}">{s}</span>'
        f'<span>{html.escape(anchors.get(s, ""))}</span></li>'
        for s in sorted(anchors, reverse=True))

    filters = "".join(
        f'<button class="fbtn" data-f="{v}">{t}</button>'
        for v, t in [("all", "All"), ("5", "5"), ("4", "4"), ("3", "3"), ("2", "2"), ("1", "1")])

    return _TEMPLATE.format(cards="".join(cards), legend=legend, filters=filters,
                            n=len(examples))


_TEMPLATE = """<title>Prosody Reference Clips</title>
<style>
  /* Layout: a scannable review console — sticky header + filter, a column of
     labeled clip cards grouped high-to-low rating. Utilitarian, data-first. */
  :root {{
    --bg: #f5f4f1; --surface: #fffefb; --fg: #1c1a17; --muted: #6b6760;
    --line: #e2ded7; --accent: #8a5a2b;
    --r5:#2f8f5b; --r4:#6aa83a; --r3:#c99a1e; --r2:#d4762a; --r1:#c23b36;
    --font-display:"Fraunces",Georgia,serif;
    --font-body:"IBM Plex Sans",system-ui,sans-serif;
    --font-mono:"IBM Plex Mono",ui-monospace,monospace;
  }}
  @media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
    --bg:#15140f; --surface:#201e18; --fg:#eceae4; --muted:#9a948a;
    --line:#332f27; --accent:#d2954f;
    --r5:#49b277; --r4:#88c452; --r3:#e2b641; --r2:#e88c45; --r1:#e2635d;
    color-scheme: dark;
  }} }}
  :root[data-theme="dark"] {{
    --bg:#15140f; --surface:#201e18; --fg:#eceae4; --muted:#9a948a;
    --line:#332f27; --accent:#d2954f;
    --r5:#49b277; --r4:#88c452; --r3:#e2b641; --r2:#e88c45; --r1:#e2635d;
    color-scheme: dark;
  }}
  * {{ box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--fg); font-family: var(--font-body);
    line-height: 1.5; margin: 0; }}
  .wrap {{ max-width: 760px; margin-inline: auto; padding-inline: 16px;
    padding-block: 24px 64px; }}
  header.top h1 {{ font-family: var(--font-display); font-weight: 600;
    font-size: clamp(1.7rem, 5vw, 2.4rem); margin: 0 0 .2em; text-wrap: balance; }}
  header.top p {{ color: var(--muted); margin: 0 0 1em; max-width: 60ch; }}
  .legend {{ list-style: none; margin: 0 0 1.5em; padding: 14px 16px;
    background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
    display: grid; gap: 10px; }}
  .legend li {{ display: grid; grid-template-columns: auto 1fr; gap: 12px;
    align-items: start; font-size: .9rem; color: var(--muted); }}
  .legend li span:last-child {{ min-width: 0; }}
  .filter {{ position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5;
    display: flex; gap: 8px; flex-wrap: wrap; padding: 10px 0;
    background: var(--bg); margin-bottom: 8px; }}
  .fbtn {{ font: inherit; font-size: .85rem; padding: 6px 14px; cursor: pointer;
    border: 1px solid var(--line); background: var(--surface); color: var(--fg);
    border-radius: 999px; }}
  .fbtn[aria-pressed="true"] {{ background: var(--accent); color: #fff;
    border-color: var(--accent); }}
  .fbtn:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
  .grid {{ display: grid; gap: 14px; }}
  .card {{ background: var(--surface); border: 1px solid var(--line);
    border-radius: 14px; padding: 16px; display: grid; gap: 12px; }}
  .card-h {{ display: flex; gap: 12px; align-items: center; }}
  .card-t h3 {{ margin: 0; font-size: 1rem; font-weight: 600;
    font-variant: small-caps; letter-spacing: .02em; }}
  .card-t .word {{ margin: 0; color: var(--muted); font-size: .82rem; }}
  .badge {{ flex: none; width: 46px; height: 46px; border-radius: 10px;
    display: grid; place-content: center; color: #fff; font-weight: 700;
    font-size: 1.3rem; font-variant-numeric: tabular-nums; }}
  .badge small {{ font-size: .6rem; font-weight: 500; opacity: .85; }}
  .badge.r5 {{ background: var(--r5); }} .badge.r4 {{ background: var(--r4); }}
  .badge.r3 {{ background: var(--r3); }} .badge.r2 {{ background: var(--r2); }}
  .badge.r1 {{ background: var(--r1); }}
  audio {{ width: 100%; }}
  .tr summary {{ cursor: pointer; color: var(--accent); font-size: .85rem;
    font-weight: 600; }}
  .tr p {{ margin: .6em 0 0; font-size: .9rem; color: var(--fg); }}
  .feats {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .feat {{ display: flex; gap: 6px; align-items: baseline; font-family: var(--font-mono);
    font-size: .74rem; background: var(--bg); border: 1px solid var(--line);
    border-radius: 7px; padding: 3px 8px; }}
  .feat .fk {{ color: var(--muted); }}
  .feat .fv {{ font-variant-numeric: tabular-nums; }}
  .missing {{ color: var(--r1); font-size: .85rem; }}
  @media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior: auto; }} }}
</style>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">

<div class="wrap">
  <header class="top">
    <h1>Prosody Reference Clips</h1>
    <p>The {n} human-labeled audio examples from the Audio Rating Project guide, each
      with its prosody rating, transcript and the acoustic features extracted from it.
      Tap to play; use the filter to isolate a rating band. These are the ground-truth
      references the rating pipeline calibrates against.</p>
  </header>

  <ul class="legend">{legend}</ul>

  <nav class="filter" aria-label="Filter by rating">{filters}</nav>

  <main class="grid" id="grid">{cards}</main>
</div>

<script>
  (function () {{
    var btns = Array.prototype.slice.call(document.querySelectorAll(".fbtn"));
    var cards = Array.prototype.slice.call(document.querySelectorAll(".card"));
    function apply(f) {{
      cards.forEach(function (c) {{ c.hidden = !(f === "all" || c.dataset.rating === f); }});
      btns.forEach(function (b) {{ b.setAttribute("aria-pressed", String(b.dataset.f === f)); }});
    }}
    btns.forEach(function (b) {{ b.addEventListener("click", function () {{ apply(b.dataset.f); }}); }});
    apply("all");
  }})();
</script>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audio-dir", required=True, help="dir holding <example_id>.<ext> clips")
    ap.add_argument("--dimension", default="prosody")
    ap.add_argument("--out", required=True, help="output HTML path")
    args = ap.parse_args(argv)
    htmltext = build(Path(args.audio_dir), args.dimension)
    Path(args.out).write_text(htmltext)
    kb = len(htmltext.encode()) / 1024
    print(f"wrote {args.out}  ({kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
