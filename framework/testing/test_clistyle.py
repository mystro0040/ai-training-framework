"""Tests for global/clistyle/clistyle.py - the shared themeable CLI output module.

Invariants that matter:
  * plain theme NEVER emits ANSI, even when colour is forced on.
  * colour obeys CLI_STYLE_COLOR=always|never and the NO_COLOR / TERM=dumb auto rule.
  * theme resolution is precedence-ordered and FAIL-OPEN (unknown -> default).
  * the house building blocks render the expected shapes.

Pure stdlib, no network, no writes to tracked files.
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # vendored clistyle.py lives in framework/
import clistyle  # noqa: E402

ESC = "\033["


class _Env:
    """Context manager: set/clear env vars, restore on exit."""
    def __init__(self, **kv):
        self.kv = kv
        self.saved = {}

    def __enter__(self):
        for k, v in self.kv.items():
            self.saved[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *a):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _mk(theme, color="always"):
    with _Env(CLI_STYLE_COLOR=color):
        return clistyle.Styler(theme=theme, stream=io.StringIO())


class ColourPolicy(unittest.TestCase):
    def test_plain_never_colours_even_when_forced(self):
        s = _mk("plain", color="always")
        self.assertNotIn(ESC, s.section("hello"))
        self.assertNotIn(ESC, s.item("OK ", "done", status="ok"))

    def test_standard_colours_when_forced_on(self):
        s = _mk("standard", color="always")
        self.assertIn(ESC, s.section("hello"))

    def test_colour_off_when_forced_never(self):
        s = _mk("standard", color="never")
        self.assertNotIn(ESC, s.section("hello"))

    def test_no_color_env_disables_under_auto(self):
        # auto rule: NO_COLOR present -> no colour even if a tty claimed
        with _Env(CLI_STYLE_COLOR="auto", NO_COLOR="1"):
            s = clistyle.Styler(theme="standard", stream=io.StringIO())
            self.assertFalse(s.use_color)

    def test_term_dumb_disables_under_auto(self):
        with _Env(CLI_STYLE_COLOR="auto", NO_COLOR=None, TERM="dumb"):
            s = clistyle.Styler(theme="standard", stream=io.StringIO())
            self.assertFalse(s.use_color)


class ThemeResolution(unittest.TestCase):
    def test_unknown_theme_falls_back_to_default(self):
        with _Env(CLI_STYLE=None):
            self.assertEqual(clistyle.resolve_theme_name("does-not-exist"),
                             clistyle.DEFAULT_THEME)
            # and the Styler itself must not raise and must use the default
            s = clistyle.Styler(theme="does-not-exist", stream=io.StringIO())
            self.assertEqual(s.theme.name, clistyle.DEFAULT_THEME)

    def test_explicit_beats_env(self):
        with _Env(CLI_STYLE="plain"):
            self.assertEqual(clistyle.resolve_theme_name("standard"), "standard")

    def test_env_used_when_no_explicit(self):
        with _Env(CLI_STYLE="plain"):
            self.assertEqual(clistyle.resolve_theme_name(None), "plain")

    def test_default_when_nothing_set(self):
        with _Env(CLI_STYLE=None):
            # config file may or may not exist; a valid name either way
            self.assertIn(clistyle.resolve_theme_name(None), clistyle.THEMES)


class BuildingBlocks(unittest.TestCase):
    def test_section_has_prefix(self):
        s = _mk("plain")
        self.assertTrue(s.section("Workspace").startswith("==> "))

    def test_item_shape(self):
        s = _mk("plain")
        line = s.item("skip", "repo-x", detail="already here")
        self.assertIn("[skip] repo-x", line)
        self.assertIn("already here", line)

    def test_rule_width_and_char(self):
        s = _mk("plain")
        out = s.rule()
        self.assertEqual(out, "=" * 62)

    def test_menu_numbers_options(self):
        s = _mk("plain")
        s.menu("Pick", ["first", "second"])
        text = s.stream.getvalue()
        self.assertIn(" 1) first", text)
        self.assertIn(" 2) second", text)

    def test_methods_return_and_emit(self):
        s = _mk("plain")
        ret = s.ok("good")
        self.assertIn("good", ret)
        self.assertIn("good", s.stream.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
