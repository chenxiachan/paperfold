"""The languages: a text can be read in every one of textfold/langs.py, and the interface speaks some of them.

A text read in a language the interface has no words for shows the interface in English, so a reading language needs
one line in langs.py and nothing more. An interface language needs more: its words in every table of
textfold/web/i18n.js, in the tutorial and in the desktop app's menu, and it must be a reading language too, under the
same name. Swedish and Danish were once reading languages that no menu offered (issue #13).

Run from the repo root:
    python3 -m unittest discover tests
"""
import re
import sys
import unittest
from pathlib import Path

from textfold import langs

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "textfold" / "web"


def rows(path, name):
    """The language codes of a table written `  const NAME = {`, one row per language, four spaces in."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"  const {name} = {{")
    found = set()
    for line in lines[start + 1:]:
        if line.startswith("  };"):
            return found
        m = re.match(r"    (?:'([\w-]+)'|\"([\w-]+)\"|([\w-]+)):", line)
        if m:
            found.add(next(g for g in m.groups() if g))
    raise AssertionError(f"{path.name}: {name} has no end")


def inline(path, name):
    """A table written on one statement, `const NAME = { en: '…', … };`: its codes and their words."""
    body = re.search(rf"const {name} = \{{(.*?)\}};", path.read_text(encoding="utf-8"), re.S).group(1)
    return dict(re.findall(r"(?:^|[{,\s])'?([\w-]+)'?: '([^']*)'", body))


INTERFACE = inline(WEB / "i18n.js", "NATIVE")


class LanguagesTest(unittest.TestCase):
    def test_the_interface_speaks_reading_languages_by_their_names(self):
        self.assertIn("en", INTERFACE)
        for code, native in INTERFACE.items():
            with self.subTest(code=code):
                self.assertIn(code, langs.LANGS, "an interface language a text cannot be read in")
                self.assertEqual(native, langs.LANGS[code][1])

    def test_every_table_of_the_interface(self):
        for name in ("S", "Z", "U", "F", "BY", "MV", "Q", "M", "DOCS"):
            with self.subTest(table=name):
                self.assertEqual(rows(WEB / "i18n.js", name), set(INTERFACE))

    def test_the_tutorial(self):
        self.assertEqual(rows(WEB / "tutorial.js", "W"), set(INTERFACE))

    def test_the_desktop_menu(self):
        main = ROOT / "desktop" / "main.js"
        if not main.exists():
            self.skipTest("no desktop/ here")
        self.assertEqual(set(inline(main, "CHECK")), set(INTERFACE))
        self.assertEqual(set(inline(main, "MISSING")), set(INTERFACE))   # (a link to a document not in the library)

    def test_the_website_names_every_reading_language(self):
        sys.path.insert(0, str(ROOT / "site"))
        try:
            from strings import LANGS_NATIVE
        finally:
            sys.path.pop(0)
        self.assertEqual(LANGS_NATIVE, ", ".join(langs.natives().values()))


if __name__ == "__main__":
    unittest.main()
