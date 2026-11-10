# VENDORED from agentic-core/global/clistyle/clistyle.py on 2026-11-10.
# Do not edit here; improve the canonical copy and re-vendor (see its ADOPTING.md).
"""clistyle - shared, themeable CLI output for the operator's tools.

CANONICAL copy: agentic-core/global/clistyle/clistyle.py. A general improvement lands
here first, then is VENDORED down into each adopting repo (see ADOPTING.md), exactly
like global/notify/notify.py.

Design contract
---------------
* Pure standard library. No third-party deps, ever.
* Never raises on normal use. An unknown theme falls back to the default; a bad colour
  policy falls back to auto. A tool that cannot even import this module should fall back
  to plain ``print()`` - adoption is ADDITIVE and FAIL-OPEN, so a tool never breaks.
* Colour is emitted only when it is safe: stdout is a TTY, ``NO_COLOR`` is unset, and
  ``TERM`` is not ``dumb``. ``CLI_STYLE_COLOR=always|never|auto`` overrides the auto rule.
* The default theme ``standard`` reproduces the house look the operator settled on
  (``workspace.py``/``reorganize.py``/``vault-sync-manager``): ``==>`` section markers,
  ``═`` rules, bold first item + dim detail, ``[OK ]``/``[-- ]`` style tags.
* The previous/plain look is preserved as the ``plain`` theme - the universal safe
  fallback and the thing to revert a tool to if the new look does not fit. Themes are a
  registry (``THEMES``); adding another is a few lines (see bottom of file).

Theme selection order (first that resolves wins), all fail-open:
  1. explicit name passed to ``styler(theme=...)``
  2. env ``CLI_STYLE``
  3. config file ``~/.config/offsec/cli_style`` (one line: a theme name)
  4. the default theme (``standard``)
A per-tool override always beats the global env/config.
"""

from __future__ import annotations

import os
import sys

__all__ = ["Styler", "Theme", "THEMES", "styler", "resolve_theme_name", "DEFAULT_THEME"]

DEFAULT_THEME = "standard"
_CONFIG_PATH = os.path.expanduser("~/.config/offsec/cli_style")


# ── colour policy ────────────────────────────────────────────────────────────

def _color_allowed(stream):
    """Auto rule, overridable by CLI_STYLE_COLOR=always|never|auto."""
    override = os.environ.get("CLI_STYLE_COLOR", "auto").strip().lower()
    if override == "always":
        return True
    if override == "never":
        return False
    try:
        tty = hasattr(stream, "isatty") and stream.isatty()
    except Exception:
        tty = False
    return bool(tty) and os.environ.get("NO_COLOR") is None and os.environ.get("TERM") != "dumb"


# ── themes ─────────────────────────────────────────────────────────────────--

# SGR codes by semantic role. A theme maps roles -> tuple of SGR codes ("" disables).
class Theme:
    """A named look. Glyphs + per-role colour codes + layout knobs."""

    def __init__(self, name, *, color, section_prefix, rule_char, rule_width,
                 indent, roles, tag_brackets=("[", "]")):
        self.name = name
        self.color = color                      # master switch for this theme
        self.section_prefix = section_prefix    # e.g. "==> "
        self.rule_char = rule_char              # e.g. "═" or "="
        self.rule_width = rule_width
        self.indent = indent                    # leading pad for items, e.g. "  "
        self.roles = roles                      # role -> tuple[str] of SGR codes
        self.tag_brackets = tag_brackets


THEMES = {
    # The look the operator settled on - unicode rules, colour, bold/dim.
    "standard": Theme(
        "standard", color=True, section_prefix="==> ", rule_char="═", rule_width=62,
        indent="  ",
        roles={
            "accent": ("1", "36"),   # bold cyan
            "bold":   ("1",),
            "dim":    ("2",),
            "ok":     ("32",),       # green
            "warn":   ("33",),       # yellow
            "err":    ("31",),       # red
            "info":   ("36",),       # cyan
            "muted":  ("2",),
        },
    ),
    # The universal safe fallback / revert target: ascii, no colour, minimal.
    "plain": Theme(
        "plain", color=False, section_prefix="==> ", rule_char="=", rule_width=62,
        indent="  ",
        roles={},   # no colour at all
    ),
}


def resolve_theme_name(explicit=None):
    """Return a valid theme name, fail-open, in precedence order."""
    for candidate in (explicit,
                      os.environ.get("CLI_STYLE"),
                      _read_config_theme()):
        if candidate and candidate.strip() in THEMES:
            return candidate.strip()
    return DEFAULT_THEME


def _read_config_theme():
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
            return fh.readline().strip()
    except Exception:
        return None


# ── the styler ─────────────────────────────────────────────────────────────--

class Styler:
    """Render house-style output under a chosen theme. Hold one per tool, or use the
    module default ``styler()``. All methods print to ``self.stream`` and also return
    the rendered string so callers can log/compose."""

    def __init__(self, theme=None, stream=None):
        name = theme if theme in THEMES else resolve_theme_name(theme)
        self.theme = THEMES.get(name, THEMES[DEFAULT_THEME])
        self.stream = stream if stream is not None else sys.stdout
        self.use_color = self.theme.color and _color_allowed(self.stream)

    # low-level colour
    def c(self, text, *codes):
        if not self.use_color or not codes:
            return text
        return "\033[" + ";".join(codes) + "m" + text + "\033[0m"

    def paint(self, text, role):
        return self.c(text, *self.theme.roles.get(role, ()))

    def _emit(self, s):
        print(s, file=self.stream)
        return s

    # building blocks
    def section(self, text):
        return self._emit(self.theme.section_prefix + self.paint(text, "accent"))

    def rule(self, title=None):
        bar = self.theme.rule_char * self.theme.rule_width
        if not title:
            return self._emit(self.paint(bar, "accent"))
        self._emit(self.paint(bar, "accent"))
        self._emit("  " + self.paint(title, "bold"))
        return self._emit(self.paint(bar, "accent"))

    def item(self, label, text, detail=None, status="plain"):
        tag = self.theme.tag_brackets[0] + label + self.theme.tag_brackets[1]
        role = {"ok": "ok", "warn": "warn", "err": "err", "info": "info"}.get(status)
        tag = self.paint(tag, role) if role else tag
        line = self.theme.indent + tag + " " + text
        if detail:
            line += "  " + self.paint(detail, "dim")
        return self._emit(line)

    def kv(self, key, value, width=0):
        return self._emit(self.paint(("%-*s" % (width, key)) if width else key, "bold")
                          + " : " + str(value))

    # one-line status helpers
    def ok(self, text):   return self._emit(self.theme.indent + self.paint("[OK ]", "ok") + " " + text)
    def fail(self, text): return self._emit(self.theme.indent + self.paint("[-- ]", "err") + " " + text)
    def warn(self, text): return self._emit(self.theme.indent + self.paint("[!]", "warn") + " " + text)
    def info(self, text): return self._emit(self.theme.indent + self.paint("[i]", "info") + " " + text)
    def note(self, text): return self._emit(self.paint(text, "dim"))

    def menu(self, title, options, footer=None):
        """Render a numbered house menu. ``options`` is a list of (key, label) or label
        strings; first entry is emphasised like the house default."""
        out = []
        out.append(self.rule(title))
        for i, opt in enumerate(options, 1):
            if isinstance(opt, (tuple, list)):
                key, label = opt[0], opt[1]
            else:
                key, label = str(i), opt
            label = self.paint(label, "bold") if i == 1 else label
            out.append(self._emit("  %2s) %s" % (key, label)))
        if footer:
            out.append(self._emit(self.paint(footer, "dim")))
        return "\n".join(str(x) for x in out)


def styler(theme=None, stream=None):
    """Factory: a Styler under the resolved theme. Pass ``theme`` to override per-tool."""
    return Styler(theme=theme, stream=stream)


# Adding a theme: insert a Theme(...) into THEMES above with the same roles keys. Tools
# pick it via CLI_STYLE=<name>, ~/.config/offsec/cli_style, or styler("<name>").
