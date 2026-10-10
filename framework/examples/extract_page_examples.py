#!/usr/bin/env python3
"""Extract the labelled prosody audio examples embedded in the Audio Rating
Project contributor page.

The page embeds each example clip as a base64 `data:audio/...` URI inside an
<audio> tag, with the rating (and often an example letter + justification) in the
surrounding markup. This decodes each clip to a file and pulls the context so we
can label it, turning the page straight into a calibration set.

Input HTML is UNTRUSTED downloaded data: we only parse text out of it, never
execute it. Run isolated:  python3 -I examples/extract_page_examples.py <page.html> <out_dir>
"""

from __future__ import annotations

import base64
import html
import re
import sys
from pathlib import Path

_MIME_EXT = {"audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/wav": "wav",
             "audio/x-wav": "wav", "audio/ogg": "ogg", "audio/mp4": "m4a",
             "audio/webm": "webm"}

AUDIO_RE = re.compile(
    r'<audio\b[^>]*\bsrc="data:(?P<mime>audio/[a-z0-9.+-]+);base64,(?P<b64>[A-Za-z0-9+/=]+)"',
    re.IGNORECASE)


def _strip_tags(s: str) -> str:
    s = re.sub(r"(?is)<script.*?</script>", " ", s)
    s = re.sub(r"(?is)<style.*?</style>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2:
        sys.exit("usage: extract_page_examples.py <page.html> <out_dir>")
    page = Path(argv[0]).read_text(errors="replace")
    out = Path(argv[1]); out.mkdir(parents=True, exist_ok=True)

    rows = []
    for i, m in enumerate(AUDIO_RE.finditer(page), 1):
        mime = m.group("mime").lower()
        ext = _MIME_EXT.get(mime, "bin")
        try:
            data = base64.b64decode(m.group("b64"), validate=False)
        except Exception as e:  # pragma: no cover
            print(f"[{i}] decode failed: {e}", file=sys.stderr)
            continue
        # context = the markup right before this tag, de-tagged. Use the NEAREST
        # (last) "Rating N" heading above the clip — that's the block it belongs
        # to; the first match in a big window could be the previous block's.
        ctx = _strip_tags(page[max(0, m.start() - 2000):m.start()])
        rhits = re.findall(r"Rating\s*([1-5])", ctx)
        rating = rhits[-1] if rhits else ""
        ehits = re.findall(r"Example\s*([A-Z])", ctx)
        example = ehits[-1] if ehits else ""
        clip = out / f"example_{i:02d}_r{rating or 'x'}.{ext}"
        clip.write_bytes(data)
        rows.append((i, rating, example, len(data), str(clip), ctx[-200:]))

    print(f"Found {len(rows)} embedded audio example(s).\n")
    for i, rating, example, nbytes, path, tail in rows:
        print(f"[{i:02d}] rating={rating or '?'} example={example or '?'}  {nbytes} bytes  -> {Path(path).name}")
        print(f"     context: ...{tail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
