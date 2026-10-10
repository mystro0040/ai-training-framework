#!/usr/bin/env python3
"""Human-paced CDP browser driver — operate a real Chromium over the DevTools port,
the way a person would: map the page first, then act with small delays and mouse
movement. Built for the general browser-attach capability (see agentic-core skill).

Connects to an ALREADY-RUNNING Chromium (never launches/closes it): the operator
sees every click in their own window. Frame-aware — Apps Script / embedded apps
render inside a nested iframe, so map and click search ALL frames.

Subcommands (operate on the chosen tab; --match <substr> picks it by URL, else last):
  map                     structure of the page: title, url, frames, clickable elements, text
  goto <url>              navigate, then map
  click "<text>"          click the element whose visible text/label matches (human move+click)
  clicksel "<css>"        click by CSS selector
  type "<css>" "<text>"   type into a field, per-char delay
  audio                   list <audio> elements and whether playing
  play [n]                click play on the Nth audio/playcontrol (default 1)
  scroll [px]             scroll the content frame down by px (default 700)
  eval "<js>"             run JS in the content frame (the frame with the most text), print result
  shot <path>             screenshot to a PNG

  python3 examples/drive.py goto "https://example.com/app" --match example.com
"""

from __future__ import annotations

import argparse
import random
import sys
import time

CDP = "http://127.0.0.1:9222"


def hpause(a=0.4, b=1.2):
    time.sleep(random.uniform(a, b))


def _pick_page(ctx, match):
    pages = [p for p in ctx.pages if not p.url.startswith("devtools://")]
    if match:
        for p in pages:
            if match in p.url:
                return p
    return pages[-1] if pages else ctx.new_page()


def _frames(page):
    return page.frames


def _clickables(frame):
    js = """() => {
      const out = [];
      const sel = 'a,button,[role=button],input[type=submit],input[type=button],summary,[onclick]';
      for (const el of document.querySelectorAll(sel)) {
        const r = el.getBoundingClientRect();
        if (r.width < 1 || r.height < 1) continue;
        const t = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().replace(/\\s+/g,' ');
        out.push({tag: el.tagName.toLowerCase(), text: t.slice(0,80)});
      }
      return out;
    }"""
    try:
        return frame.evaluate(js)
    except Exception:
        return []


def _text(frame, limit=1800):
    try:
        t = frame.evaluate("() => document.body ? document.body.innerText : ''")
        return " ".join(t.split())[:limit]
    except Exception:
        return ""


def do_map(page):
    print(f"URL   : {page.url}")
    print(f"TITLE : {page.title()}")
    frames = _frames(page)
    print(f"FRAMES: {len(frames)}")
    for i, fr in enumerate(frames):
        clk = _clickables(fr)
        txt = _text(fr)
        if not txt and not clk and i > 0:
            continue
        tag = "main" if fr == page.main_frame else f"iframe[{i}]"
        print(f"\n--- frame {i} ({tag}) url={fr.url[:90]}")
        if clk:
            print("  clickable:")
            for c in clk[:40]:
                print(f"    <{c['tag']}> {c['text']!r}")
        if txt:
            print(f"  text: {txt}")


def _human_click(page, handle):
    try:
        box = handle.bounding_box()
        if box:
            x = box["x"] + box["width"] / 2 + random.uniform(-4, 4)
            y = box["y"] + box["height"] / 2 + random.uniform(-3, 3)
            page.mouse.move(x - random.uniform(30, 80), y - random.uniform(20, 50), steps=3)
            hpause(0.15, 0.4)
            page.mouse.move(x, y, steps=random.randint(4, 9))
            hpause(0.1, 0.3)
    except Exception:
        pass
    handle.click()


def _find_by_text(page, text):
    text_l = text.lower()
    for fr in _frames(page):
        for role in ("button", "link"):
            try:
                loc = fr.get_by_role(role, name=text, exact=False)
                if loc.count() > 0:
                    return loc.first
            except Exception:
                pass
        try:
            loc = fr.locator(f"text={text}")
            if loc.count() > 0:
                return loc.first
        except Exception:
            pass
    # loose: scan clickables
    for fr in _frames(page):
        for sel in ("a", "button", "[role=button]", "summary"):
            loc = fr.locator(sel)
            for i in range(min(loc.count(), 60)):
                try:
                    if text_l in (loc.nth(i).inner_text() or "").lower():
                        return loc.nth(i)
                except Exception:
                    pass
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["map", "goto", "click", "clicksel", "type", "audio", "play",
                                    "scroll", "eval", "frames", "clickxy", "shot"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--match", default="", help="pick the tab whose URL contains this")
    a = ap.parse_args(argv)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = _pick_page(ctx, a.match)

        if a.cmd == "goto":
            page.goto(a.args[0], wait_until="domcontentloaded")
            hpause(1.0, 2.0)
            do_map(page)
        elif a.cmd == "map":
            do_map(page)
        elif a.cmd == "click":
            h = _find_by_text(page, a.args[0])
            if not h:
                print(f"NOT FOUND: {a.args[0]!r}"); return 2
            _human_click(page, h)
            hpause(1.0, 2.0)
            do_map(page)
        elif a.cmd == "clicksel":
            for fr in _frames(page):
                loc = fr.locator(a.args[0])
                if loc.count() > 0:
                    _human_click(page, loc.first); break
            hpause(1.0, 2.0)
            do_map(page)
        elif a.cmd == "type":
            css, text = a.args[0], a.args[1]
            for fr in _frames(page):
                loc = fr.locator(css)
                if loc.count() > 0:
                    loc.first.click(); hpause()
                    loc.first.type(text, delay=random.randint(40, 110)); break
            print("typed")
        elif a.cmd == "audio":
            for fr in _frames(page):
                info = fr.evaluate("""() => Array.from(document.querySelectorAll('audio')).map(a=>
                    ({src:(a.currentSrc||a.src||'').slice(0,60), paused:a.paused, dur:a.duration, t:a.currentTime}))""")
                if info:
                    print(f"frame {fr.url[:60]}: {info}")
        elif a.cmd == "play":
            n = int(a.args[0]) if a.args else 1
            done = False
            for fr in _frames(page):
                loc = fr.locator("audio")
                if loc.count() >= n:
                    fr.evaluate("(i)=>document.querySelectorAll('audio')[i].play()", n - 1)
                    print(f"playing audio {n}"); done = True; break
            if not done:
                print("no audio element to play")
        elif a.cmd == "clickxy":
            x, y = float(a.args[0]), float(a.args[1])
            page.mouse.move(x - random.uniform(40, 90), y - random.uniform(25, 55), steps=3)
            hpause(0.15, 0.4)
            page.mouse.move(x + random.uniform(-3, 3), y + random.uniform(-2, 2),
                            steps=random.randint(4, 9))
            hpause(0.1, 0.3)
            page.mouse.click(x, y)
            hpause(1.0, 2.0)
            print(f"clicked ({x},{y})")
        elif a.cmd == "frames":
            for i, fr in enumerate(_frames(page)):
                try:
                    t = fr.evaluate("() => document.body ? document.body.innerText : ''") or ""
                except Exception as e:
                    t = f"<eval failed: {type(e).__name__}>"
                marks = [m for m in ("Separation test", "Continue to next", "Process outline",
                                     "Key takeaway", "audio") if m in t]
                print(f"[{i}] len={len(t)} url={fr.url[:70]} marks={marks}")
        elif a.cmd == "scroll":
            px = int(a.args[0]) if a.args else 700
            # hover over the content area, then wheel — scrolls whatever is under the cursor
            page.mouse.move(700, 430, steps=3)
            hpause(0.1, 0.3)
            page.mouse.wheel(0, px)
            # also try scrolling the scroll container inside every frame
            for fr in _frames(page):
                try:
                    fr.evaluate(f"""() => {{
                        (document.scrollingElement||document.body).scrollBy(0,{px});
                        for (const el of document.querySelectorAll('*')) {{
                           if (el.scrollHeight > el.clientHeight + 40) {{ el.scrollTop += {px}; }}
                        }}
                    }}""")
                except Exception:
                    pass
            hpause(0.6, 1.2)
            print(f"scrolled {px}px")
        elif a.cmd == "eval":
            cf = max(_frames(page), key=lambda f: len(_text(f, 400)))
            try:
                print(repr(cf.evaluate(a.args[0])))
            except Exception as e:
                print(f"eval error: {e}")
        elif a.cmd == "shot":
            path = a.args[0] if a.args else "/tmp/claude-1000/shot.png"
            page.screenshot(path=path, full_page=True)
            print(f"shot -> {path}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
